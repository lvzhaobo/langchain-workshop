"""
DAG 模式 5：Supervisor 路由（Orchestrator）

图结构：
                        ┌→ [代码审查 Agent] ──┐
  [Supervisor] ──路由───┼→ [文档审查 Agent] ──┼──→ [Supervisor]（循环决策）
                        └→ [测试审查 Agent] ──┘          │
                                                    [FINISH] → END

API 映射：
  Supervisor 是一个 LLM 驱动的路由节点
  每次 Worker 完成后回到 Supervisor → Supervisor 决定下一个 Worker 或 FINISH
  add_conditional_edges 实现路由循环

运行：
  export DASHSCOPE_API_KEY="sk-..."
  python 5_supervisor.py
"""

import os, time
from typing import TypedDict, Annotated
from datetime import datetime, timezone, timedelta
from operator import add
from langgraph.graph import StateGraph, END

CST = timezone(timedelta(hours=8))


# ====== State ======
class State(TypedDict):
    task: str
    messages: Annotated[list[str], add]  # 对话历史
    next_worker: str                      # "code_reviewer" | "doc_reviewer" | "test_reviewer" | "FINISH"
    results: Annotated[list[str], add]    # 各 Worker 的结果


# ====== LLM ======
def _init_llm():
    key = os.getenv("DASHSCOPE_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not key:
        return None, "mock"
    from langchain_openai import ChatOpenAI
    if os.getenv("DASHSCOPE_API_KEY"):
        return ChatOpenAI(model="qwen-plus", api_key=key, base_url="https://dashscope.aliyuncs.com/compatible-mode/v1", temperature=0.7), "bailian"
    return ChatOpenAI(model="gpt-4o-mini", api_key=key, temperature=0.7), "openai"


llm, mode = _init_llm()

# Worker 定义 — Supervisor 可调度的专家池
WORKERS = {
    "code_reviewer": "代码审查专家：检查代码质量、安全漏洞、性能问题",
    "doc_reviewer": "文档审查专家：检查文档完整性、可读性、API 文档准确性",
    "test_reviewer": "测试审查专家：检查测试覆盖率、测试用例设计、边界条件",
}


def _call(prompt: str) -> str:
    if llm is None:
        time.sleep(0.2)
        return ""
    return llm.invoke(prompt).content


# ====== Nodes ======
def supervisor_node(s: State) -> dict:
    """
    Supervisor — LLM 驱动的调度中心
    分析当前状态，决定下一个调用的 Worker
    """
    results_done = s.get("results", [])
    workers_called = len(results_done)

    print(f"\n👑 [Supervisor] 调度决策中... (已完成 {workers_called} 个 Worker)")

    # 构造决策 prompt
    worker_desc = "\n".join([f"- {k}: {v}" for k, v in WORKERS.items()])
    completed = "\n".join(results_done) if results_done else "(尚无)"

    if llm:
        prompt = (
            f"你是一个项目审查的 Supervisor。你的团队有这些专家：\n{worker_desc}\n\n"
            f"审查任务：{s['task']}\n\n"
            f"已完成的审查：\n{completed}\n\n"
            f"请决定下一步："
            f"如果需要更多审查，回复 NEXT: <worker_name>（从 code_reviewer/doc_reviewer/test_reviewer 中选择一个尚未调用的）"
            f"如果所有必要的审查已完成，回复 FINISH"
        )
        decision = _call(prompt).strip()
    else:
        # Mock 模拟：依次调用三个 Worker
        order = ["code_reviewer", "doc_reviewer", "test_reviewer"]
        if workers_called < len(order):
            decision = f"NEXT: {order[workers_called]}"
        else:
            decision = "FINISH"

    # 解析决策
    if "FINISH" in decision.upper():
        next_worker = "FINISH"
    else:
        # 提取 worker 名称
        for w in WORKERS:
            if w in decision:
                next_worker = w
                break
        else:
            next_worker = "FINISH" if workers_called >= 3 else "code_reviewer"

    print(f"   → 决策: {next_worker}")
    return {"next_worker": next_worker}


def code_reviewer_node(s: State) -> dict:
    print(f"\n🔒 [代码审查 Agent] 工作中...")
    result = _call(f'审查以下任务相关的代码方面：{s["task"]}。用 2 句话总结。')
    return {"results": [f"【代码审查】{result or '代码结构良好，建议补充单元测试。'}"]}


def doc_reviewer_node(s: State) -> dict:
    print(f"\n📄 [文档审查 Agent] 工作中...")
    result = _call(f'审查以下任务相关的文档方面：{s["task"]}。用 2 句话总结。')
    return {"results": [f"【文档审查】{result or '文档较完整，建议增加使用示例。'}"]}


def test_reviewer_node(s: State) -> dict:
    print(f"\n🧪 [测试审查 Agent] 工作中...")
    result = _call(f'审查以下任务相关的测试方面：{s["task"]}。用 2 句话总结。')
    return {"results": [f"【测试审查】{result or '测试覆盖率不足，建议补充边界条件测试。'}"]}


# ====== 路由函数 ======
def supervisor_router(s: State) -> str:
    """根据 Supervisor 的决策路由到对应 Worker 或结束"""
    next_w = s.get("next_worker", "FINISH")
    if next_w == "FINISH":
        return "FINISH"
    return next_w


def worker_router(s: State) -> str:
    """Worker 完成后总是回到 Supervisor"""
    return "supervisor"


# ====== Build Graph ======
builder = StateGraph(State)
builder.add_node("supervisor", supervisor_node)
builder.add_node("code_reviewer", code_reviewer_node)
builder.add_node("doc_reviewer", doc_reviewer_node)
builder.add_node("test_reviewer", test_reviewer_node)

builder.set_entry_point("supervisor")

# Supervisor → 各 Worker 或 END
builder.add_conditional_edges(
    "supervisor",
    supervisor_router,
    {
        "code_reviewer": "code_reviewer",
        "doc_reviewer": "doc_reviewer",
        "test_reviewer": "test_reviewer",
        "FINISH": END,
    }
)

# 每个 Worker → 回到 Supervisor（形成循环调度）
builder.add_edge("code_reviewer", "supervisor")
builder.add_edge("doc_reviewer", "supervisor")
builder.add_edge("test_reviewer", "supervisor")

app = builder.compile()


# ====== Run ======
if __name__ == "__main__":
    print("=" * 50)
    print(f"📐 DAG 模式 5：Supervisor 路由 [{mode.upper()}]")
    print("=" * 50)
    print("图拓扑: Supervisor ⇄ Workers（循环调度）")
    print("  [Supervisor] ──→ Worker A ──→ [Supervisor]")
    print("               ──→ Worker B ──→ [Supervisor]")
    print("               ──→ FINISH   ──→ END")
    print("边类型: Supervisor 是 LLM 驱动的路由节点，动态决策")
    print()

    task = "审查一个 Python Web 项目的代码质量、文档完整性和测试覆盖率"
    print(f"📝 任务: {task}\n")

    result = app.invoke({"task": task}, {"recursion_limit": 20})

    print(f"\n{'='*50}")
    print(f"📊 审查完成！共调用 {len(result.get('results', []))} 个 Worker")
    for r in result.get("results", []):
        print(f"  {r}")
    print(f"\n💡 Supervisor 模式的核心: LLM 自主决定'下一步调用谁'")

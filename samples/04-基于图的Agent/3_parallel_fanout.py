"""
DAG 模式 3：并行扇出/扇入（Fan-out / Fan-in = Map-Reduce）

图结构：
                         ┌→ [安全审查] ──┐
  [分发] ──Fan-out──┼→ [性能审查] ──┼──Fan-in──→ [汇总] → END
                         └→ [风格审查] ──┘

API 映射：
  LangGraph Send API：节点返回 [Send("node", state), ...]
  每个 Send 创建一个并行执行分支
  State 中用 Annotated[list, reducer] 自动合并结果

运行：
  export DASHSCOPE_API_KEY="sk-..."
  python 3_parallel_fanout.py
"""

import os, time
from typing import TypedDict, Annotated
from datetime import datetime, timezone, timedelta
from operator import add  # list reducer
from langgraph.graph import StateGraph, END
from langgraph.types import Send

CST = timezone(timedelta(hours=8))


# ====== State ======
class State(TypedDict):
    diff: str                             # 输入：代码 diff
    dimensions: list[str]                 # 审查维度列表
    reviews: Annotated[list[str], add]    # 关键！Annotated + add = 自动追加合并
    final_report: str


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


def _call(prompt: str) -> str:
    if llm is None:
        time.sleep(0.2)
        return ""
    return llm.invoke(prompt).content


# ====== Nodes ======
def dispatcher_node(s: State) -> dict:
    """
    分发节点 — 返回要审查的维度列表
    每个维度会创建一个 Send 到 reviewer 节点
    """
    print(f"\n📦 [dispatcher] 分发审查任务...")
    dimensions = ["安全性", "性能", "代码风格"]
    print(f"   维度: {dimensions}")
    return {"dimensions": dimensions}


def reviewer_node(s: State) -> dict:
    """
    审查节点 — 对单个维度进行审查
    此节点会被 Fan-out 为 3 个并行实例
    """
    dimension = s["dimensions"][-1] if s.get("dimensions") else "?"  # 当前维度
    start = time.time()
    print(f"\n🔍 [reviewer] 审查维度: {dimension} ...")

    content = _call(f'从「{dimension}」角度审查以下代码变更。用 2-3 句话总结发现：\n\n{s["diff"]}')
    review = content or f"[{dimension}] Mock 审查结果：建议改进。"
    elapsed = round((time.time() - start) * 1000)
    print(f"   ✅ {dimension} 完成 ({elapsed}ms)")

    # 返回结果 — Annotated[list, add] 会自动追加到 reviews
    return {"reviews": [f"## {dimension} 审查\n{review}\n"]}


def _continue_to_reviewers(state: State) -> list[Send]:
    """
    关键函数！LangGraph 的 Fan-out 机制：
    返回 Send 列表 → 每个 Send 创建一个 reviewer 并行实例
    """
    dimensions = state.get("dimensions", [])
    return [Send("reviewer", {"diff": state["diff"], "dimensions": [d]}) for d in dimensions]


def aggregator_node(s: State) -> dict:
    """
    汇总节点 — 等待所有 reviewer 完成后自动触发
    reviews 字段已通过 Annotated[list, add] 自动合并
    """
    all_reviews = s.get("reviews", [])
    print(f"\n📊 [aggregator] 汇总 {len(all_reviews)} 条审查意见...")

    combined = "\n".join(all_reviews)
    report = _call(f'将以下多条审查意见汇总为一个简洁的审查报告（200字以内）：\n\n{combined}')
    final = report or f"汇总报告（{len(all_reviews)} 条意见）:\n{combined[:300]}"
    return {"final_report": final}


# ====== Build Graph ======
builder = StateGraph(State)
builder.add_node("dispatcher", dispatcher_node)
builder.add_node("reviewer", reviewer_node)
builder.add_node("aggregator", aggregator_node)

builder.set_entry_point("dispatcher")
builder.add_conditional_edges("dispatcher", _continue_to_reviewers)  # Fan-out！
builder.add_edge("reviewer", "aggregator")                           # 汇总（多个结果先合并）
builder.add_edge("aggregator", END)

app = builder.compile()


# ====== Run ======
if __name__ == "__main__":
    print("=" * 60)
    print(f"📐 DAG 模式 3：并行扇出/扇入 [{mode.upper()}]")
    print("=" * 60)
    print("图拓扑:")
    print("  [dispatcher] ──Send──▶ [reviewer(安全)] ──┐")
    print("               ──Send──▶ [reviewer(性能)] ──┼──▶ [aggregator] → END")
    print("               ──Send──▶ [reviewer(风格)] ──┘")
    print("边类型: add_conditional_edges + Send API（动态 Fan-out）")
    print("State: Annotated[list, add] = 自动追加合并 Fan-in 结果")
    print()

    diff = """
+ const userInput = req.body.input;
+ const query = `SELECT * FROM users WHERE name='${userInput}'`;
+ console.log(query);
+ // 新增: 前端直接调用数据库
+ app.get('/api/users', (req, res) => {
+   const data = db.query('SELECT * FROM users');
+   res.json(data);
+ });
"""
    print(f"📝 输入代码 diff:\n{diff}\n")
    print("⏳ 三个审查维度将并行执行...\n")

    start = time.time()
    result = app.invoke({"diff": diff})
    total = round((time.time() - start) * 1000)

    print(f"\n{'='*60}")
    print(f"📊 最终审查报告（总耗时 {total}ms）")
    print(f"{'='*60}")
    print(result["final_report"])
    print(f"\n💡 三个审查并行执行，总时间 ≈ 最慢的那个审查（而非三者之和）")

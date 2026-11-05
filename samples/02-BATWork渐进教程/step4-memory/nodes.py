"""
Agent Loop 的 7 个节点函数

每个节点接收 AgentState，返回部分更新的 dict，
LangGraph 自动合并到共享 State 中。

Step 4 新增：Memory 记忆系统集成
- enrich_context 节点调用 memory.recall() 检索历史记忆
- 项目知识库自动注入上下文
"""

from __future__ import annotations
import os
import json
from typing import Any
from langchain_core.messages import AIMessage, HumanMessage
from state import AgentState  # noqa: E402
from tools import describe_all, call_tool  # noqa: E402


# LLM 实例（由 agent.py 的 build_graph 注入）
_llm: Any = None
# Memory 实例（由 agent.py 的 build_graph 注入，Step 4 新增）
_memory: Any = None

def set_llm(llm: Any) -> None:
    global _llm
    _llm = llm

def set_memory(memory: Any) -> None:
    """注入 Memory 实例（Step 4 新增）"""
    global _memory
    _memory = memory


def _call_llm(prompt: str) -> str:
    """封装 LLM 调用"""
    if _llm is None:
        raise RuntimeError("LLM 未初始化，请先调用 set_llm()")
    resp = _llm.invoke(prompt)
    return resp.content


# ══════════════════════════════════════════════
#  Node 1: 意图理解
# ══════════════════════════════════════════════

def understand_intent(state: AgentState) -> dict:
    """
    把用户的自然语言输入提炼为结构化意图
    """

    prompt = f"""你是一个智能任务分析助手。分析以下用户输入，提炼为结构化意图描述。

要求：
1. 核心目标：用户到底想完成什么
2. 输入数据：需要什么文件或资料（如果提到了）
3. 期望输出：用户想要什么格式的结果（报告/表格/图表/PPT等）
4. 约束条件：用户提到的任何限制或偏好

用户输入：
{state['user_input']}

工作目录：{state['workspace_path']}

请用简洁的中文回答，每点一行。"""

    intent = _call_llm(prompt)

    print(f"\n{'─'*50}")
    print(f"📋 [Node 1] 意图理解")
    print(f"{'─'*50}")
    print(intent)

    return {
        "intent": intent,
        "messages": [HumanMessage(content=state["user_input"])],
    }


# ══════════════════════════════════════════════
#  Node 2: 上下文补齐
# ══════════════════════════════════════════════

def enrich_context(state: AgentState) -> dict:
    """
    扫描工作目录、加载可用工具列表、召回历史记忆，补齐 Agent 执行所需的上下文
    
    Step 4 新增：调用 memory.recall() 检索相关历史记忆，注入项目知识库
    """

    ws = state["workspace_path"]
    files = []
    if os.path.exists(ws):
        for f in sorted(os.listdir(ws)):
            full = os.path.join(ws, f)
            if os.path.isfile(full) and not f.startswith("."):
                files.append(f)

    tools_desc = describe_all()

    # ── Step 4 新增：召回历史记忆 ──
    memory_context = ""
    project_context = ""
    if _memory is not None:
        # 根据意图和用户输入召回相关历史
        query_for_recall = f"{state.get('intent', '')} {state['user_input']}"
        memory_context = _memory.recall(query_for_recall)
        # 读取项目知识库
        project_context = _memory.get_project_context()

    context = f"""工作目录文件: {files if files else '(空)'}
工作目录路径: {ws}

{project_context}

{memory_context}

可用工具列表:
{tools_desc}"""

    print(f"\n{'─'*50}")
    print(f"🔍 [Node 2] 上下文补齐")
    print(f"{'─'*50}")
    print(context[:500])

    return {
        "enriched_context": context,
    }


# ══════════════════════════════════════════════
#  Node 3: 任务规划
# ══════════════════════════════════════════════

def plan_tasks(state: AgentState) -> dict:
    """
    根据意图和上下文，生成可执行的任务步骤列表
    """

    tools_desc = describe_all()

    prompt = f"""你是一个任务规划专家。根据用户意图，生成详细的执行步骤。

{state['enriched_context']}

用户意图:
{state['intent']}

要求：
- 每步必须是一个可以立即执行的工具调用
- 第一步通常是读取输入文件或查看目录
- 中间步骤做数据处理和分析
- 最后一步生成产物（报告/文件）
- 如果意图很简单，直接生成回复即可（plan 为空）

请用 JSON 数组格式输出每一步，每步包含:
- "step": 序号(从1开始)
- "action": 工具名(必须从可用工具列表中选择)
- "target": 操作目标(文件名/搜索词等)
- "reason": 为什么需要这一步

只输出 JSON 数组，不要其他文字。例如:
[{{"step": 1, "action": "list_files", "target": "", "reason": "查看工作目录文件"}}]

如果不需要工具就能回答，输出空数组 []。"""

    resp = _call_llm(prompt)

    # 解析 JSON
    try:
        # 清理 LLM 可能输出的多余文字
        resp = resp.strip()
        if resp.startswith("```"):
            resp = resp.split("```")[1]
            if resp.startswith("json"):
                resp = resp[4:]
        plan = json.loads(resp)
    except json.JSONDecodeError:
        plan = []

    print(f"\n{'─'*50}")
    print(f"📝 [Node 3] 任务规划 — 共 {len(plan)} 步")
    print(f"{'─'*50}")
    for p in plan:
        print(f"  Step {p['step']}: {p['action']}({p['target']}) — {p['reason']}")

    return {
        "plan": plan,
        "current_step": 0,
        "retry_count": 0,
    }


# ══════════════════════════════════════════════
#  Node 4: 工具执行
# ══════════════════════════════════════════════

def execute_tool(state: AgentState) -> dict:
    """
    执行 plan[current_step] 指定的工具
    """

    step_idx = state["current_step"]
    if step_idx >= len(state["plan"]):
        return {"current_step": step_idx}

    step = state["plan"][step_idx]
    tool_name = step["action"]
    target = step.get("target", "")

    print(f"\n{'─'*50}")
    print(f"⚡ [Node 4] 执行工具 — Step {step['step']}: {tool_name}({target})")
    print(f"{'─'*50}")

    result = call_tool(tool_name, state, target)

    if result["success"]:
        print(f"  ✅ 成功")
        if result["output"]:
            # 只打印前 500 字符
            output_preview = result["output"][:500]
            if len(result["output"]) > 500:
                output_preview += f"\n  ...(共 {len(result['output'])} 字符，已截断)"
            print(f"  📤 {output_preview}")
    else:
        print(f"  ❌ 失败: {result['output']}")

    new_results = list(state.get("tool_results", []))
    new_results.append(dict(result))

    return {
        "tool_results": new_results,
        "current_step": step_idx + 1,
    }


# ══════════════════════════════════════════════
#  Node 5: 结果校验
# ══════════════════════════════════════════════

def validate_result(state: AgentState) -> dict:
    """
    检查上一步工具执行结果是否有效
    """

    results = state.get("tool_results", [])
    if not results:
        return {"validation_passed": False, "validation_feedback": "没有执行结果"}

    last = results[-1]
    step_idx = state["current_step"] - 1  # 刚执行完的步骤

    # 校验规则
    if not last["success"]:
        return {
            "validation_passed": False,
            "validation_feedback": f"工具执行失败: {last['output']}",
        }

    # 检查输出是否为空
    if not last["output"] or last["output"].strip() == "":
        return {
            "validation_passed": False,
            "validation_feedback": "工具返回了空结果",
        }

    print(f"\n{'─'*50}")
    print(f"🔬 [Node 5] 结果校验 — Step {step_idx+1}")
    print(f"{'─'*50}")
    print(f"  ✅ 校验通过")

    return {
        "validation_passed": True,
        "validation_feedback": "",
    }


# ══════════════════════════════════════════════
#  Node 6: 产物生成
# ══════════════════════════════════════════════

def generate_output(state: AgentState) -> dict:
    """
    汇总所有工具执行结果，让 LLM 生成最终产物
    """

    tools_desc = describe_all()

    # 汇总执行过程
    execution_log = []
    for tr in state.get("tool_results", []):
        status = "✅" if tr["success"] else "❌"
        execution_log.append(f"Step {tr['step']}: {status} {tr['action']} → {tr['output'][:300]}")

    prompt = f"""你是一个报告生成专家。根据以下任务执行记录，生成最终的结果报告。

用户意图:
{state['intent']}

可用工具:
{tools_desc}

执行过程:
{chr(10).join(execution_log)}

请根据实际执行结果，生成一份完整、专业的报告。如果执行过程中得到了数据，请基于数据给出分析结论。
用 Markdown 格式输出。"""

    output = _call_llm(prompt)

    # 保存到文件
    filepath = os.path.join(state["workspace_path"], "output.md")
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(output)

    print(f"\n{'─'*50}")
    print(f"📦 [Node 6] 产物生成")
    print(f"{'─'*50}")
    print(f"  产物已保存: output.md ({len(output)} 字符)")

    return {
        "final_output": output,
        "output_files": [filepath],
        "messages": [AIMessage(content=output)],
    }


# ══════════════════════════════════════════════
#  Node 7: 兜底处理
# ══════════════════════════════════════════════

def handle_error(state: AgentState) -> dict:
    """
    重试超限后的兜底策略：用已有结果尽力生成
    """

    results = state.get("tool_results", [])
    if results:
        print(f"\n{'─'*50}")
        print(f"⚠️ [Node 7] 兜底处理 — 用部分结果生成降级报告")
        print(f"{'─'*50}")
        return generate_output(state)
    else:
        return {
            "final_output": "任务执行失败，未能获取有效结果。请检查输入或重试。",
            "messages": [AIMessage(content="抱歉，任务执行失败。请检查输入或重试。")],
        }

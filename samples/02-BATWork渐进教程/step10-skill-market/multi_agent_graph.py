"""
Multi-Agent LangGraph — Workshop 多智能体显性调度演示

Agent 角色：
- Orchestrator（编排器）：接收任务，决定路由
- Researcher（研究员）：搜索和收集信息
- Analyst（分析师）：数据分析和模式识别
- Writer（写手）：根据研究和分析撰写内容
- Reviewer（审阅官）：审阅输出，决定是修订还是通过

支持两种模式：
- simulated（模拟）：使用静态文本，无需 API Key，适合演示
- llm（真实 LLM）：调用 DeepSeek / OpenAI 等，需要 API Key

图结构：
  Orchestrator
    ├──→ Researcher
    │      └──→ Analyst
    │            └──→ Writer
    │                  └──→ Reviewer ──(需要修订)──→ Writer
    │                        └──(通过)──→ END
    └──→ Writer（简单任务直接写）
"""

from typing import TypedDict, Optional, Any
import logging

from langgraph.graph import StateGraph, END

logger = logging.getLogger(__name__)

# ── Agent 角色定义 ──────────────────────────────────────────

AGENT_ROLES = {
    "orchestrator": {
        "name": "编排器",
        "emoji": "🎯",
        "color": "#7c5cfc",
        "description": "任务接收与路由分发",
    },
    "researcher": {
        "name": "研究员",
        "emoji": "🔍",
        "color": "#3b82f6",
        "description": "信息搜索与收集",
    },
    "analyst": {
        "name": "分析师",
        "emoji": "📊",
        "color": "#f59e0b",
        "description": "数据分析与模式识别",
    },
    "writer": {
        "name": "写手",
        "emoji": "✍️",
        "color": "#22c55e",
        "description": "内容撰写与生成",
    },
    "reviewer": {
        "name": "审阅官",
        "emoji": "🔎",
        "color": "#ef4444",
        "description": "质量审阅与反馈",
    },
}

# ── State ──────────────────────────────────────────────────

class MultiAgentState(TypedDict):
    user_input: str          # 用户输入
    enable_llm: bool         # 是否启用 LLM（True=DeepSeek, False=模拟）
    task_type: str           # 任务类型：research / simple / analysis
    research_result: str     # 研究员产出
    analysis_result: str     # 分析师产出
    draft: str               # 写手草稿
    review_feedback: str     # 审阅反馈
    revision_count: int      # 修订次数
    final_output: str        # 最终输出
    agent_trace: list[dict]  # Agent 执行轨迹
    current_agent: str       # 当前执行 Agent


# ── LLM 调用帮助函数 ───────────────────────────────────────

_llm_instance: Any = None


def set_llm(llm):
    """注入 LLM 实例（由 server.py 初始化时调用）"""
    global _llm_instance
    _llm_instance = llm


def _llm_call(role_prompt: str, user_content: str, enable_llm: bool) -> str:
    """调用 LLM 或返回模拟文本"""
    if not enable_llm or _llm_instance is None:
        return _simulate_response(role_prompt, user_content)

    try:
        from langchain_core.messages import SystemMessage, HumanMessage
        response = _llm_instance.invoke([
            SystemMessage(content=role_prompt),
            HumanMessage(content=user_content),
        ])
        return response.content
    except Exception as e:
        logger.warning(f"LLM 调用失败，fallback 到模拟模式: {e}")
        return _simulate_response(role_prompt, user_content)


def _simulate_response(role_prompt: str, user_content: str) -> str:
    """模拟响应（无 LLM 时的 fallback）"""
    # 从角色 prompt 中提取角色名
    role = "agent"
    for rp in ["分析师", "研究员", "写手", "审阅官", "编排器"]:
        if rp in role_prompt:
            role = rp
            break
    return f"[模拟] {role} 处理中：对「{user_content[:60]}」的分析结果"


# ── Agent 节点函数（LLM 集成版）────────────────────────────

def node_orchestrator(state: MultiAgentState) -> dict[str, Any]:
    """编排器：分析任务类型，决定路由"""
    user_input = state["user_input"]
    enable_llm = state.get("enable_llm", False)
    trace = list(state.get("agent_trace", []))

    # 根据输入判断任务类型
    analysis_keywords = ["分析", "数据", "统计", "报表", "趋势", "对比"]
    research_keywords = ["调研", "搜索", "查找", "了解", "信息", "竞品", "市场"]

    is_analysis = any(kw in user_input for kw in analysis_keywords)
    is_research = any(kw in user_input for kw in research_keywords)

    if is_research or is_analysis:
        task_type = "research"
    else:
        task_type = "simple"

    trace.append({
        "agent": "orchestrator",
        "action": f"任务分析完成，类型: {task_type}",
        "decision": "→ Researcher" if task_type == "research" else "→ Writer",
    })

    return {
        "task_type": task_type,
        "current_agent": "orchestrator",
        "agent_trace": trace,
    }


def node_researcher(state: MultiAgentState) -> dict[str, Any]:
    """研究员：收集和整理信息（LLM 模式时调用真实 API）"""
    user_input = state["user_input"]
    enable_llm = state.get("enable_llm", False)
    trace = list(state.get("agent_trace", []))

    if enable_llm and _llm_instance:
        prompt = """你是信息研究员。针对用户的问题进行深度研究，收集和分析相关信息。
输出格式：用 Markdown 的结构化报告，包含以下部分：
1. **研究概述**: 一句话总结研究方向
2. **关键发现**: 3-5 条核心发现，每条用 bullet point
3. **数据支撑**: 如果有数据相关的分析，给出量化结论
4. **初步建议**: 基于发现的初步建议方向"""
        research = _llm_call(prompt, user_input, enable_llm)
    else:
        keywords = [w for w in user_input.split() if len(w) > 1]
        research = f"""## 研究结果

针对「{user_input}」的研究：

1. **关键概念**: {', '.join(keywords[:5]) if keywords else '待分析'}
2. **信息来源**: 内部知识库 + 公开数据
3. **核心发现**: 
   - 相关数据已收集
   - 关键指标已提取
   - 上下文信息已整理
4. **数据摘要**: 已完成初步信息收集，移交给分析师。"""

    trace.append({
        "agent": "researcher",
        "action": f"完成信息收集",
        "output_size": len(research),
    })

    return {
        "research_result": research,
        "current_agent": "researcher",
        "agent_trace": trace,
    }


def node_analyst(state: MultiAgentState) -> dict[str, Any]:
    """分析师：分析数据，提取洞察"""
    research = state.get("research_result", "")
    user_input = state["user_input"]
    enable_llm = state.get("enable_llm", False)
    trace = list(state.get("agent_trace", []))

    if enable_llm and _llm_instance:
        prompt = """你是数据分析师。基于研究员提供的信息，进行深度分析。
输出格式：
1. **数据概览**: 概述当前数据状态
2. **关键洞察**: 3 个具体洞察，用数据支撑
3. **趋势判断**: 短期和中期趋势
4. **风险提示**: 潜在风险和关注点
5. **移交建议**: 给写手的具体撰写方向建议"""
        analysis_input = f"用户问题: {user_input}\n\n研究结果:\n{research}"
        analysis = _llm_call(prompt, analysis_input, enable_llm)
    else:
        analysis = f"""## 分析报告

基于研究结果的分析：

1. **数据概览**: 输入材料已处理
2. **关键洞察**:
   - 趋势识别：发现 3 个关键模式
   - 异常检测：无显著异常
   - 关联分析：发现 2 组强关联

3. **建议方向**: 
   - 重点关注增长领域
   - 监控风险指标
   - 优化资源分配

4. **输出格式**: 结构化分析报告就绪，移交写手。"""

    trace.append({
        "agent": "analyst",
        "action": "完成数据分析",
        "output_size": len(analysis),
    })

    return {
        "analysis_result": analysis,
        "current_agent": "analyst",
        "agent_trace": trace,
    }


def node_writer(state: MultiAgentState) -> dict[str, Any]:
    """写手：撰写内容"""
    research = state.get("research_result", "")
    analysis = state.get("analysis_result", "")
    user_input = state["user_input"]
    feedback = state.get("review_feedback", "")
    rev_count = state.get("revision_count", 0)
    enable_llm = state.get("enable_llm", False)
    trace = list(state.get("agent_trace", []))

    is_revision = bool(feedback)

    if enable_llm and _llm_instance:
        if is_revision:
            prompt = f"""你是专业写手。根据审阅官反馈修订文稿。
审阅反馈: {feedback}
修订要求: 这是第 {rev_count + 1} 轮修订，请彻底解决反馈中提到的问题。

改写文稿，输出完整版（用 Markdown 格式，包含标题、摘要、正文、建议、结论）。"""
            write_input = f"原始任务: {user_input}\n\n研究材料:\n{research}\n\n分析材料:\n{analysis}"
        else:
            prompt = """你是专业写手。根据研究员和分析师的材料，撰写一份完整的综合报告。
输出格式（Markdown）:
## {任务标题}
### 摘要
### 背景与分析
### 核心发现
### 建议方案（短期/中期/长期）
### 结论

要求：专业、具体、有数据支撑。"""
            write_input = f"任务: {user_input}\n\n研究材料:\n{research}\n\n分析材料:\n{analysis}"
        draft = _llm_call(prompt, write_input, enable_llm)
    else:
        if is_revision:
            draft = f"""## 修订稿 (第 {rev_count + 1} 轮)

根据审阅反馈「{feedback}」修订：

针对「{user_input}」的综合报告：

### 核心内容
- 基于研究材料的深度分析
- 关键发现与数据支撑的结论
- 具体可执行的建议方案

### 修订说明
- ✅ 已根据反馈调整内容结构
- ✅ 补充了数据分析深度
- ✅ 优化了表达清晰度

---
*生成时间: 多智能体协作（模拟模式）*"""
        else:
            draft = f"""## {user_input} - 综合报告

### 摘要
针对「{user_input}」的完整分析和建议。

### 研究背景
{research[:200]}

### 分析洞察
{analysis[:200] if analysis else '基于直接输入的分析'}

### 建议方案
1. **短期行动**: 基于当前数据的最优决策
2. **中期规划**: 3-6 个月的优化路径
3. **长期战略**: 可持续发展的建议

### 结论
综合以上分析，建议优先关注核心指标变化，及时调整策略。

---
*由 Multi-Agent 协作生成（模拟模式）*"""

    trace.append({
        "agent": "writer",
        "action": "修订草稿" if is_revision else "撰写初稿",
        "revision": is_revision,
        "output_size": len(draft),
    })

    return {
        "draft": draft,
        "current_agent": "writer",
        "agent_trace": trace,
    }


def node_reviewer(state: MultiAgentState) -> dict[str, Any]:
    """审阅官：质量检查"""
    draft = state.get("draft", "")
    user_input = state["user_input"]
    rev_count = state.get("revision_count", 0)
    enable_llm = state.get("enable_llm", False)
    trace = list(state.get("agent_trace", []))

    if enable_llm and _llm_instance:
        prompt = """你是质量审阅官。审阅写手的文稿，判断是否需要修订。
输出格式（严格按以下格式）:
评分: [1-100的数字]
需要修订: [是/否]
反馈: [如果需要修订，给出具体的修订建议；如果通过，写"通过"]
摘要: [一句话点评]"""
        review_input = f"任务: {user_input}\n\n文稿:\n{draft}"
        review_result = _llm_call(prompt, review_input, enable_llm)

        # 解析 LLM 输出
        score = 70  # default
        needs_revision = True
        feedback = "请进一步增强内容深度和数据支撑"

        for line in review_result.split("\n"):
            line = line.strip()
            if line.startswith("评分:"):
                try:
                    score = int(''.join(c for c in line if c.isdigit()))
                except ValueError:
                    pass
            elif line.startswith("需要修订:"):
                needs_revision = "是" in line
            elif line.startswith("反馈:"):
                feedback = line.replace("反馈:", "").strip()
    else:
        # 模拟评分逻辑
        score = min(50 + rev_count * 25, 95)
        needs_revision = score < 80
        feedback = "请补充更多数据支撑，增强结论的说服力"

    if needs_revision:
        trace.append({
            "agent": "reviewer",
            "action": f"质量评分 {score}/100，需要修订",
            "feedback": feedback,
        })
        return {
            "review_feedback": feedback,
            "revision_count": rev_count + 1,
            "current_agent": "reviewer",
            "agent_trace": trace,
        }
    else:
        trace.append({
            "agent": "reviewer",
            "action": f"质量评分 {score}/100，通过审阅 ✅",
            "approved": True,
        })
        return {
            "review_feedback": "",
            "final_output": draft,
            "current_agent": "reviewer",
            "agent_trace": trace,
        }


# ── 路由函数 ────────────────────────────────────────────────

def route_after_orchestrator(state: MultiAgentState) -> str:
    """编排后路由：研究任务 → Researcher，简单任务 → Writer"""
    if state.get("task_type") == "research":
        return "researcher"
    return "writer"


def route_after_researcher(state: MultiAgentState) -> str:
    """研究后总是进入分析"""
    return "analyst"


def route_after_analyst(state: MultiAgentState) -> str:
    """分析后总是进入撰写"""
    return "writer"


def route_after_reviewer(state: MultiAgentState) -> str:
    """审阅后路由：需要修订 → Writer，通过 → END"""
    if state.get("review_feedback"):
        return "writer"
    return END


# ── 构建图 ──────────────────────────────────────────────────

def build_multi_agent_graph(llm=None) -> Any:
    """
    构建多智能体协作图

    Args:
        llm: LangChain ChatModel 实例（可选，用于 LLM 模式）

    图结构:
        Orchestrator ──(research)──→ Researcher → Analyst → Writer
              │                                                    ↑
              └──(simple)──→ Writer ──→ Reviewer ──(修订)─────┘
                                            └──(通过)──→ END
    """
    # 注入 LLM（如有）
    if llm:
        set_llm(llm)

    graph = StateGraph(MultiAgentState)

    # 添加节点
    graph.add_node("orchestrator", node_orchestrator)
    graph.add_node("researcher", node_researcher)
    graph.add_node("analyst", node_analyst)
    graph.add_node("writer", node_writer)
    graph.add_node("reviewer", node_reviewer)

    # 设置入口
    graph.set_entry_point("orchestrator")

    # 添加条件边
    graph.add_conditional_edges("orchestrator", route_after_orchestrator, {
        "researcher": "researcher",
        "writer": "writer",
    })
    graph.add_edge("researcher", "analyst")
    graph.add_edge("analyst", "writer")
    graph.add_edge("writer", "reviewer")
    graph.add_conditional_edges("reviewer", route_after_reviewer, {
        "writer": "writer",
        END: END,
    })

    return graph.compile()


def get_graph_definition() -> dict[str, Any]:
    """返回图的结构定义（供前端可视化使用）"""
    return {
        "nodes": [
            {
                "id": "orchestrator",
                "label": "编排器",
                "emoji": "🎯",
                "color": "#7c5cfc",
                "x": 400, "y": 60,
                "description": "任务接收与路由分发",
            },
            {
                "id": "researcher",
                "label": "研究员",
                "emoji": "🔍",
                "color": "#3b82f6",
                "x": 150, "y": 220,
                "description": "信息搜索与收集",
            },
            {
                "id": "analyst",
                "label": "分析师",
                "emoji": "📊",
                "color": "#f59e0b",
                "x": 400, "y": 220,
                "description": "数据分析与模式识别",
            },
            {
                "id": "writer",
                "label": "写手",
                "emoji": "✍️",
                "color": "#22c55e",
                "x": 650, "y": 220,
                "description": "内容撰写与生成",
            },
            {
                "id": "reviewer",
                "label": "审阅官",
                "emoji": "🔎",
                "color": "#ef4444",
                "x": 400, "y": 400,
                "description": "质量审阅与反馈",
            },
        ],
        "edges": [
            {"from": "orchestrator", "to": "researcher", "label": "研究任务"},
            {"from": "orchestrator", "to": "writer", "label": "简单任务"},
            {"from": "researcher", "to": "analyst", "label": "移交分析"},
            {"from": "analyst", "to": "writer", "label": "移交撰写"},
            {"from": "writer", "to": "reviewer", "label": "提交审阅"},
            {"from": "reviewer", "to": "writer", "label": "需修订"},
            {"from": "reviewer", "to": "end", "label": "通过✅"},
        ],
    }

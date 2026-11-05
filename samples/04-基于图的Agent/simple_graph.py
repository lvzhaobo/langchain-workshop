"""
最简单的 LangGraph 线性流水线
流程：计划节点 → 写作节点 → 润色节点 → END

运行模式（自动检测，优先级从高到低）：
  1. 百炼 API（阿里云百炼平台，推荐）
     export DASHSCOPE_API_KEY="sk-..."
     python simple_graph.py

  2. OpenAI API
     export OPENAI_API_KEY="sk-..."
     python simple_graph.py

  3. Mock 模式（无 API Key 时自动启用，演示图流转）
     python simple_graph.py
"""

import os
from typing import TypedDict
from langgraph.graph import StateGraph, END


# ============================================================
# Step 0: 检测 API Key，决定用哪个 LLM
# ============================================================
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if DASHSCOPE_API_KEY:
    from langchain_openai import ChatOpenAI
    llm = ChatOpenAI(
        model="qwen-plus",                   # 百炼模型：qwen-turbo / qwen-plus / qwen-max
        api_key=DASHSCOPE_API_KEY,
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        temperature=0.7,
    )
    MODE = "🟢 百炼模式（Qwen-Plus）"

elif OPENAI_API_KEY:
    from langchain_openai import ChatOpenAI
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.7)
    MODE = "🟢 OpenAI 模式（GPT-4o-mini）"

else:
    llm = None
    MODE = "🟡 Mock 模式（无 API Key，使用模拟数据演示图流转）"

HAS_LLM = llm is not None


# ============================================================
# Step 1: 定义状态 — 图中流转的数据结构
# ============================================================
class ArticleState(TypedDict):
    topic: str      # 输入：写作主题
    plan: str       # 计划节点的产出
    draft: str      # 写作节点的产出
    final: str      # 润色节点的产出


# ============================================================
# Step 2: 实现三个节点
# ============================================================

def planner_node(state: ArticleState) -> dict:
    """节点1：根据主题生成写作大纲"""
    topic = state["topic"]
    print(f"\n🔵 [计划节点] 开始... 主题: {topic}")

    if HAS_LLM:
        prompt = f'请为主题「{topic}」生成一个 3 段式的写作大纲，每段一句话。直接输出大纲，不要废话。'
        plan = llm.invoke(prompt).content
    else:
        # Mock：模拟 LLM 输出
        plan = (
            f"1. 引言段：阐述「{topic}」的背景与核心问题\n"
            f"2. 主体段：分析关键技术趋势与实践案例\n"
            f"3. 结论段：展望未来发展方向与潜在挑战"
        )

    print(f"✅ [计划节点] 完成，大纲长度: {len(plan)} 字")
    return {"plan": plan}


def writer_node(state: ArticleState) -> dict:
    """节点2：根据大纲撰写正文"""
    print(f"\n🟢 [写作节点] 开始...")

    if HAS_LLM:
        prompt = f'根据以下大纲写一篇 300 字左右的短文，语言流畅自然：\n\n{state["plan"]}'
        draft = llm.invoke(prompt).content
    else:
        # Mock：模拟根据大纲生成的草稿
        draft = (
            f"随着人工智能技术的飞速发展，{state['topic']}正在成为业界关注的焦点。"
            f"传统的软件开发模式面临着效率瓶颈，而 AI Agent 的出现为行业带来了全新的可能性。"
            f"从需求分析到代码生成，从测试到运维，Agent 正在重新定义开发者的工作方式。\n\n"
            f"在实际应用中，基于大语言模型的 Agent 能够理解自然语言指令，"
            f"自主规划任务步骤，调用工具链完成复杂工程操作。"
            f"一些领先企业已经将 Agent 集成到 CI/CD 流水线中，实现了代码审查、"
            f"Bug 修复等环节的自动化，显著缩短了交付周期。\n\n"
            f"展望未来，Agent 将从辅助工具逐步演进为自主开发实体，"
            f"具备更强的推理能力和上下文理解能力。然而，可靠性、安全性以及"
            f"与现有人类工作流的融合仍然是需要持续攻克的挑战。"
        )

    print(f"✅ [写作节点] 完成，草稿长度: {len(draft)} 字")
    return {"draft": draft}


def polisher_node(state: ArticleState) -> dict:
    """节点3：润色正文"""
    print(f"\n🟡 [润色节点] 开始...")

    if HAS_LLM:
        prompt = f'请润色以下文章，修正语法和用词，使其更加优美，不要改变原意：\n\n{state["draft"]}'
        final = llm.invoke(prompt).content
    else:
        # Mock：模拟润色（加个前缀标识）
        final = (
            f"【润色版】\n\n"
            f"{state['draft']}\n\n"
            f"── 以上内容经过语法修正和用词优化 ✅"
        )

    print(f"✅ [润色节点] 完成，终稿长度: {len(final)} 字")
    return {"final": final}


# ============================================================
# Step 3: 构建图
# ============================================================
builder = StateGraph(ArticleState)

# 添加节点
builder.add_node("planner", planner_node)
builder.add_node("writer", writer_node)
builder.add_node("polisher", polisher_node)

# 连接边 — 定义流转顺序
builder.set_entry_point("planner")          # 入口：planner
builder.add_edge("planner", "writer")       # planner → writer
builder.add_edge("writer", "polisher")      # writer → polisher
builder.add_edge("polisher", END)           # polisher → 结束

# ============================================================
# Step 4: 编译 & 运行
# ============================================================
app = builder.compile()

if __name__ == "__main__":
    print("=" * 60)
    print(f"🚀 启动图 Agent — 线性流水线   [{MODE}]")
    print("=" * 60)
    print()
    print("图结构（DAG）：")
    print("  [planner] ──→ [writer] ──→ [polisher] ──→ END")
    print()

    topic = "AI Agent 如何改变软件开发的未来"
    print(f"📝 输入主题：{topic}")
    print()

    result = app.invoke({"topic": topic})

    print("\n" + "=" * 60)
    print("📄 最终输出")
    print("=" * 60)
    print(result["final"])

    print("\n" + "=" * 60)
    print("📊 状态全追踪（四个字段的流转过程）")
    print("=" * 60)
    for key, value in result.items():
        preview = value[:100].replace("\n", "\\n") + ("..." if len(value) > 100 else "")
        print(f"  [{key}]")
        print(f"    {preview}")
        print()

    # 额外：展示图的关键信息
    print("=" * 60)
    print("🔍 图结构信息")
    print("=" * 60)
    graph_info = app.get_graph()
    print(f"  节点数: {len(graph_info.nodes)}")
    for node_name, node_data in graph_info.nodes.items():
        print(f"    - {node_name}")
    print(f"  边数: {len(graph_info.edges)}")
    for edge in graph_info.edges:
        print(f"    - {edge.source} → {edge.target}")

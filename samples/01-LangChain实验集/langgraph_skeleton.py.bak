"""
Lab 7.5 — LangGraph 多 Agent 骨架代码

学员需要完成的内容：
  1. 定义 AgentState（工作流状态）
  2. 实现 4 个节点函数（Router、Diagnosis、Solution、Execute）
  3. 组装 StateGraph 并添加条件路由
  4. 用 stream 观察逐节点执行过程

运行方式：
  python langgraph_skeleton.py
"""

import json
import os
from pathlib import Path
from typing import TypedDict, List, Optional

from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END

# ---------------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------------
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "你的百炼 API Key")
DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
MODEL = "qwen-plus"

DATA_DIR = Path(__file__).parent


# ---------------------------------------------------------------------------
# 状态定义
# ---------------------------------------------------------------------------

class AgentState(TypedDict):
    """工作流全局状态——在各个节点之间传递的数据结构"""
    # 输入
    user_query: str

    # Router 节点产出
    intent: str                    # diagnosis | inquiry | inspection | unknown
    device_id: Optional[str]
    symptom: Optional[str]

    # Diagnosis 节点产出
    device_info: Optional[str]     # 设备基本信息（JSON）
    diagnosis_result: Optional[str]  # 诊断结论
    severity: Optional[str]        # normal | warning | critical

    # Solution 节点产出
    solution: Optional[str]        # 处置方案

    # Execute 节点产出
    execution_result: Optional[str]  # 执行结果

    # 全局
    messages: List[str]            # 执行日志


# ---------------------------------------------------------------------------
# 数据加载
# ---------------------------------------------------------------------------

def load_equipment_data():
    with open(DATA_DIR / "equipment_data.json", "r", encoding="utf-8") as f:
        return json.load(f)


def load_knowledge_base():
    with open(DATA_DIR / "knowledge_base.json", "r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# 节点函数
# ---------------------------------------------------------------------------

def router_node(state: AgentState) -> AgentState:
    """节点 1：Router — 意图识别 + 参数提取

    分析用户输入，提取设备编号和故障现象，判断处理意图。
    """
    # ===================================================================
    # TODO: 实现 Router 节点
    # 提示：
    #   1. 用 LLM 分析 user_query，提取设备编号和故障现象
    #   2. 判断意图：diagnosis（故障诊断）、inquiry（信息查询）、inspection（巡检）、unknown
    #   3. 记录执行日志到 messages
    #   4. 返回更新后的 state
    # ===================================================================
    pass


def diagnosis_node(state: AgentState) -> AgentState:
    """节点 2：Diagnosis — 故障诊断

    根据设备编号和故障现象，查询设备信息和知识库，给出诊断结论。
    """
    # ===================================================================
    # TODO: 实现 Diagnosis 节点
    # 提示：
    #   1. 用 device_id 查设备数据
    #   2. 用 symptom 查知识库中相关文档
    #   3. 用 LLM 综合判断严重程度（normal / warning / critical）
    #   4. 记录日志
    # ===================================================================
    pass


def solution_node(state: AgentState) -> AgentState:
    """节点 3：Solution — 方案生成

    根据诊断结论，生成处置方案。
    """
    # ===================================================================
    # TODO: 实现 Solution 节点
    # 提示：
    #   1. 根据 severity 和 diagnosis_result 生成处置方案
    #   2. critical 级别的方案要包含紧急停机和上报步骤
    #   3. warning 级别要包含检查和观察建议
    #   4. normal 级别只需记录
    # ===================================================================
    pass


def execute_node(state: AgentState) -> AgentState:
    """节点 4：Execute — 执行/记录

    模拟执行处置方案，生成巡检记录。
    """
    # ===================================================================
    # TODO: 实现 Execute 节点
    # 提示：
    #   1. 将诊断结论和处置方案汇总
    #   2. 生成一条巡检记录（JSON 格式），包含时间、设备、问题、处置、结果
    #   3. 记录执行日志
    # ===================================================================
    pass


def fallback_node(state: AgentState) -> AgentState:
    """兜底节点：意图不明时的处理"""
    state["messages"].append("⚠️ 无法识别用户意图，请提供更详细的信息")
    state["intent"] = "unknown"
    return state


# ---------------------------------------------------------------------------
# 条件函数
# ---------------------------------------------------------------------------

def route_by_intent(state: AgentState) -> str:
    """根据意图路由到不同节点"""
    # ===================================================================
    # TODO: 实现意图路由
    # 返回节点名：
    #   intent == "diagnosis" → "diagnosis"
    #   intent == "inquiry"   → "solution"（跳过诊断）
    #   intent == "inspection"→ "execute"（直接执行巡检）
    #   其他                    → "fallback"
    # ===================================================================
    pass


def route_by_severity(state: AgentState) -> str:
    """根据严重程度决定后续路径"""
    # ===================================================================
    # TODO: 实现严重程度路由
    #   severity == "critical" → "solution"（直接生成紧急方案）
    #   severity == "warning"  → "solution"
    #   severity == "normal"   → "execute"（跳过方案生成，直接记录）
    # ===================================================================
    pass


# ---------------------------------------------------------------------------
# 图构建
# ---------------------------------------------------------------------------

def build_graph():
    """组装 StateGraph"""
    # ===================================================================
    # TODO: 构建工作流图
    #
    # 图结构：
    #   START → router → [条件：route_by_intent]
    #     ├── diagnosis → [条件：route_by_severity]
    #     │     ├── solution → execute → END
    #     │     └── execute → END
    #     ├── solution → execute → END
    #     ├── execute → END
    #     └── fallback → END
    #
    # 提示：
    #   workflow = StateGraph(AgentState)
    #   workflow.add_node("router", router_node)
    #   workflow.add_node("diagnosis", diagnosis_node)
    #   ...
    #   workflow.set_entry_point("router")
    #   workflow.add_conditional_edges("router", route_by_intent, {
    #       "diagnosis": "diagnosis",
    #       "inquiry": "solution",
    #       ...
    #   })
    #   ...
    #   graph = workflow.compile()
    # ===================================================================
    pass


# ---------------------------------------------------------------------------
# 可视化与验证
# ---------------------------------------------------------------------------

def stream_graph(graph, user_query: str):
    """用 stream 观察图的逐节点执行过程"""
    # ===================================================================
    # TODO: 实现 stream 观察
    #
    # for event in graph.stream({"user_query": user_query, "messages": []}):
    #     for node_name, node_output in event.items():
    #         print(f"\n📍 节点 [{node_name}] 执行完成")
    #         # 打印该节点的关键输出
    #
    # 观察点：
    #   - 每个节点的输入输出是什么？
    #   - 条件路由选择了哪条路径？
    #   - 状态在各个节点间如何传递？
    # ===================================================================
    pass


def compare_graph_vs_agent(graph, user_query: str):
    """对比：StateGraph 编排 vs 单 Agent"""
    # ===================================================================
    # TODO（选做）: 用同一个任务，对比 StateGraph 和 create_react_agent
    # 观察：
    #   - StateGraph 的执行路径是确定的（你定义的图结构）
    #   - ReAct Agent 的执行路径是动态的（AI 自己决定）
    #   - 哪种方式更适合需要审批/合规的场景？
    # ===================================================================
    pass


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 50)
    print("Lab 7.5 — LangGraph 多 Agent 骨架")
    print("=" * 50)

    if DASHSCOPE_API_KEY == "你的百炼 API Key":
        print("\n⚠️  请先设置环境变量 DASHSCOPE_API_KEY")
        exit(1)

    # TODO: 完成上述函数后，取消以下注释来测试
    # print("\n🔨 构建工作流图...")
    # graph = build_graph()
    # print("   图构建完成")

    # print("\n📊 测试 Stream...")
    # stream_graph(graph, "EP-D-002 的断路器拒分了，需要紧急处理")

    # print("\n🔄 测试另一个路径...")
    # stream_graph(graph, "帮我查一下天河区有几台变压器")

    print("\n👆 请完成代码中的 TODO 部分，然后取消 main 中的注释来运行")

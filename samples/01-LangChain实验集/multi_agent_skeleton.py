"""
Lab 7.5b — 多 Agent 协作骨架代码

三个专业 Agent + 一个 Supervisor 调度中心：
  - Diagnosis Agent（诊断专家）：查设备、查知识库，给出诊断结论
  - Solution Agent（方案专家）：根据诊断结论生成处置方案
  - Execute Agent（执行专家）：记录巡检、推送通知
  - Supervisor：看 State → 决定调谁 → 收结果 → 再决定 → 直到完成

学员需要完成的内容：
  1. 每个 Agent 的工具函数
  2. Supervisor 的调度逻辑
  3. 状态共享和 Agent 间数据流
  4. 并行分发（Send API）

运行方式：
  python multi_agent_skeleton.py
"""

import json
import os
from pathlib import Path
from typing import TypedDict, List, Optional, Literal

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
# 数据加载
# ---------------------------------------------------------------------------

def load_equipment_data():
    with open(DATA_DIR / "equipment_data.json", "r", encoding="utf-8") as f:
        return json.load(f)


def load_knowledge_base():
    with open(DATA_DIR / "knowledge_base.json", "r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# 共享状态（所有 Agent 读写同一份）
# ---------------------------------------------------------------------------

class MultiAgentState(TypedDict):
    """多 Agent 共享状态

    设计要点：
    - 每个 Agent 只读写自己负责的字段
    - Supervisor 读所有字段，决定路由
    - 字段命名要能看出是哪个 Agent 的产出
    """
    # 输入
    user_query: str

    # Diagnosis Agent 的产出
    device_id: Optional[str]
    device_info: Optional[str]
    diagnosis_result: Optional[str]
    severity: Optional[str]       # normal | warning | critical
    related_procedures: Optional[List[str]]

    # Solution Agent 的产出
    solution_plan: Optional[str]
    alert_sent: Optional[bool]

    # Execute Agent 的产出
    execution_record: Optional[str]
    notification_sent: Optional[bool]

    # Supervisor 调度用
    next_agent: str               # 下一个要执行的 Agent 名
    task_history: List[str]        # 已执行的 Agent 列表
    final_answer: Optional[str]    # 最终汇总答案


# =======================================================================
# 工具定义：每个 Agent 有自己专用的工具
# =======================================================================

from langchain_core.tools import tool


# ---- Diagnosis Agent 的工具 ----

@tool
def search_equipment_by_id(device_id: str) -> str:
    """根据设备编号查找设备详细信息。Diagnosis Agent 专用工具。

    参数:
        device_id: 设备编号，如 EP-B-001
    """
    # ===================================================================
    # TODO: 实现设备查找
    # ===================================================================
    pass


@tool
def search_knowledge_base(symptom: str) -> str:
    """根据故障现象搜索知识库中的相关技术文档。Diagnosis Agent 专用工具。

    参数:
        symptom: 故障现象描述
    """
    # ===================================================================
    # TODO: 实现知识库搜索
    # ===================================================================
    pass


# ---- Solution Agent 的工具 ----

@tool
def generate_repair_plan(diagnosis: str, severity: str, device_name: str) -> str:
    """根据诊断结论生成处置方案。Solution Agent 专用工具。

    参数:
        diagnosis: 诊断结论
        severity: 严重程度
        device_name: 设备名称
    """
    # ===================================================================
    # TODO: 用 LLM 生成处置方案
    # ===================================================================
    pass


@tool
def send_alert(device_name: str, severity: str, content: str) -> str:
    """发送告警通知。Solution Agent 专用工具。

    参数:
        device_name: 设备名称
        severity: 严重程度
        content: 告警内容
    """
    # ===================================================================
    # TODO: 模拟发送告警（打印到终端即可）
    # ===================================================================
    pass


# ---- Execute Agent 的工具 ----

@tool
def create_inspection_record(device_id: str, result: str, actions: str) -> str:
    """创建巡检记录。Execute Agent 专用工具。

    参数:
        device_id: 设备编号
        result: 巡检结果
        actions: 已执行的处置措施
    """
    # ===================================================================
    # TODO: 生成巡检记录 JSON
    # ===================================================================
    pass


@tool
def push_notification(target: str, message: str) -> str:
    """推送通知。Execute Agent 专用工具。

    参数:
        target: 推送目标（如 飞书、短信）
        message: 推送内容
    """
    # ===================================================================
    # TODO: 模拟推送通知
    # ===================================================================
    pass


# =======================================================================
# Agent 节点：每个节点是一个有专属 System Prompt 和 Tool 的 Agent
# =======================================================================

def diagnosis_agent_node(state: MultiAgentState) -> MultiAgentState:
    """Diagnosis Agent — 诊断专家

    职责：根据用户描述的设备故障，查设备信息和知识库，给出诊断结论。
    专属工具：search_equipment_by_id、search_knowledge_base
    """
    # ===================================================================
    # TODO: 实现 Diagnosis Agent
    # 1. 如果你的 LangGraph 版本支持 ToolNode，可以用 ToolNode + LLM
    # 2. 如果不支持，可以直接用 LLM.invoke 模拟 Agent 行为
    #    关键是用 Agent 专属的 System Prompt
    #
    # System Prompt 示例：
    #   "你是电力设备故障诊断专家。你可以使用 search_equipment_by_id
    #    查找设备信息，使用 search_knowledge_base 查找相关技术文档。
    #    请根据用户描述给出：1)设备当前状态 2)可能原因 3)严重程度。"
    # ===================================================================
    pass


def solution_agent_node(state: MultiAgentState) -> MultiAgentState:
    """Solution Agent — 方案专家

    职责：根据 Diagnosis Agent 的诊断结论，生成处置方案。
    专属工具：generate_repair_plan、send_alert
    """
    # ===================================================================
    # TODO: 实现 Solution Agent
    # 关键：这个 Agent 不需要重新诊断，它从 state 中读 diagnosis_result
    # ===================================================================
    pass


def execute_agent_node(state: MultiAgentState) -> MultiAgentState:
    """Execute Agent — 执行专家

    职责：记录巡检结果、推送通知。
    专属工具：create_inspection_record、push_notification
    """
    # ===================================================================
    # TODO: 实现 Execute Agent
    # ===================================================================
    pass


# =======================================================================
# Supervisor 调度中心
# =======================================================================

def supervisor_node(state: MultiAgentState) -> MultiAgentState:
    """Supervisor — 调度中心

    职责：读取当前 State，决定下一步调用哪个 Agent。
    这是多 Agent 协作的核心：一个 LLM 负责调度，而不是硬编码的 if-else。

    调度逻辑：
    1. 如果还没有诊断结果 → 调 Diagnosis Agent
    2. 如果诊断已完成但还没有处置方案 → 调 Solution Agent
    3. 如果方案已生成但还没有执行 → 调 Execute Agent
    4. 如果全部完成 → FINISH
    """
    # ===================================================================
    # TODO: 实现 Supervisor
    #
    # 方式 A（简单）：硬编码规则
    #   if not state.get("diagnosis_result"):
    #       state["next_agent"] = "diagnosis_agent"
    #   elif not state.get("solution_plan"):
    #       state["next_agent"] = "solution_agent"
    #   elif not state.get("execution_record"):
    #       state["next_agent"] = "execute_agent"
    #   else:
    #       state["next_agent"] = "FINISH"
    #
    # 方式 B（进阶）：用 LLM 做调度决策
    #   把 State 摘要发给 LLM，让它决定下一步。
    #   这是更真实的 Supervisor 模式——有新 Agent 加入时不需要改规则。
    # ===================================================================
    pass


def summarize_node(state: MultiAgentState) -> MultiAgentState:
    """汇总节点：把所有 Agent 的产出汇总为最终答案"""
    # ===================================================================
    # TODO: 汇总所有 Agent 的结果
    # ===================================================================
    pass


# =======================================================================
# 路由函数
# =======================================================================

def route_to_agent(state: MultiAgentState) -> str:
    """Supervisor 决策后的路由"""
    # ===================================================================
    # TODO: 返回 state["next_agent"]，如果是 FINISH 则返回 "summarize"
    # ===================================================================
    pass


# =======================================================================
# 图构建：Supervisor 模式
# =======================================================================

def build_multi_agent_graph():
    """构建 Supervisor 模式的多 Agent 工作流

    图结构：
                        ┌──────────────┐
                        │  Supervisor  │ ← 调度中心
                        └──────┬───────┘
               ┌───────────────┼───────────────┐
               ▼               ▼               ▼
        ┌────────────┐ ┌────────────┐ ┌────────────┐
        │ Diagnosis  │ │ Solution   │ │ Execute    │
        │ Agent      │ │ Agent      │ │ Agent      │
        └────────────┘ └────────────┘ └────────────┘
               │               │               │
               └───────────────┼───────────────┘
                               │
                        ┌──────▼──────┐
                        │  Summarize  │
                        └─────────────┘

    关键：每个 Agent 执行完后回到 Supervisor，而不是直线前进。
    这样 Supervisor 可以根据 Agent 的返回结果动态调整策略。
    """
    # ===================================================================
    # TODO: 组装多 Agent 图
    #
    # 1. 创建 StateGraph(MultiAgentState)
    # 2. 添加所有节点：supervisor、diagnosis_agent、solution_agent、execute_agent、summarize
    # 3. 添加条件边：supervisor → route_to_agent → 各 Agent
    # 4. 每个 Agent 执行完 → 回到 supervisor（形成循环）
    # 5. FINISH → summarize → END
    # ===================================================================
    pass


# =======================================================================
# 状态共享验证
# =======================================================================

def verify_state_sharing(graph):
    """验证 Agent 间状态共享

    1. 跑一个完整的故障诊断流程
    2. 检查 Diagnosis Agent 写入的 diagnosis_result
       Solution Agent 是否能读到
    3. 检查 Execute Agent 写入的 execution_record
       是否包含了前两个 Agent 的信息
    """
    # ===================================================================
    # TODO: 验证状态共享
    #
    # 验证点：
    # - Solution Agent 的输入是否包含 Diagnosis Agent 的诊断结论？
    # - Execute Agent 的记录是否汇总了诊断和处置信息？
    # ===================================================================
    pass


# =======================================================================
# 并行分发验证（选做）
# =======================================================================

def verify_parallel_dispatch():
    """验证 Send API 并行分发

    场景：用户说"帮我查一下 EP-B-001 和 EP-D-002 的状态"
    Supervisor 可以同时向两个 Diagnosis Agent 实例分发任务。

    提示：使用 langgraph.types.Send
    """
    # ===================================================================
    # TODO（选做）: 实现并行分发
    # ===================================================================
    pass


# =======================================================================
# 主入口
# =======================================================================

if __name__ == "__main__":
    print("=" * 50)
    print("Lab 7.5b — 多 Agent 协作骨架")
    print("=" * 50)

    if DASHSCOPE_API_KEY == "你的百炼 API Key":
        print("\n⚠️  请先设置环境变量 DASHSCOPE_API_KEY")
        exit(1)

    # TODO: 完成上述函数后，取消以下注释来测试
    # print("\n🔨 构建多 Agent 工作流...")
    # graph = build_multi_agent_graph()

    # print("\n🚀 运行诊断流程...")
    # result = graph.invoke({
    #     "user_query": "EP-D-002 断路器拒分，操作电源正常但分闸失败，需要紧急处理",
    #     "task_history": [],
    # })

    # print("\n📋 Agent 调度历史:")
    # for step in result.get("task_history", []):
    #     print(f"  → {step}")

    # print(f"\n🔍 Diagnosis Agent 诊断结论:")
    # print(f"  {result.get('diagnosis_result', 'N/A')}")

    # print(f"\n📝 Solution Agent 处置方案:")
    # print(f"  {result.get('solution_plan', 'N/A')}")

    # print(f"\n✅ Execute Agent 执行记录:")
    # print(f"  {result.get('execution_record', 'N/A')}")

    # print(f"\n📊 最终汇总:")
    # print(f"  {result.get('final_answer', 'N/A')}")

    # verify_state_sharing(graph)

    print("\n👆 请完成代码中的 TODO 部分，然后取消 main 中的注释来运行")

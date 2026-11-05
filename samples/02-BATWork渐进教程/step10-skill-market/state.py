"""
AgentState — LangGraph 图中流动的共享状态

每个节点读写同一个 AgentState，LangGraph 通过 Checkpointer
自动持久化，支持跨多次对话延续同一个 Task。

Step 5 新增：matched_skill 字段，保存匹配到的 Skill 信息
"""

from typing import TypedDict, Annotated, List, Optional, Any
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage


class ToolResult(TypedDict):
    step: int          # 执行到第几步
    action: str        # 调用的工具名
    success: bool      # 是否成功
    output: str        # 执行输出


class PlanStep(TypedDict):
    step: int          # 步骤序号
    action: str        # 要执行的动作（工具名）
    target: str        # 操作目标（文件名/搜索词等）
    reason: str        # 为什么需要这一步


class AgentState(TypedDict):
    # ── 用户输入 ──
    user_input: str                     # 用户原始输入
    workspace_path: str                 # 当前工作目录
    session_id: str                     # 会话 ID（用于 Memory 持久化）

    # ── 上下文 ──
    intent: str                         # 解析后的意图
    enriched_context: str               # 补齐后的上下文（文件列表、Memory 召回、Skill 匹配等）
    matched_skill: Optional[dict]       # Step 5 新增：匹配到的 Skill 信息 {name, triggers, steps, constraints}

    # ── 规划 ──
    plan: List[dict]                    # 任务步骤列表，每项含 step/action/target/reason
    current_step: int                   # 当前执行到第几步

    # ── 消息历史（add_messages reducer 自动合并） ──
    messages: Annotated[List[BaseMessage], add_messages]

    # ── 执行 ──
    tool_results: List[dict]            # 工具执行结果列表

    # ── 校验 ──
    validation_passed: bool             # 上一步校验是否通过
    validation_feedback: str            # 校验反馈
    retry_count: int                    # 当前步骤重试次数

    # ── 产出 ──
    final_output: str                   # 最终产物内容
    output_files: List[str]             # 产出的文件路径

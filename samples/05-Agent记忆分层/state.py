"""
LangGraph 三层记忆的状态定义

State 包含三个记忆层的数据：
- messages:         短期记忆（当前对话），由 add_messages Reducer 自动管理
- memory_context:   从长期记忆注入的上下文（注入到 SystemMessage）
- memory_blocks:    记忆块 {persona, human, long_term, today_notes}
- user_profile:     当前用户画像缓存
- profile_delta:    本轮检测到的画像变更（待写入 Store）
- session_meta:     会话元信息 {user_id, session_id, started_at}
"""

from typing import TypedDict, Annotated, Optional, Any
from datetime import datetime

from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage
from pydantic import BaseModel, Field


# ═══════════════════════════════════════════════════════════
# Graph State（图上流转的状态）
# ═══════════════════════════════════════════════════════════

class MemoryAgentState(TypedDict):
    """三层记忆的完整 Graph State"""

    # ── 短期记忆：由 add_messages Reducer 自动追加（不覆盖）──
    messages: Annotated[list[BaseMessage], add_messages]

    # ── 从长期记忆注入的上下文 ──
    memory_context: str
    memory_blocks: dict

    # ── 用户画像 ──
    user_profile: dict
    profile_delta: Optional[dict]

    # ── 会话元信息 ──
    session_meta: dict
    compaction_count: int
    pending_consolidation: bool


# ═══════════════════════════════════════════════════════════
# Store 中存储的数据模型（Pydantic，用于验证）
# ═══════════════════════════════════════════════════════════

class UserTrait(BaseModel):
    """用户画像中的一个特征"""
    value: Any
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    first_seen: str = Field(default_factory=lambda: datetime.now().isoformat())


class UserProfile(BaseModel):
    """用户画像（存储在 Store namespace ("profiles", uid) 中）"""
    user_id: str
    name: str = ""
    role: str = ""
    skill_level: str = "intermediate"
    traits: dict[str, dict] = Field(default_factory=dict)
    facts: list[dict] = Field(default_factory=list)
    interaction_count: int = 0
    first_seen: str = Field(default_factory=lambda: datetime.now().isoformat())
    last_seen: str = Field(default_factory=lambda: datetime.now().isoformat())


class MemoryFact(BaseModel):
    """长期记忆中的一条事实（存储在 Store namespace ("memories", uid) 中）"""
    fact_id: str
    content: str
    category: str = "knowledge"  # preference / knowledge / decision / pattern
    score: float = 5.0
    confidence: float = 0.5
    recall_count: int = 0
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    last_recalled_at: Optional[str] = None
    superseded_by: Optional[str] = None

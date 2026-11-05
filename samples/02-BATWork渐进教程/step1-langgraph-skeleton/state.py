"""
Step 1: AgentState — 最简状态（3 节点用）
"""

from typing import TypedDict, List
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage
from typing import Annotated


class AgentState(TypedDict):
    user_input: str
    workspace_path: str
    intent: str
    enriched_context: str
    messages: Annotated[List[BaseMessage], add_messages]
    final_output: str

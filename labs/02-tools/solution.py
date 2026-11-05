# 参考答案 —— 卡住 3 分钟以上再看
from typing import Annotated, TypedDict

from langchain_core.messages import AIMessage
from langchain_core.tools import tool
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode


@tool
def get_device_status(device_id: str) -> str:
    """查询 5G 设备当前状态。"""
    db = {"DEV-0001": "在线，北京望京", "DEV-0002": "离线，上海张江"}
    return db.get(device_id, f"未找到设备 {device_id}")


@tool
def restart_device(device_id: str) -> str:
    """给设备下发重启指令。"""
    return f"{device_id} 已下发重启指令"


TOOLS = [get_device_status, restart_device]


class State(TypedDict):
    messages: Annotated[list, add_messages]


def assistant(state: State) -> dict:
    return {
        "messages": [
            AIMessage(
                content="",
                tool_calls=[
                    {"name": "get_device_status", "args": {"device_id": "DEV-0001"}, "id": "call_1"}
                ],
            )
        ]
    }


def route(state: State) -> str:
    last = state["messages"][-1]
    return "tools" if getattr(last, "tool_calls", None) else END


def build():
    g = StateGraph(State)
    g.add_node("assistant", assistant)
    g.add_node("tools", ToolNode(TOOLS))
    g.add_edge(START, "assistant")
    g.add_conditional_edges("assistant", route)
    g.add_edge("tools", END)
    return g.compile()

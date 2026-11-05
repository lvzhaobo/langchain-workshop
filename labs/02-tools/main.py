# %% Lab 02 —— 工具调用循环
from typing import Annotated, TypedDict

from langchain_core.messages import AIMessage
from langchain_core.tools import tool
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages


# %% 1. 工具：就是普通函数 + @tool 装饰器
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


# %% 2. State
class State(TypedDict):
    messages: Annotated[list, add_messages]


# %% 3. 「假模型」节点：写死返回一个 tool_call，不联网、不花钱
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


# %% 4. 判断函数：最后一条消息有 tool_calls 就去 tools
def route(state: State) -> str:
    last = state["messages"][-1]
    return "tools" if getattr(last, "tool_calls", None) else END


# %% 5. 组装
def build():
    g = StateGraph(State)
    g.add_node("assistant", assistant)
    g.add_edge(START, "assistant")

    # TODO 1: 加一个 tools 节点
    #         提示：g.add_node("tools", ToolNode(TOOLS))
    #         需要先 from langgraph.prebuilt import ToolNode

    # TODO 2: assistant 之后按 route 决定去哪
    #         提示：g.add_conditional_edges("assistant", route)

    # TODO 3: tools 执行完就结束（真实场景这里是回到 assistant）
    #         提示：g.add_edge("tools", END)

    return g.compile()


# %% 6. 运行
if __name__ == "__main__":
    for m in build().invoke({"messages": [("user", "DEV-0001 现在什么状态？")]})["messages"]:
        print(f"{type(m).__name__:14} → {m.content or m.tool_calls}")

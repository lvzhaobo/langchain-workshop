# 参考答案 —— 卡住 3 分钟以上再看
from typing import Annotated, TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages


class State(TypedDict):
    messages: Annotated[list, add_messages]


def node(state: State) -> dict:
    return {"messages": [("ai", "hello")]}


def build():
    g = StateGraph(State)
    g.add_node("node", node)
    g.add_edge(START, "node")
    g.add_edge("node", END)
    return g.compile()

# 参考答案 —— 卡住 3 分钟以上再看
from typing import TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import START, StateGraph


class State(TypedDict):
    turns: int


def tick(state: State) -> dict:
    return {"turns": state.get("turns", 0) + 1}


def build():
    g = StateGraph(State)
    g.add_node("tick", tick)
    g.add_edge(START, "tick")
    return g.compile(checkpointer=InMemorySaver())


def run():
    """返回 (A1, A2, B1)。"""
    app = build()
    a = {"configurable": {"thread_id": "A"}}
    b = {"configurable": {"thread_id": "B"}}
    return (
        app.invoke({}, config=a)["turns"],
        app.invoke({}, config=a)["turns"],
        app.invoke({}, config=b)["turns"],
    )

# 参考答案 —— 卡住 3 分钟以上再看
from typing import TypedDict

from langgraph.graph import END, START, StateGraph


class State(TypedDict):
    n: int
    trace: list[str]


def think(state: State) -> dict:
    n = state["n"] + 1
    return {"n": n, "trace": state.get("trace", []) + [f"think-{n}"]}


def should_continue(state: State) -> str:
    return "think" if state["n"] < 3 else END


def build():
    g = StateGraph(State)
    g.add_node("think", think)
    g.add_edge(START, "think")
    g.add_conditional_edges("think", should_continue)
    return g.compile()

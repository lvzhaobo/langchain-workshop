# %% Lab NN 起始骨架 —— 只改带 TODO 的地方
from typing import Annotated, TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages


# %% 1. State
class State(TypedDict):
    messages: Annotated[list, add_messages]


# %% 2. 节点
def node(state: State) -> dict:
    return {"messages": [("ai", "hello")]}


# %% 3. 组装
def build():
    g = StateGraph(State)
    g.add_node("node", node)
    g.add_edge(START, "node")
    # TODO 1: 把 edge 从 node 接到 END
    return g.compile()


# %% 4. 运行
if __name__ == "__main__":
    print(build().invoke({"messages": [("user", "hi")]}))

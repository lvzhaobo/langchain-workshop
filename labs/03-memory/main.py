# %% Lab 03 —— Checkpointer 与 thread_id
from typing import TypedDict

from langgraph.graph import START, StateGraph


# %% 1. State：这次只有一个字段，用来数「这个会话被调用了几次」
class State(TypedDict):
    turns: int


# %% 2. 节点：每次进来 +1
def tick(state: State) -> dict:
    return {"turns": state.get("turns", 0) + 1}


# %% 3. 组装
def build():
    g = StateGraph(State)
    g.add_node("tick", tick)
    g.add_edge(START, "tick")

    # TODO 1: 让图具备记忆 —— 给 compile 传 checkpointer
    #         提示：from langgraph.checkpoint.memory import InMemorySaver
    #               return g.compile(checkpointer=InMemorySaver())
    return g.compile()


# %% 4. 运行
if __name__ == "__main__":
    app = build()

    # TODO 2: 给每次调用指定会话
    #         提示：cfg = {"configurable": {"thread_id": "A"}}
    #               app.invoke({}, config=cfg)
    print("thread A 第 1 次 →", app.invoke({}))
    print("thread A 第 2 次 →", app.invoke({}))
    print("thread B 第 1 次 →", app.invoke({}))

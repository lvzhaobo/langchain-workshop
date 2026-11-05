# %% Lab 01 —— 最小 StateGraph
# 目标：让 think 节点循环 3 次后自动结束
from typing import TypedDict

from langgraph.graph import END, START, StateGraph


# %% 1. State：图在节点之间传递的共享数据
class State(TypedDict):
    n: int              # 已经跑了几轮
    trace: list[str]    # 每轮留下一条痕迹


# %% 2. Node：接收 State，返回「要更新哪些字段」
def think(state: State) -> dict:
    n = state["n"] + 1
    return {"n": n, "trace": state.get("trace", []) + [f"think-{n}"]}


# %% 3. 判断函数：返回字符串 = 下一个节点名，返回 END = 结束
def should_continue(state: State) -> str:
    return "think" if state["n"] < 3 else END


# %% 4. 组装
def build():
    g = StateGraph(State)
    g.add_node("think", think)
    g.add_edge(START, "think")

    # TODO 1: 把 think 之后的走向交给 should_continue
    #         提示：g.add_conditional_edges("think", should_continue)
    #         如果不写这一行，图在 think 之后就停了（只会跑一轮）

    return g.compile()


# %% 5. 运行
if __name__ == "__main__":
    print(build().invoke({"n": 0, "trace": []}))

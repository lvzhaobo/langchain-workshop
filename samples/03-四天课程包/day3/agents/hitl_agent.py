"""Day3 HITL Agent — 人工审批：暂停等人决定，批准后继续执行

真数据版：diagnose 节点读 day1 真实对象（指标+P0 事件），
按真实收光功率/事件给出诊断与拟执行操作，人批准后才"执行"。
"""
import operator
from typing import Any, List, Annotated
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt
from langgraph.checkpoint.memory import MemorySaver

from .tools import get_object


class HITLState(TypedDict):
    device_name: str
    diagnosis: str
    proposed_action: str
    human_decision: str
    results: Annotated[List[str], operator.add]


def diagnose(state: HITLState) -> dict[str, Any]:
    """诊断：读真实对象数据，拼出诊断结论和拟执行的高危操作"""
    oid = state["device_name"]
    obj = get_object(oid)
    if obj:
        m = obj.get("metrics", {})
        p0 = [e for e in obj.get("events", []) if e.get("level") == "P0"]
        issue = p0[0]["description"] if p0 else f"收光功率 {m.get('rx_power_dbm')} dBm，低于阈值 -28 dBm"
        diagnosis = f"{obj['id']} {obj['name']}（{obj['vendor']}）: {issue}"
    else:
        diagnosis = f"{oid} 数据缺失，按光模块功率异常预案处理"
    return {
        "diagnosis": diagnosis,
        "proposed_action": f"重启 {oid} 光模块端口",
        "results": [f"诊断: {diagnosis}"],
    }


def human_review(state: HITLState) -> dict[str, Any]:
    decision = interrupt(f"是否批准执行：{state['proposed_action']}？依据：{state['diagnosis']}")
    if decision:
        return {"human_decision": "approved"}
    return {"human_decision": "rejected"}


def execute(state: HITLState) -> dict[str, Any]:
    return {"results": [f"执行: {state['proposed_action']} — 完成"]}


def escalate(state: HITLState) -> dict[str, Any]:
    return {"results": ["升级: 提交工单给二线运维"]}


def after_review(state: HITLState) -> str:
    return "execute" if state.get("human_decision") == "approved" else "escalate"


# 全局实例供 app.py 复用
checkpointer = MemorySaver()

def build_hitl():
    builder = StateGraph(HITLState)
    for name, fn in [("diagnose", diagnose), ("human_review", human_review),
                     ("execute", execute), ("escalate", escalate)]:
        builder.add_node(name, fn)
    builder.add_edge(START, "diagnose")
    builder.add_edge("diagnose", "human_review")
    builder.add_conditional_edges("human_review", after_review, {"execute": "execute", "escalate": "escalate"})
    builder.add_edge("execute", END)
    builder.add_edge("escalate", END)
    return builder.compile(checkpointer=checkpointer)

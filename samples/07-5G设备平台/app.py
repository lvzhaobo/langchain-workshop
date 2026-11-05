"""5G 设备智能运维平台 —— LangGraph Agent 集成

启动：python app.py → http://localhost:8100
依赖：pip install flask flask-cors langgraph langchain-openai
"""

import json
import sys
import operator
from pathlib import Path
from typing import Annotated, TypedDict

# 确保 agents 模块可导入
sys.path.insert(0, str(Path(__file__).parent))

from flask import Flask, jsonify, render_template, request, Response
from flask_cors import CORS
from langgraph.graph import StateGraph, START, END, MessagesState
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import interrupt, Command
import requests

app = Flask(__name__)
CORS(app)

# ── 设备平台 API（转发到 labs-new 8000 端口）─────────
PLATFORM_URL = "http://localhost:8000"


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/devices")
def api_devices():
    try:
        resp = requests.get(f"{PLATFORM_URL}/devices", timeout=5)
        return jsonify(resp.json())
    except Exception:
        return jsonify({"error": "底层平台不可达，请先启动 labs-new 1.1: python server.py"}), 503


@app.route("/api/devices/<device_id>")
def api_device(device_id):
    try:
        resp = requests.get(f"{PLATFORM_URL}/devices/{device_id}", timeout=5)
        return jsonify(resp.json())
    except Exception:
        return jsonify({"error": "平台不可达"}), 503


# ── Agent 接口 ─────────────────────────────────────

from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import MemorySaver


def _run_agent(agent, question: str, thread_id: str):
    """通用：跑 Agent 并流式返回结果"""
    def generate():
        config = {"configurable": {"thread_id": thread_id}}
        for chunk in agent.stream(
            {"messages": [HumanMessage(content=question)]},
            config,
            stream_mode="messages",
        ):
            content = getattr(chunk[0], "content", "") if isinstance(chunk, tuple) else ""
            if content:
                yield f"data: {json.dumps({'content': content})}\n\n"
        yield "data: [DONE]\n\n"
    return Response(generate(), mimetype="text/event-stream")


@app.route("/agent/single", methods=["POST"])
def agent_single():
    """sample-6: 单 Agent（ReAct 循环 + 平台工具）"""
    from agents.single_agent import single_agent
    data = request.get_json() or {}
    question = data.get("question", "帮我查 DEV-0001 的状态和告警")
    thread_id = data.get("thread_id", "single-1")
    return _run_agent(single_agent, question, thread_id)


@app.route("/agent/stream-demo", methods=["GET"])
def agent_stream_demo():
    """sample-9: Stream 流式 — 逐 token 输出"""
    return jsonify({
        "message": "在 agent/single 接口中使用 stream_mode='messages' 实现流式输出",
        "sample": "sample-9",
    })


# ── sample-12 Superisor: 多 Agent 调度 ──────────
SUPERVISOR_CHKP = MemorySaver()

@app.route("/agent/supervisor", methods=["POST"])
def agent_supervisor():
    """sample-12: Supervisor 模式 — 中央调度 + 3 个 Worker"""
    from langgraph.graph import MessagesState
    from langchain_core.messages import AIMessage

    def supervisor_node(state: MessagesState) -> dict:
        msgs = state["messages"]
        done = set()
        for m in msgs:
            c = m.content if hasattr(m, "content") else ""
            if "[检测结果]" in c: done.add("detection")
            if "[诊断结果]" in c: done.add("diagnosis")
            if "[处置结果]" in c: done.add("disposal")
        if "detection" not in done: return {"messages": [AIMessage(content="→detection")]}
        elif "diagnosis" not in done: return {"messages": [AIMessage(content="→diagnosis")]}
        elif "disposal" not in done: return {"messages": [AIMessage(content="→disposal")]}
        return {"messages": [AIMessage(content="→FINISH")]}

    def detection_w(state): return {"messages": [AIMessage(content="[检测结果] 光模块功率异常，风险等级 P0，涉及链路 2 条")]}
    def diagnosis_w(state): return {"messages": [AIMessage(content="[诊断结果] 根因为对端设备发光模块老化")]}
    def disposal_w(state): return {"messages": [AIMessage(content="[处置结果] 已创建工单 WO-20260725-001")]}

    def route_s(state) -> str:
        last = state["messages"][-1].content
        if "detection" in last: return "detection"
        elif "diagnosis" in last: return "diagnosis"
        elif "disposal" in last: return "disposal"
        return "__end__"

    s_builder = StateGraph(MessagesState)
    for name, fn in [("supervisor", supervisor_node), ("detection", detection_w), ("diagnosis", diagnosis_w), ("disposal", disposal_w)]:
        s_builder.add_node(name, fn)
    s_builder.add_edge(START, "supervisor")
    s_builder.add_conditional_edges("supervisor", route_s, {"detection":"detection","diagnosis":"diagnosis","disposal":"disposal","__end__":END})
    s_builder.add_edge("detection", "supervisor"); s_builder.add_edge("diagnosis", "supervisor"); s_builder.add_edge("disposal", "supervisor")
    s_agent = s_builder.compile()

    data = request.get_json() or {}
    q = data.get("question", "DEV-0001 业务中断，全面排查")
    tid = data.get("thread_id", "supervisor-" + str(int(__import__("time").time())))
    return _run_agent(s_agent, q, tid)


# ── sample-8 HITL: 人工审批 ─────────────────────
_pending_hitl: dict[str, dict] = {}

@app.route("/agent/hitl/start", methods=["POST"])
def agent_hitl_start():
    """sample-8: HITL — 开始排查，在审批点暂停"""
    from langgraph.types import Command
    import operator

    class HITLState(TypedDict):
        device_name: str; diagnosis: str; proposed_action: str
        human_decision: str; results: Annotated[list, operator.add]

    def diagnose(state): return {"diagnosis": f"{state['device_name']} 光模块功率异常", "proposed_action": f"重启 {state['device_name']} 光模块端口", "results": [f"诊断: 光模块功率异常"]}
    def human_review(state):
        decision = interrupt(f"是否批准执行：{state['proposed_action']}？")
        return {"human_decision": "approved" if decision else "rejected"}
    def execute(state): return {"results": [f"执行: {state['proposed_action']} — 完成"]}
    def escalate(state): return {"results": ["升级: 提交工单给二线运维"]}
    def after_review(state) -> str: return "execute" if state.get("human_decision") == "approved" else "escalate"

    h_builder = StateGraph(HITLState)
    for n, f in [("diagnose", diagnose), ("human_review", human_review), ("execute", execute), ("escalate", escalate)]:
        h_builder.add_node(n, f)
    h_builder.add_edge(START, "diagnose"); h_builder.add_edge("diagnose", "human_review")
    h_builder.add_conditional_edges("human_review", after_review, {"execute":"execute","escalate":"escalate"})
    h_builder.add_edge("execute", END); h_builder.add_edge("escalate", END)
    h_agent = h_builder.compile(checkpointer=MemorySaver())

    data = request.get_json() or {}
    device = data.get("device_name", "DEV-0001")
    tid = data.get("thread_id", "hitl-" + str(int(__import__("time").time())))

    try:
        h_agent.invoke({"device_name": device, "results": []}, {"configurable": {"thread_id": tid}})
    except Exception:
        pass  # interrupted — expected

    state = h_agent.get_state({"configurable": {"thread_id": tid}})
    _pending_hitl[tid] = {"agent": h_agent, "state": state}
    return jsonify({"status": "pending", "thread_id": tid, "device": device, "action": f"重启 {device} 光模块端口"})


@app.route("/agent/hitl/decide", methods=["POST"])
def agent_hitl_decide():
    """sample-8: HITL — 人做决定后继续"""
    from langgraph.types import Command
    data = request.get_json() or {}
    tid = data.get("thread_id")
    approved = data.get("approved", False)
    if tid not in _pending_hitl: return jsonify({"error": "session not found"}), 404
    info = _pending_hitl.pop(tid)
    result = info["agent"].invoke(Command(resume=approved), {"configurable": {"thread_id": tid}})
    return jsonify({"status": "completed", "decision": "approved" if approved else "rejected", "results": result.get("results", [])})


# ── Checkpoint Sessions ─────────────────────────
@app.route("/sessions", methods=["GET"])
def list_sessions():
    """sample-7: 列出所有 checkpoint 会话"""
    return jsonify({"sessions": [], "message": "使用 MemorySaver，重启后会话清空。生产请用 SqliteSaver"})


# ── RAG Search ──────────────────────────────────
@app.route("/rag/search", methods=["POST"])
def rag_search():
    """sample-14: RAG 知识库检索"""
    data = request.get_json() or {}
    q = data.get("question", "")
    # Mock 知识库检索结果
    kb = {
        "光模块": ["收光功率低于-28dBm视为异常，低于-30dBm为严重故障。常见原因：光纤接头脏污、对端发光模块老化。",
                   "排查步骤：1.清洁光纤接头 2.检查对端光模块发光功率 3.更换光模块测试"],
        "端口": ["端口Down排查：1.检查物理链路 2.查看CRC错误计数 3.检查对端设备状态 4.shutdown/undo shutdown重置"],
        "告警": ["P0：业务中断需立即处理；P1：性能严重下降2小时内处理；P2：一般告警24小时内处理；P3：提示信息可延后"],
        "AAU": ["AAU正常工作温度范围-40°C至+55°C，发射功率不应超过40W（46dBm），定期检查驻波比。"],
    }
    results = []
    for kw, docs in kb.items():
        if kw in q:
            results.extend(docs)
    if not results:
        results = [v[0] for v in kb.values()][:2]  # 默认返回前两类
    return jsonify({"question": q, "results": results, "count": len(results)})


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    print(f"""
╔══════════════════════════════════════════════╗
║   5G 设备智能运维平台                         ║
║                                              ║
║   地址：http://localhost:8100                 ║
║                                              ║
║   实验接口：                                   ║
║   POST /agent/single    sample-6 单Agent      ║
║                                              ║
║   依赖：先在 labs-new 1.1 启动平台（8000）     ║
╚══════════════════════════════════════════════╝
""")
    app.run(host="0.0.0.0", port=8100, debug=True)

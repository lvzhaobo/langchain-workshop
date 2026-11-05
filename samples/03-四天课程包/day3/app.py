"""Day3 多 Agent 协作 —— Supervisor + HITL + Stream + Checkpoint

启动：
    cp .env.example .env   # 填入 DEEPSEEK_API_KEY
    pip install -r requirements.txt
    python app.py          # → http://localhost:8301

功能通道（统一 SSE）：
    POST /agent/supervisor   Supervisor 多 Agent 调度
    POST /agent/hitl/start   人工审批（暂停等待）
    POST /agent/hitl/decide  人做决定后继续
    GET  /sessions           查看 Checkpoint 会话
"""
import json, os, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv()

from flask import Flask, Response, jsonify, render_template, request
from langchain_core.messages import HumanMessage
from langgraph.types import Command

app = Flask(__name__)

# ═══ HITL Agent（checkpointer 全局共享，Supervisor 也用它存会话）═══
from agents.hitl_agent import build_hitl, checkpointer
hitl_agent = build_hitl()

# ═══ Supervisor Agent ═══
from agents.supervisor_agent import build_supervisor
supervisor_agent = build_supervisor(checkpointer)

@app.route("/agent/supervisor", methods=["POST"])
def run_supervisor():
    data = request.get_json() or {}
    q = data.get("question", "OBJ-0006 业务中断，全面排查")
    tid = data.get("thread_id", "sup-" + str(int(time.time())))

    def generate():
        config = {"configurable": {"thread_id": tid}}
        for chunk in supervisor_agent.stream(
            {"messages": [HumanMessage(content=q)]}, config, stream_mode="messages"
        ):
            if isinstance(chunk, tuple) and hasattr(chunk[0], "content") and chunk[0].content:
                yield f"data: {json.dumps({'content': chunk[0].content})}\n\n"
        yield "data: [DONE]\n\n"

    return Response(generate(), mimetype="text/event-stream")


# ═══ HITL 接口 ═══
@app.route("/agent/hitl/start", methods=["POST"])
def hitl_start():
    data = request.get_json() or {}
    device = data.get("device_name", "OBJ-0006")
    tid = data.get("thread_id", "hitl-" + str(int(time.time())))
    try:
        hitl_agent.invoke({"device_name": device, "results": []}, {"configurable": {"thread_id": tid}})
    except Exception:
        pass  # interrupt 触发的异常
    state = hitl_agent.get_state({"configurable": {"thread_id": tid}})
    vals = state.values or {}
    return jsonify({"status": "pending", "thread_id": tid, "device": device,
                    "action": vals.get("proposed_action", f"重启 {device} 光模块端口"),
                    "diagnosis": vals.get("diagnosis", "")})


@app.route("/agent/hitl/decide", methods=["POST"])
def hitl_decide():
    data = request.get_json() or {}
    tid = data.get("thread_id")
    approved = data.get("approved", False)
    if not tid: return jsonify({"error": "缺少 thread_id"}), 400
    result = hitl_agent.invoke(Command(resume=approved), {"configurable": {"thread_id": tid}})
    return jsonify({"status": "completed", "decision": "approved" if approved else "rejected",
                    "results": result.get("results", [])})


# ═══ Sessions ═══
@app.route("/sessions", methods=["GET"])
def list_sessions():
    # MemorySaver.storage: {thread_id: {ns: {checkpoint_id: ...}}}
    sessions = []
    for tid, ns_map in getattr(checkpointer, "storage", {}).items():
        n = sum(len(cps) for cps in ns_map.values())
        sessions.append({"thread_id": tid, "checkpoints": n})
    return jsonify({"sessions": sessions, "total": len(sessions)})


# ═══ Pages ═══
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/health")
def health():
    api_ok = bool(os.getenv("DEEPSEEK_API_KEY"))
    return jsonify({"status": "ok", "api_configured": api_ok})


if __name__ == "__main__":
    print("Day3 多Agent协作: http://localhost:8301")
    app.run(host="0.0.0.0", port=8301, debug=True)

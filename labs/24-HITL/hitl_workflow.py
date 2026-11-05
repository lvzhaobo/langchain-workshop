"""HITL 人工审批 — LangGraph interrupt + Command(resume) + Web 页面 + 飞书通知

三通道：
  1. 终端 input()        — 零依赖，理解 interrupt 机制
  2. Web 页面审批        — 平台页面展示审批卡片，点击通过/驳回
  3. 飞书通知            — 讲师演示：卡片链接 → 打开 Web 页面审批

运行：
  python hitl_workflow.py                     # 终端 input 模式
  python hitl_workflow.py --server            # 启动 Web 审批服务（端口 8100）
  python hitl_workflow.py --offline           # 离线演示（纯打印，不调 LLM）

依赖：pip install langgraph langchain langchain-openai requests flask
"""
import os
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))  # 自动读取课程根目录 .env

import json
import sys
import time
import threading
import uuid
from pathlib import Path
from typing import TypedDict, Literal, Annotated
import operator

import requests
from flask import Flask, request, jsonify, render_template_string

# ═══ 配置 ═══
BASE_URL = "http://localhost:8000"  # 平台地址
HITL_PORT = 8100                    # 审批服务端口
WEB_APPROVAL_URL = f"http://localhost:{HITL_PORT}"

# ═══ 全局审批队列 — 线程间通信 ═══
_pending: dict[str, dict] = {}  # approval_id → {"state","event","result"}
_lock = threading.Lock()

# ═══ LangGraph ═══
# interrupt 与 Command 都要从 langgraph.types 导入
# 如果此环境无 langgraph，请 pip install langgraph>=0.2
try:
    from langgraph.types import Command, interrupt
    from langgraph.graph import StateGraph, END
    from langgraph.checkpoint.memory import MemorySaver
    LANGGRAPH_READY = True
except ImportError:
    LANGGRAPH_READY = False
    Command = None  # type: ignore

    def interrupt(value):  # type: ignore[misc]
        raise RuntimeError("本实验需要 langgraph：pip install 'langgraph<1.0'")


# ══════════════════════════════════════════════════════════════
# State & Agent 节点
# ══════════════════════════════════════════════════════════════

class HITLState(TypedDict, total=False):
    user_input: str
    device_id: str
    detect_result: str
    diagnose_result: str
    decide_result: str
    execute_result: str
    risk_level: str               # high / medium / low
    approval_status: str          # pending / approved / rejected / auto_approved
    approval_id: str              # Web 审批用——关联 approval_id
    messages: Annotated[list, operator.add]


def _ask(prompt: str) -> str:
    try:
        from langchain_openai import ChatOpenAI
        llm = ChatOpenAI(model=os.getenv("AGENT_MODEL", "deepseek-chat"), temperature=0,
                         api_key=os.getenv("AGENT_API_KEY", "REPLACE_ME_NO_KEY"), base_url=os.getenv("AGENT_API_BASE", "https://api.deepseek.com/v1"))
        return llm.invoke(prompt).content
    except Exception:
        return f"[LLM 不可用] 模拟分析：{prompt[:60]}..."


# 取数降级：HTTP 优先 → 本地快照兜底 → 明确失败（同 3.2 / 3.3）
DEVICES_FILE = Path(__file__).parent / "data" / "devices.json"
if not DEVICES_FILE.exists():
    DEVICES_FILE = Path(__file__).parent.parent / "04-平台搭建" / "data" / "devices.json"


def _fetch_device(device_id: str) -> str:
    d, degraded = None, False
    try:
        resp = requests.get(f"{BASE_URL}/devices/{device_id}", timeout=5)
        data = resp.json()
        if not data.get("found"):
            return f"设备 {device_id} 不存在"
        d = data["device"]
    except Exception:
        # 读 1.1 的真数据，不能随手编一台设备 —— 编的数据跟平台对不上，
        # 学员开着平台查到 running、关了平台又看到 alarm，只会以为自己环境坏了。
        try:
            devices = json.loads(DEVICES_FILE.read_text(encoding="utf-8"))
            d = next((x for x in devices if x["device_id"] == device_id), None)
            degraded = True
        except Exception:
            d = None
        if d is None:
            return f"取数失败：平台 {BASE_URL} 不可达，本地快照中也没有 {device_id}。请勿基于推测作答。"

    alarms = d.get("alarms", [])
    alarm_text = "\n".join([
        f"  [{a['severity']}] {a['type']}: {a['description']}"
        for a in alarms
    ]) if alarms else "无告警"
    note = "\n（数据来源：本地快照，平台 API 未启动）" if degraded else ""
    return (f"{d['vendor']} {d['model']}，站点 {d['site']}，状态 {d['status']}。"
            f"告警({len(alarms)}条):\n{alarm_text}" + note)


def detector_node(state: HITLState) -> HITLState:
    device_id = state.get("device_id", "DEV-0001")
    device_info = _fetch_device(device_id)
    analysis = _ask(f"分析设备状态。输出：状态/告警汇总/初步判断。\n{device_info}")
    return {**state, "detect_result": analysis}


def diagnoser_node(state: HITLState) -> HITLState:
    diagnosis = _ask(f"诊断根因。输出：最可能根因+置信度+备选。\n{state.get('detect_result','')[:500]}")
    return {**state, "diagnose_result": diagnosis}


def decider_node(state: HITLState) -> HITLState:
    decision = _ask(f"评估风险。输出：风险等级(high/medium/low)+处置策略。\n{state.get('diagnose_result','')[:400]}")
    risk = "medium"
    for level in ("high", "low"):
        if f"风险等级：{level}" in decision or f"风险等级: {level}" in decision:
            risk = level; break
    if "P0" in state.get("detect_result", ""):
        risk = "high"
    return {**state, "decide_result": decision, "risk_level": risk}


def human_approval_node(state: HITLState) -> HITLState:
    """人工审批节点——interrupt() 暂停，三通道恢复"""
    risk = state.get("risk_level", "medium")

    if risk != "high":
        return {**state, "approval_status": "auto_approved"}

    # 生成审批 ID（Web 审批用）
    approval_id = str(uuid.uuid4())[:8]
    state["approval_id"] = approval_id

    # 写入全局队列（Web 审批通道）
    event = threading.Event()
    with _lock:
        _pending[approval_id] = {
            "device_id": state.get("device_id", ""),
            "risk_level": risk,
            "summary": state.get("decide_result", "")[:300],
            "event": event,
            "result": None,
        }

    # 发送飞书通知（如果 feishu-server.py 在运行）
    _notify_feishu(approval_id, state)

    # ═══ interrupt 暂停 ═══
    # interrupt() 把当前状态存进 checkpointer 并把入参抛回调用方，
    # 直到 Command(resume=...) 才继续往下执行
    result = interrupt({
        "approval_id": approval_id,
        "device_id": state.get("device_id", ""),
        "risk_level": risk,
        "summary": state.get("decide_result", "")[:300],
    })

    # === resume 后 ===
    # 清理队列
    with _lock:
        _pending.pop(approval_id, None)

    if isinstance(result, dict):
        approved = result.get("approved", False)
    else:
        approved = str(result).lower() in ("y", "yes", "true")

    print(f"\n   审批结果：{'通过' if approved else '驳回'}")

    return {**state, "approval_status": "approved" if approved else "rejected"}


def executor_node(state: HITLState) -> HITLState:
    if state.get("approval_status") == "rejected":
        return {**state, "execute_result": "审批驳回，处置方案已取消。请联系审批人重新评估。"}

    execution = _ask(
        f"生成处置方案。输出：步骤+命令+耗时+回滚。\n{state.get('decide_result','')[:400]}"
    )
    return {**state, "execute_result": execution}


def risk_router(state: HITLState) -> Literal["human_approval", "executor", "__end__"]:
    if state.get("risk_level") == "high":
        return "human_approval"
    return "executor"


def build_hitl_pipeline():
    graph = StateGraph(HITLState)
    graph.add_node("detector", detector_node)
    graph.add_node("diagnoser", diagnoser_node)
    graph.add_node("decider", decider_node)
    graph.add_node("human_approval", human_approval_node)
    graph.add_node("executor", executor_node)

    graph.set_entry_point("detector")
    graph.add_edge("detector", "diagnoser")
    graph.add_edge("diagnoser", "decider")
    graph.add_conditional_edges("decider", risk_router, {
        "human_approval": "human_approval",
        "executor": "executor",
    })
    graph.add_edge("human_approval", "executor")
    graph.add_edge("executor", END)

    return graph.compile(checkpointer=MemorySaver())


# ══════════════════════════════════════════════════════════════
# 飞书通知 — 发送卡片链接（不依赖回调机制）
# ══════════════════════════════════════════════════════════════

FEISHU_SERVER = "http://localhost:3456"  # lab-07/api/feishu-server.py


def _notify_feishu(approval_id: str, state: HITLState):
    """向飞书发送审批通知卡片。卡片按钮是 URL 链接 → 打开 Web 审批页。

    这种模式不需要飞书回调——卡片上的按钮直接打开浏览器，
    用户在自己的电脑上完成审批，Web 服务收到请求后唤醒流水线。
    """
    approve_url = f"{WEB_APPROVAL_URL}/approve/{approval_id}"
    reject_url = f"{WEB_APPROVAL_URL}/reject/{approval_id}"

    card = {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": "人工审批 · 5G基站排障"},
            "template": "red",
        },
        "elements": [
            {"tag": "div", "text": {"tag": "lark_md", "content": (
                f"**设备：**{state.get('device_id','')}\n"
                f"**风险等级：**{state.get('risk_level','')}\n\n"
                f"**诊断摘要：**\n{state.get('decide_result','')[:200]}"
            )}},
            {"tag": "hr"},
            {"tag": "action", "actions": [
                {"tag": "button", "text": {"tag": "plain_text", "content": "通过审批"},
                 "type": "primary", "url": approve_url},
                {"tag": "button", "text": {"tag": "plain_text", "content": "驳回审批"},
                 "type": "danger", "url": reject_url},
            ]},
        ],
    }

    try:
        requests.post(f"{FEISHU_SERVER}/api/send-card", json={
            "receive_id_type": "open_id",
            "receive_id": "ou_5f21b96e0709ced8aecd1ca3f87956da",
            "card": card,
        }, timeout=5)
        print(f"   飞书审批通知已发送（卡片链接 → Web 审批页面）")
    except Exception:
        pass  # 飞书服务不可用，不影响主流程


# ══════════════════════════════════════════════════════════════
# Web 审批服务 — Flask
# ══════════════════════════════════════════════════════════════

APPROVAL_PAGE_HTML = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>HITL 审批</title>
<style>
  body{font-family:system-ui;max-width:640px;margin:40px auto;padding:20px}
  .card{border-radius:12px;padding:24px;border-left:4px solid #dc2626;background:#fef2f2}
  h1{font-size:20px;margin-bottom:16px} pre{background:#f3f4f6;padding:12px;border-radius:8px;font-size:14px;white-space:pre-wrap}
  .actions{margin-top:20px;display:flex;gap:12px}
  button{padding:10px 24px;border:none;border-radius:8px;font-size:16px;cursor:pointer;color:white}
  .approve{background:#16a34a}.reject{background:#dc2626}
  .result{display:none;margin-top:20px;padding:16px;border-radius:8px;font-size:18px}
  .result.ok{display:block;background:#dcfce7;color:#166534}
  .result.no{display:block;background:#fef2f2;color:#991b1b}
</style></head><body>
<div class="card">
  <h1>人工审批 — {{ risk_level }} 风险</h1>
  <p><strong>设备：</strong>{{ device_id }}</p>
  <p><strong>审批 ID：</strong>{{ approval_id }}</p>
  <pre>{{ summary }}</pre>
  <div class="actions">
    <button class="approve" onclick="submit('approve')">通过审批</button>
    <button class="reject" onclick="submit('reject')">驳回审批</button>
  </div>
</div>
<div class="result" id="result"></div>
<script>
async function submit(action){
  const btns=document.querySelectorAll('button');btns.forEach(b=>b.disabled=true);
  const resp=await fetch('/hitl/'+action,{method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({approval_id:'{{ approval_id }}'})});
  const r=document.getElementById('result');
  if(resp.ok){r.className='result ok';r.textContent=action==='approve'?'已通过':'已驳回';}
  else{r.className='result no';r.textContent='处理失败，请重试';btns.forEach(b=>b.disabled=false);}
}
</script></body></html>"""


def create_web_app():
    app = Flask(__name__)

    @app.route("/")
    def index():
        with _lock:
            count = len(_pending)
        return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>HITL 审批服务</title>
<style>
  body{{font-family:system-ui;max-width:640px;margin:40px auto;padding:20px}}
  h1{{font-size:20px}} .info{{background:#f0f9ff;padding:16px;border-radius:8px;margin:12px 0}}
  a{{color:#2563eb}}
</style></head><body>
<h1>HITL 人工审批服务</h1>
<div class="info">
  <p>当前待审批：<strong>{count}</strong> 项</p>
  <p><a href="/hitl/pending">查看待审批列表</a></p>
</div>
<p>端点：</p>
<ul>
  <li><code>GET /</code> — 本页</li>
  <li><code>GET /hitl/pending</code> — 待审批列表 (JSON)</li>
  <li><code>POST /hitl/approve</code> — 通过审批</li>
  <li><code>POST /hitl/reject</code> — 驳回审批</li>
  <li><code>GET /approve/&lt;id&gt;</code> — 审批页面</li>
  <li><code>GET /reject/&lt;id&gt;</code> — 驳回页面</li>
</ul>
</body></html>"""

    @app.route("/hitl/pending", methods=["GET"])
    def list_pending():
        with _lock:
            items = [{"approval_id": aid, "device_id": info["device_id"],
                       "risk_level": info["risk_level"]} for aid, info in _pending.items()]
        return jsonify({"pending": items, "count": len(items)})

    @app.route("/hitl/approve", methods=["POST"])
    def hitl_approve():
        data = request.get_json(silent=True) or {}
        aid = data.get("approval_id", "")
        with _lock:
            info = _pending.get(aid)
        if not info:
            return jsonify({"error": f"审批项 {aid} 不存在或已处理"}), 404
        info["result"] = {"approved": True}
        info["event"].set()
        return jsonify({"status": "ok", "message": "已通过"})

    @app.route("/hitl/reject", methods=["POST"])
    def hitl_reject():
        data = request.get_json(silent=True) or {}
        aid = data.get("approval_id", "")
        with _lock:
            info = _pending.get(aid)
        if not info:
            return jsonify({"error": f"审批项 {aid} 不存在或已处理"}), 404
        info["result"] = {"approved": False}
        info["event"].set()
        return jsonify({"status": "ok", "message": "已驳回"})

    # 直接 URL 访问审批页面（飞书卡片链接目标）
    @app.route("/approve/<approval_id>")
    def approve_page(approval_id):
        return _render_approval_page(approval_id, "approve")

    @app.route("/reject/<approval_id>")
    def reject_page(approval_id):
        return _render_approval_page(approval_id, "reject")

    def _render_approval_page(approval_id, default_action):
        with _lock:
            info = _pending.get(approval_id)
        if not info:
            return f"<h1>审批项 {approval_id} 已处理或不存在</h1>", 404
        return render_template_string(
            APPROVAL_PAGE_HTML,
            approval_id=approval_id,
            device_id=info.get("device_id", ""),
            risk_level=info.get("risk_level", ""),
            summary=info.get("summary", ""),
        )

    return app


# ══════════════════════════════════════════════════════════════
# 终端审批模式（学员练习）
# ══════════════════════════════════════════════════════════════

def run_terminal(device_id="DEV-0001"):
    """终端 input 审批——零依赖，理解 interrupt 机制"""
    if not LANGGRAPH_READY:
        print("请先 pip install langgraph")
        return

    app = build_hitl_pipeline()
    config = {"configurable": {"thread_id": f"term-{uuid.uuid4().hex[:8]}"}}

    initial: HITLState = {
        "user_input": f"设备 {device_id} 有严重告警，请分析并给出处置方案",
        "device_id": device_id,
        "detect_result": "",
        "diagnose_result": "",
        "decide_result": "",
        "execute_result": "",
        "risk_level": "medium",
        "approval_status": "pending",
        "approval_id": "",
        "messages": [],
    }

    print(f"\n{'='*60}")
    print(f"  HITL 人工审批 — 终端 input 模式")
    print(f"  设备: {device_id}")
    print(f"{'='*60}")

    try:
        for event in app.stream(initial, config):
            for node_name, node_output in event.items():
                risk = node_output.get("risk_level", "")
                print(f"\n  [{node_name}]", end="")
                if risk:
                    print(f" 风险等级: {risk}")
                    if risk != "high":
                        print("  → 无需审批，自动执行")
    except Exception as e:
        # interrupt 会以异常形式中断 stream，这是预期行为；
        # 但 NameError/AttributeError 等代码错误必须暴露，不能静默吞掉
        if isinstance(e, (NameError, AttributeError, TypeError, ImportError)):
            raise

    state = app.get_state(config)
    if not state or not state.next:
        print("\n  流程已完成（无需审批）")
        return

    # ═══ 人工审批 ═══
    print(f"""
   ╔══════════════════════════════════════════╗
   ║  人工审批点                              ║
   ║                                          ║
   ║  恢复方式（任选其一）：                  ║
   ║    1. 终端输入 y / n                     ║
   ║    2. 浏览器审批页（需先 --server 启动）  ║
   ╚══════════════════════════════════════════╝
   审批页地址: http://localhost:{HITL_PORT}/approve/""")

    decision = input("   通过？(y/n): ").strip().lower()
    approved = decision == "y"

    for event in app.stream(Command(resume={"approved": approved, "comment": "终端审批"}), config):
        for node_name, _ in event.items():
            print(f"  [{node_name}] ✓")

    final = app.get_state(config).values
    print(f"\n  {'通过' if final.get('approval_status') == 'approved' else '驳回'}")
    print(f"  处置: {final.get('execute_result','')[:200]}...")


# ══════════════════════════════════════════════════════════════
# 离线演示
# ══════════════════════════════════════════════════════════════

def run_offline():
    print("=" * 60)
    print("  HITL 人工审批 — 离线演示（不调 LLM）")
    print("=" * 60)

    steps = [
        ("检测", "设备 DEV-0001（华为 AAU5613）：状态 alarm\n告警：[P0] 基站退服：SCTP链路中断"),
        ("诊断", "根因：SCTP 端点配置不匹配（置信度 0.85）"),
        ("决策", "风险等级：high\n策略：立即修复 + 升级紧急工单 + 通知二线"),
    ]
    for label, r in steps:
        print(f"\n  [{label}] {r}")
        time.sleep(0.3)

    print(f"""
   ╔══════════════════════════════════════════╗
   ║  人工审批点                              ║
   ║                                          ║
   ║  恢复方式：                              ║
   ║    终端：输入 y / n                      ║
   ║    Web：python hitl_workflow.py --server ║
   ║    飞书：卡片链接 → Web 页面审批         ║
   ║                                          ║
   ║  去掉 --offline 运行真实 LangGraph 版    ║
   ╚══════════════════════════════════════════╝""")

    decision = input("   通过？(y/n): ").strip().lower()
    if decision == "y":
        print("\n  [处置] SCTP配置已修改 → 重启链路 → 告警恢复 → 工单已生成")
    else:
        print("\n  [处置] 审批驳回，方案已取消")

    print("\nHITL 流程演示完成")


# ══════════════════════════════════════════════════════════════
# 主入口
# ══════════════════════════════════════════════════════════════

OFFLINE = "--offline" in sys.argv
SERVER_MODE = "--server" in sys.argv

if __name__ == "__main__":
    if OFFLINE:
        run_offline()
    elif SERVER_MODE:
        web_app = create_web_app()
        print(f"""
═══ HITL 审批服务 ═══
  地址: http://localhost:{HITL_PORT}
  待审批: GET  /hitl/pending
  通过:   POST /hitl/approve  {{"approval_id":"..."}}
  驳回:   POST /hitl/reject   {{"approval_id":"..."}}
  飞书卡片目标: /approve/<id>  /reject/<id>
═══════════════════════════""")
        web_app.run(host="0.0.0.0", port=HITL_PORT, debug=False)
    else:
        run_terminal()

"""
sample-18：A2A（Agent-to-Agent）— 两个独立 Agent 通过 HTTP 互相派任务

运行: python3.13 demo-18.py

对比 sample-12（Supervisor）：
  之前：一个图内的 Supervisor 调度 Worker，紧耦合
  现在：两个独立运行的 Agent 通过 HTTP + JSON 标准格式通信
"""

import json, time, threading
from http.server import HTTPServer, BaseHTTPRequestHandler

# ═══════════════════════════════════════════════════════════
# Agent A：检测 Agent（负责调用 Agent B 做诊断）
# ═══════════════════════════════════════════════════════════

class AgentA:
    """检测 Agent — 能自己查设备，也能派诊断任务给 Agent B"""
    def __init__(self):
        self.name = "检测Agent"
        self.agent_card = {
            "name": self.name,
            "url": "http://localhost:9101",
            "skills": ["detect_alarm", "query_device"],
        }

    def query_device(self, device_id):
        return f"{device_id}: 诺基亚 AirFrame 16，光模块收光功率 -30.2 dBm（异常）"

    def send_task_to_agent_b(self, question):
        """A2A 标准协议：POST /tasks → Agent B"""
        import urllib.request
        task = {
            "id": "task-001",
            "message": {"role": "user", "parts": [{"type": "text", "text": question}]}
        }
        req = urllib.request.Request(
            "http://localhost:9102/tasks",
            data=json.dumps(task).encode(),
            headers={"Content-Type": "application/json"}
        )
        resp = urllib.request.urlopen(req)
        return json.loads(resp.read())


# ═══════════════════════════════════════════════════════════
# Agent B：诊断 Agent（HTTP Server）
# ═══════════════════════════════════════════════════════════

class AgentBHandler(BaseHTTPRequestHandler):
    """Agent B 的 HTTP 接口"""

    def do_GET(self):
        if self.path == "/.well-known/agent-card.json":
            card = {"name":"诊断Agent","url":"http://localhost:9102",
                    "skills":["diagnose","search_kb"]}
            self._json(200, card)
        elif self.path == "/health":
            self._json(200, {"status": "ok"})

    def do_POST(self):
        if self.path == "/tasks":
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            msg = body["message"]["parts"][0]["text"]
            # 模拟诊断
            result = f"[诊断结果] 根因分析：对端光模块老化导致发光功率衰减。建议：更换对端光模块。"
            self._json(200, {"id": body["id"], "status": "completed",
                "message": {"role": "agent", "parts": [{"type": "text", "text": result}]}})

    def _json(self, code, data):
        self.send_response(code); self.send_header("Content-Type","application/json"); self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode())

    def log_message(self, *args): pass  # 静默日志


# ═══════════════════════════════════════════════════════════
# 启动演示
# ═══════════════════════════════════════════════════════════

print("=" * 60)
print("A2A 实战：两个 Agent 通过 HTTP 标准协议通信")
print("=" * 60)

# 1. 启动 Agent B（HTTP Server，后台线程）
server_b = HTTPServer(("localhost", 9102), AgentBHandler)
thread_b = threading.Thread(target=server_b.serve_forever, daemon=True)
thread_b.start()
print("\n1. Agent B 已启动 → http://localhost:9102")

# 2. 读取 Agent B 的 Agent Card
import urllib.request
resp = urllib.request.urlopen("http://localhost:9102/.well-known/agent-card.json")
card_b = json.loads(resp.read())
print(f"   发现 Agent: {card_b['name']}，技能: {card_b['skills']}")

# 3. Agent A 向 B 发送诊断任务
agent_a = AgentA()
print(f"\n2. Agent A 查设备状态...")
device_result = agent_a.query_device("DEV-0001")
print(f"   {device_result}")

print(f"\n3. Agent A → POST /tasks → Agent B")
print(f'   "请诊断 DEV-0001 光模块功率异常的原因"')
result = agent_a.send_task_to_agent_b("请诊断 DEV-0001 光模块功率异常的原因")
print(f"\n4. Agent B 返回诊断结果:")
print(f"   {result['message']['parts'][0]['text']}")

server_b.shutdown()

# ═══ 对比 ═══
print("\n" + "=" * 60)
print("A2A vs Supervisor — 什么时候用哪个")
print("=" * 60)
print("""
  Supervisor（sample-12）：         A2A（sample-18）：
  ┌────────────────────┐          ┌──────────┐   ┌──────────┐
  │  Supervisor         │          │ Agent A  │──→│ Agent B  │
  │  ├─ W1             │          │ (检测)   │←──│ (诊断)   │
  │  ├─ W2             │          └──────────┘   └──────────┘
  │  └─ W3             │                ↑ HTTP + JSON ↑
  └────────────────────┘          独立进程，松耦合
  一个图内，紧耦合

  Supervisor 适合：同一系统内的多 Agent 编排
  A2A 适合：跨系统、跨团队的 Agent 协作（微服务化）
""")

print("✅ sample-18 完成 — Agent B HTTP Server + Agent A 调用真实通信")

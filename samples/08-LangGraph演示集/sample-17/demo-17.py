"""
sample-17：MCP（Model Context Protocol）— 真实可运行的 MCP Server + Client

运行: python3.13 demo-17.py

对比 sample-6（@tool）：
  之前：@tool 装饰器 → 工具绑定在 LangChain 代码里，换框架得重写
  现在：MCP Server 暴露工具 → 任何 MCP Client 都能调同一套工具
"""

import subprocess, json, sys, os

print("=" * 60)
print("MCP 实战：5G 设备工具 MCP Server + Client")
print("=" * 60)

# ═══ 启动 MCP Server ═══
PYTHON = os.environ.get("PYTHON", sys.executable)  # 用当前解释器，可用 PYTHON= 覆盖获取
SERVER_SCRIPT = os.path.join(os.path.dirname(__file__), "mcp_server.py")

proc = subprocess.Popen(
    [PYTHON, SERVER_SCRIPT],
    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
)

def call_mcp(method: str, params: dict = None) -> dict:
    """发送 JSON-RPC 请求到 MCP Server"""
    req = {"jsonrpc": "2.0", "method": method, "id": 1}
    if params: req["params"] = params
    proc.stdin.write(json.dumps(req) + "\n")
    proc.stdin.flush()
    return json.loads(proc.stdout.readline())

# ═══ 1. 初始化连接 ═══
print("\n1. 初始化 MCP 连接...")
init_resp = call_mcp("initialize")
print(f"   Server: {init_resp['result']['serverInfo']['name']} v{init_resp['result']['serverInfo']['version']}")

# ═══ 2. 发现工具列表 ═══
print("\n2. 发现可用工具（tools/list）...")
tools_resp = call_mcp("tools/list")
tools = tools_resp["result"]["tools"]
for t in tools:
    print(f"   {t['name']}: {t['description']}")
    print(f"      参数: {json.dumps(t['inputSchema']['properties'], ensure_ascii=False)}")

# ═══ 3. 调用工具 ═══
print("\n3. 调工具 — 和 sample-6 的 @tool 完全一样的体验\n")

# 3a. 查设备
resp = call_mcp("tools/call", {"name": "query_device", "arguments": {"device_id": "DEV-0001"}})
result = resp["result"]["content"][0]["text"]
print(f"   query_device('DEV-0001') → {result}")

# 3b. 查告警
resp = call_mcp("tools/call", {"name": "query_alarms", "arguments": {"device_id": "DEV-0001"}})
result = resp["result"]["content"][0]["text"]
print(f"   query_alarms('DEV-0001') → {result}")

# 3c. 查另一台有告警的设备
resp = call_mcp("tools/call", {"name": "query_device", "arguments": {"device_id": "DEV-0002"}})
result = resp["result"]["content"][0]["text"]
print(f"   query_device('DEV-0002') → {result}")

resp = call_mcp("tools/call", {"name": "query_alarms", "arguments": {"device_id": "DEV-0002"}})
result = resp["result"]["content"][0]["text"]
print(f"   query_alarms('DEV-0002') → {result}")

proc.terminate()

# ═══ 4. 对比 ═══
print("\n" + "=" * 60)
print("MCP vs @tool — 对比")
print("=" * 60)
print(f"""
  sample-6 @tool 写法：                  MCP 写法：
  ┌──────────────────────────┐         ┌──────────────────────────┐
  │ @tool                    │         │ # mcp_server.py          │
  │ def query_device(id):    │         │ def query_device(id):    │
  │     return "华为 AAU..."  │         │     return "华为 AAU..." │
  │                          │         │                          │
  │ llm.bind_tools([...])    │         │ # demo-17.py             │
  │                          │         │ call_mcp("tools/call",   │
  │ 仅 LangChain 可用         │         │   {{"name":"query_device"}})
  │                          │         │                          │
  └──────────────────────────┘         │ 任何 MCP Client 都能调    │
                                       └──────────────────────────┘

  关键区别：
  - @tool 和 LangChain 绑定 → 换 Dify 得重写
  - MCP 是标准协议 → 写一次，LangChain/Dify/Coze 都能用
  - LangGraph 仍然负责编排（State + Node + Edge）
  - MCP 只替代工具绑定层
""")

print("✅ sample-17 完成 — MCP Server 真实可运行")
print("   启动方式: python3.13 mcp_server.py")

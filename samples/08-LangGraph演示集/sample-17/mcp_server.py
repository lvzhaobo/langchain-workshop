"""MCP Server — 把 5G 设备工具暴露为 MCP 标准服务

运行: python3.13 mcp_server.py
客户端通过 stdio JSON-RPC 连接并调用工具
"""
import json, sys, os

# 工具池 — 和 sample-6 的 @tool 定义一样的函数
DEVICES = {
    "DEV-0001": {"vendor":"诺基亚","model":"AirFrame 16","site":"望京SOHO","status":"running"},
    "DEV-0002": {"vendor":"华为","model":"AAU5613","site":"望京SOHO","status":"alarm"},
    "DEV-0003": {"vendor":"中兴","model":"BBU8600","site":"金融街","status":"running"},
}

def query_device(device_id: str) -> str:
    d = DEVICES.get(device_id)
    if not d: return f"设备 {device_id} 不存在"
    return f"{d['vendor']} {d['model']}，站点{d['site']}，状态{d['status']}"

def query_alarms(device_id: str) -> str:
    d = DEVICES.get(device_id)
    if not d: return f"设备 {device_id} 不存在"
    if d["status"] == "alarm": return f"{device_id}: P0-基站退服 ×1, P1-光模块异常 ×2"
    return f"{device_id}: 当前无告警"

TOOLS = {
    "query_device": {"fn": query_device, "desc": "查询 5G 基站设备详情", "params": {"device_id": "string"}},
    "query_alarms": {"fn": query_alarms, "desc": "查询设备当前告警列表", "params": {"device_id": "string"}},
}

# MCP JSON-RPC 主循环（简化实现，不依赖 mcp 包）
def handle_request(req: dict) -> dict:
    method = req.get("method")
    req_id = req.get("id")

    if method == "initialize":
        return {"jsonrpc":"2.0","id":req_id,"result":{"serverInfo":{"name":"5g-device-mcp","version":"1.0"}}}
    elif method == "tools/list":
        tools_list = [{"name":k,"description":v["desc"],
            "inputSchema":{"type":"object","properties":{p:{"type":t} for p,t in v["params"].items()}}}
            for k,v in TOOLS.items()]
        return {"jsonrpc":"2.0","id":req_id,"result":{"tools":tools_list}}
    elif method == "tools/call":
        tool_name = req["params"]["name"]
        tool_args = req["params"]["arguments"]
        tool = TOOLS.get(tool_name)
        if not tool: return {"jsonrpc":"2.0","id":req_id,"error":{"code":-32601,"message":f"Unknown tool: {tool_name}"}}
        result = tool["fn"](**tool_args)
        return {"jsonrpc":"2.0","id":req_id,"result":{"content":[{"type":"text","text":result}]}}
    return {"jsonrpc":"2.0","id":req_id,"error":{"code":-32601,"message":"Method not found"}}


if __name__ == "__main__":
    print("5G MCP Server 启动（stdio JSON-RPC）", file=sys.stderr)
    for line in sys.stdin:
        try:
            req = json.loads(line.strip())
            resp = handle_request(req)
            print(json.dumps(resp), flush=True)
        except json.JSONDecodeError:
            pass

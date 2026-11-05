"""Lab 27 · LangServe —— 把图变成 HTTP API

跑法：
    ./run.sh 27

它会：
  1. 建一个 5G 排障图（detect → diagnose）
  2. 用 add_routes 一行挂到 FastAPI 上
  3. 起本地服务，自测 /invoke /batch /stream 三个端点
  4. 打印 playground 地址

不需要 LangServe 手写路由的原因：add_routes 会自动生成
  POST /invoke    单条调用
  POST /batch     批量调用
  POST /stream    SSE 流式
  GET  /playground 可视化调试页
  GET  /openapi.json  OpenAPI 文档
"""
import os
import socket
import threading
import time
from typing import Annotated

from typing_extensions import NotRequired, TypedDict  # Python < 3.12 上 pydantic 要求用这些

import requests
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from langserve import add_routes

from _mock_llm import scripted, use_mock

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

PORT = 8123
API_BASE = os.getenv("AGENT_API_BASE", "https://api.deepseek.com/v1")
API_KEY = os.getenv("AGENT_API_KEY", "")
MODEL = os.getenv("AGENT_MODEL", "deepseek-chat")

# 假的设备库：真实场景换成平台接口
DEVICES = {
    "DEV-0001": {"vendor": "华为", "model": "AAU5613", "site": "望京SOHO", "status": "alarm",
                 "alarms": [("P0", "基站退服", "SCTP 链路中断")]},
    "DEV-0002": {"vendor": "中兴", "model": "AAU8851", "site": "广州天河", "status": "running", "alarms": []},
}


class State(TypedDict):
    # 只有 device_id 是调用方要传的；其余是图内部产生的中间量。
    # 标成 NotRequired，否则 LangServe 会把它们也算进请求体的必填字段。
    device_id: str
    device_info: NotRequired[str]
    diagnosis: NotRequired[str]
    trace: NotRequired[Annotated[list[str], lambda a, b: a + b]]


def build_llm():
    if use_mock():
        return scripted([
            ("【风险等级】高危\n【根因】SCTP 链路中断导致基站退服\n"
             "【建议】1) 检查 SCTP 偶联状态 2) 核对对端 IP 3) 30 分钟未恢复则升级", None),
        ] * 10)
    return ChatOpenAI(model=MODEL, temperature=0, api_key=API_KEY, base_url=API_BASE)


def detect_node(state: State) -> dict:
    """查设备 + 告警"""
    did = state["device_id"]
    d = DEVICES.get(did)
    if not d:
        return {"device_info": f"设备 {did} 不存在", "trace": ["detect:未找到"]}
    alarms = "；".join(f"[{s}] {t}: {desc}" for s, t, desc in d["alarms"]) or "无告警"
    info = (f"设备 {did}：{d['vendor']} {d['model']}，站点 {d['site']}，"
            f"状态 {d['status']}，告警：{alarms}")
    return {"device_info": info, "trace": ["detect:ok"]}


def diagnose_node(state: State) -> dict:
    """让模型给诊断结论"""
    llm = build_llm()
    msgs = [
        SystemMessage(content="你是 5G 运维专家。根据设备信息给出诊断，控制在 120 字内。"),
        HumanMessage(content=f"请诊断：\n{state['device_info']}"),
    ]
    out = llm.invoke(msgs)
    return {"diagnosis": out.content, "trace": ["diagnose:ok"]}


def build_graph():
    g = StateGraph(State)
    g.add_node("detect", detect_node)
    g.add_node("diagnose", diagnose_node)
    g.add_edge(START, "detect")
    g.add_edge("detect", "diagnose")
    g.add_edge("diagnose", END)
    return g.compile()


# ═══ 挂到 FastAPI ═══
graph = build_graph()
app = FastAPI(title="5G 排障 API", version="1.0.0")
add_routes(app, graph, path="/diagnose")


def _free_port(preferred: int) -> int:
    for p in (preferred, 0):
        with socket.socket() as s:
            try:
                s.bind(("127.0.0.1", p))
                return s.getsockname()[1]
            except OSError:
                continue
    return preferred


def start_server() -> tuple[uvicorn.Server, int]:
    port = _free_port(PORT)
    cfg = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error")
    server = uvicorn.Server(cfg)
    threading.Thread(target=server.run, daemon=True).start()
    for _ in range(100):
        try:
            requests.get(f"http://127.0.0.1:{port}/openapi.json", timeout=0.5)
            return server, port
        except requests.RequestException:
            time.sleep(0.1)
    raise RuntimeError("服务没起来")


def main() -> None:
    if use_mock():
        print("⚠️  没检测到 AGENT_API_KEY —— 用预设答复（零 Key 模式）\n")

    server, port = start_server()
    base = f"http://127.0.0.1:{port}/diagnose"

    print("=" * 62)
    print("  Lab 27 · LangServe 把图变成 HTTP API")
    print("=" * 62)

    print(f"\n① add_routes 自动生成的端点")
    for p in ("/invoke", "/batch", "/stream", "/playground", "/openapi.json"):
        print(f"     POST {base}{p}" if p in ("/invoke", "/batch", "/stream") else f"     GET  {base}{p}")

    print(f"\n② 单条调用 POST /invoke")
    r = requests.post(f"{base}/invoke", json={"input": {"device_id": "DEV-0001"}}, timeout=120)
    r.raise_for_status()
    out = r.json()["output"]
    print(f"     状态码 {r.status_code}")
    print(f"     诊断：{out['diagnosis'][:80]}…")
    print(f"     trace：{out['trace']}")

    print(f"\n③ 批量调用 POST /batch —— 一次发多条，省往返")
    r = requests.post(f"{base}/batch",
                      json={"inputs": [{"device_id": "DEV-0001"}, {"device_id": "DEV-0002"}]},
                      timeout=180)
    r.raise_for_status()
    outs = r.json()["output"]
    print(f"     返回 {len(outs)} 条结果")
    for i, o in enumerate(outs, 1):
        print(f"     [{i}] {o['diagnosis'][:60]}…")

    print(f"\n④ 流式 POST /stream —— SSE，前端可以逐字渲染")
    chunks = 0
    with requests.post(f"{base}/stream", json={"input": {"device_id": "DEV-0001"}},
                       stream=True, timeout=120) as resp:
        resp.raise_for_status()
        for line in resp.iter_lines():
            if line.startswith(b"data:"):
                chunks += 1
    print(f"     收到 {chunks} 个 SSE 事件")

    print(f"\n⑤ 可视化调试页")
    print(f"     地址：http://127.0.0.1:{port}/diagnose/playground/   ← 注意结尾的斜杠")
    print(f"     ⚠️  本脚本跑完就会关掉服务。要常驻，另开一个终端：")
    print(f"        ./run.sh 27 --serve")

    print(f"\n{'=' * 62}")
    print("  核心收获")
    print("  1. add_routes 一行把 Runnable / 图变成 5 个端点，不用手写路由")
    print("  2. /playground 自带调试界面，给前端或客户演示最省事")
    print("  3. /stream 走 SSE，图里每个节点都会推一个事件")
    print("  4. 输入输出结构自动进 OpenAPI，前端能直接生成客户端")
    print("=" * 62)

    server.should_exit = True


if __name__ == "__main__":
    import sys

    if "--serve" in sys.argv:
        print("=" * 64, flush=True)
        print("  LangServe 常驻服务", flush=True)
        print("=" * 64, flush=True)
        print(f"  Playground : http://127.0.0.1:{PORT}/diagnose/playground/", flush=True)
        print(f"  OpenAPI    : http://127.0.0.1:{PORT}/openapi.json", flush=True)
        print(f"  invoke     : POST http://127.0.0.1:{PORT}/diagnose/invoke", flush=True)
        print("  Ctrl+C 停止", flush=True)
        print("=" * 64, flush=True)
        uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="info")
    else:
        main()

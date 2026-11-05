"""平台工具 —— @tool 回调本平台 API（localhost:8100）

教学点：Agent 不直接读文件，而是像真实运维系统一样调平台 HTTP API，
形成 "Agent → 工具 → 平台 API → 数据" 的闭环。
docstring 会被 LLM 用来决定选哪个工具，务必写清楚参数与用途。
"""
import requests
from langchain_core.tools import tool

BASE_URL = "http://localhost:8081"


@tool
def query_object(object_id: str) -> str:
    """查询单个对象的详情（基本信息 + 关键指标）。参数：object_id 如 OBJ-0001"""
    try:
        resp = requests.get(f"{BASE_URL}/api/objects/{object_id}", timeout=5)
        data = resp.json()
        if not data.get("found"):
            return f"对象 {object_id} 不存在"
        o = data["object"]
        metrics = "，".join(f"{k}={v}" for k, v in o.get("metrics", {}).items())
        return (
            f"{o['id']} {o['name']}：类别 {o['category']}，"
            f"厂商 {o.get('vendor', '-')} 型号 {o.get('model', '-')}，"
            f"位置 {o.get('site', '-')}，状态 {o['status']}。指标：{metrics}"
        )
    except Exception as e:
        return f"平台不可达（{BASE_URL}）: {e}"


@tool
def query_events(object_id: str) -> str:
    """查询对象的异常/事件列表。参数：object_id 如 OBJ-0001"""
    try:
        resp = requests.get(f"{BASE_URL}/api/objects/{object_id}", timeout=5)
        data = resp.json()
        if not data.get("found"):
            return f"对象 {object_id} 不存在"
        events = data["object"].get("events", [])
        if not events:
            return f"{object_id} 当前无异常事件"
        lines = [
            f"- [{e.get('level', '?')}] {e.get('type', '')}: {e.get('description', '')}（{e.get('time', '')}）"
            for e in events
        ]
        return f"{object_id} 异常事件({len(events)}条):\n" + "\n".join(lines)
    except Exception as e:
        return f"平台不可达: {e}"


@tool
def list_objects(status: str = "") -> str:
    """列出对象清单。参数：status 可选，筛选 normal/warning/fault，留空返回全部"""
    try:
        url = f"{BASE_URL}/api/objects"
        if status:
            url += f"?status={status}"
        resp = requests.get(url, timeout=5)
        data = resp.json()
        objects = data.get("objects", [])
        lines = [f"- {o['id']} {o['name']} [{o['status']}] 事件{len(o.get('events', []))}条" for o in objects[:10]]
        return f"对象列表(共{data.get('total', len(objects))}条，显示前10):\n" + "\n".join(lines)
    except Exception as e:
        return f"平台不可达: {e}"


# 工具清单（供 single_agent.py 使用，放在函数定义之后）
TOOLS = [query_object, query_events, list_objects]

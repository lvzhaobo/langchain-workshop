"""5G 平台工具 —— 对接 labs-new 平台 API（localhost:8000）"""

import requests
from langchain_core.tools import tool

BASE_URL = "http://localhost:8000"


@tool
def query_device(device_id: str) -> str:
    """查询 5G 基站设备详情。参数：device_id 如 DEV-0001"""
    try:
        resp = requests.get(f"{BASE_URL}/devices/{device_id}", timeout=5)
        data = resp.json()
        if not data.get("found"):
            return f"设备 {device_id} 不存在"
        d = data["device"]
        return (
            f"设备 {device_id}：{d['vendor']} {d['model']}，"
            f"类型 {d['type']}，站点 {d['site']}，状态 {d['status']}"
        )
    except Exception as e:
        return f"平台不可达（{BASE_URL}）: {e}"


@tool
def query_alarms(device_id: str) -> str:
    """查询设备告警列表。参数：device_id 如 DEV-0001"""
    try:
        resp = requests.get(f"{BASE_URL}/devices/{device_id}/alarms", timeout=5)
        data = resp.json()
        alarms = data.get("alarms", [])
        if not alarms:
            return f"{device_id} 当前无告警"
        lines = [f"- [{a.get('severity','?')}] {a.get('type','')}: {a.get('description','')}" for a in alarms]
        return f"{device_id} 告警({len(alarms)}条):\n" + "\n".join(lines)
    except Exception as e:
        return f"平台不可达: {e}"


@tool
def list_devices(status: str = "") -> str:
    """列出所有设备。参数：status 可选，筛选 online/offline/warning/critical"""
    try:
        url = f"{BASE_URL}/devices"
        if status:
            url += f"?status={status}"
        resp = requests.get(url, timeout=5)
        data = resp.json()
        devices = data.get("devices", [])
        lines = [f"- {d['device_id']} {d['vendor']} {d['model']} 站点{d['site']} [{d['status']}]" for d in devices[:10]]
        return f"设备列表(共{len(devices)}台，显示前10):\n" + "\n".join(lines)
    except Exception as e:
        return f"平台不可达: {e}"

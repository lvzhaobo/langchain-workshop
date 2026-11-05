"""Day3 共享工具 — 真实数据接入：day1 对象数据 + day2 知识库

多 Agent 场景的数据源与 Day1/Day2 打通：
    对象数据: 优先 HTTP 调 day1 平台（8081，在跑就复用），未启动则直接读 ../day1/data/objects.json
    知识库:   直接读 ../day2/data/knowledge/*.md，关键词打分检索（教学版，不依赖 Embedding）
"""
import json
import os
import re
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).parent.parent                     # day3/
DAY1_URL = os.getenv("DAY1_URL", "http://localhost:8081")
OBJECTS_FILE = BASE_DIR.parent / "day1" / "data" / "objects.json"
KNOWLEDGE_DIR = BASE_DIR.parent / "day2" / "data" / "knowledge"


def get_object(object_id: str) -> dict[str, Any] | None:
    """单对象详情：HTTP 优先（复用 day1 平台），文件兜底（day3 可独立运行）"""
    try:
        import requests
        resp = requests.get(f"{DAY1_URL}/api/objects/{object_id}", timeout=2)
        if resp.ok and resp.json().get("found"):
            return resp.json()["object"]
    except Exception:
        pass
    try:
        for o in json.loads(OBJECTS_FILE.read_text(encoding="utf-8")):
            if o["id"] == object_id:
                return o
    except Exception:
        pass
    return None


def extract_object_id(text: str) -> str:
    """从用户输入中提取对象 ID（格式 OBJ-XXXX）"""
    m = re.search(r"OBJ-\d{4}", text.upper())
    return m.group(0) if m else ""


def format_object(o: dict[str, Any]) -> str:
    """对象数据 → 给 LLM 看的事实文本（检测 Agent 的输入）"""
    m = o.get("metrics", {})
    lines = [
        f"{o['id']} {o['name']}（{o['vendor']} {o['model']}，{o['site']}）状态: {o['status']}",
        f"指标: 收光 {m.get('rx_power_dbm')} dBm | 温度 {m.get('temperature_c')}°C"
        f" | CPU {m.get('cpu_percent')}% | 驻波比 {m.get('vswr')}",
    ]
    events = o.get("events", [])
    if events:
        lines.append(f"事件（{len(events)} 条）:")
        lines += [f"  [{e['level']}] {e['type']}: {e['description']}（{e['time']}）" for e in events]
    else:
        lines.append("事件: 无")
    return "\n".join(lines)


def search_knowledge(query: str, top_k: int = 2) -> list[dict[str, Any]]:
    """知识库检索（教学版）：按 ## 段落切分，query 的二字词组命中计分取 top_k"""
    grams = {query[i:i + 2] for i in range(len(query) - 1) if query[i:i + 2].strip()}
    hits: list[dict[str, Any]] = []
    for f in sorted(KNOWLEDGE_DIR.glob("*.md")):
        for para in re.split(r"\n(?=## )", f.read_text(encoding="utf-8")):
            para = para.strip()
            if not para:
                continue
            score = sum(1 for g in grams if g in para)
            if score:
                hits.append({"src": f.name, "text": para[:400], "score": score})
    hits.sort(key=lambda h: -h["score"])
    return hits[:top_k]

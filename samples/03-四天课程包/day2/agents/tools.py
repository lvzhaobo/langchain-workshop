"""Day 2 工具集 — RAG 检索 + Memory 读写"""
import os, json
from datetime import datetime
from pathlib import Path
from langchain_core.tools import tool

BASE_DIR = Path(__file__).parent.parent
KNOWLEDGE_DIR = BASE_DIR / "data" / "knowledge"
MEMORY_FILE = BASE_DIR / "memory.json"


def load_knowledge(query: str) -> list[str]:
    """简易关键词检索知识库"""
    results = []
    for f in KNOWLEDGE_DIR.glob("*.md"):
        text = f.read_text(encoding="utf-8")
        # 关键词匹配
        score = 0
        for kw in query.replace("？","").replace("?","").split():
            if kw in text:
                score += 1
        if score > 0:
            results.append((f.name, text[:300], score))
    results.sort(key=lambda x: x[2], reverse=True)
    return [r[1] for r in results[:3]]


@tool
def search_kb(query: str) -> str:
    """搜索 5G 基站运维知识库。参数：query 故障现象或关键词"""
    results = load_knowledge(query)
    if not results:
        return "知识库中未找到相关内容"
    return "\n\n---\n".join(results)


@tool
def write_memory(fact: str, category: str = "general") -> str:
    """将重要信息写入持久记忆。category: identity/preference/project/decision/general"""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    entry = {"category": category, "fact": fact, "time": ts}
    memories = []
    if MEMORY_FILE.exists():
        memories = json.loads(MEMORY_FILE.read_text())
    memories.append(entry)
    MEMORY_FILE.write_text(json.dumps(memories, ensure_ascii=False, indent=2))
    return f"已写入 [{category}]: {fact}"


@tool
def read_memory(query: str = "") -> str:
    """读取持久记忆"""
    if not MEMORY_FILE.exists():
        return "（暂无记忆）"
    memories = json.loads(MEMORY_FILE.read_text())
    if not memories:
        return "（暂无记忆）"
    lines = [f"[{m['category']}] {m['fact']} — {m['time']}" for m in memories[-20:]]
    return "\n".join(lines)

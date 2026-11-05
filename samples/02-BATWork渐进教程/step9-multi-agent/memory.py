"""
Step 4: Memory 记忆系统 — ChromaDB 向量存储 + SQLite 摘要

提供三个核心能力：
1. save_interaction() — 每次对话结束后保存摘要
2. recall() — 根据当前意图检索最相关的历史记忆
3. save_project_context() — 持久化项目级知识（约定/规范/偏好）
"""

from __future__ import annotations
import os
import json
import sqlite3
import hashlib
from datetime import datetime
from typing import Optional


class AgentMemory:
    """Agent 长期记忆管理器"""

    def __init__(self, persist_dir: str = "./memory_data"):
        self.persist_dir = persist_dir
        os.makedirs(persist_dir, exist_ok=True)

        # SQLite 存摘要
        db_path = os.path.join(persist_dir, "memory.db")
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self._init_db()

        # ChromaDB 存向量（可选，降级到纯 SQLite）
        self.chroma = None
        try:
            import chromadb
            self.chroma = chromadb.PersistentClient(
                path=os.path.join(persist_dir, "chroma")
            )
            self.collection = self.chroma.get_or_create_collection("agent_memory")
        except ImportError:
            print("⚠️ ChromaDB 未安装，使用纯 SQLite 模式（向量检索不可用）")

    def _init_db(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id TEXT PRIMARY KEY,
                session_id TEXT,
                intent TEXT,
                context TEXT,
                summary TEXT,
                created_at TEXT
            )
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS project_context (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TEXT
            )
        """)
        self.conn.commit()

    # ── 保存交互记录 ──

    def save_interaction(self, session_id: str, intent: str, context: str, summary: str):
        """每次 Agent 执行完毕后调用，保存对话摘要"""
        mem_id = hashlib.md5(f"{session_id}_{datetime.now().isoformat()}".encode()).hexdigest()[:16]
        now = datetime.now().isoformat()

        self.conn.execute(
            "INSERT INTO memories (id, session_id, intent, context, summary, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (mem_id, session_id, intent, context, summary, now)
        )
        self.conn.commit()

        # 向量化（ChromaDB 模式）
        if self.chroma:
            try:
                self.collection.add(
                    documents=[f"{intent}\n{summary}"],
                    metadatas=[{"session_id": session_id, "intent": intent}],
                    ids=[mem_id],
                )
            except Exception:
                pass

    # ── 检索相关记忆 ──

    def recall(self, query: str, top_k: int = 3) -> str:
        """根据当前意图检索最相关的历史记忆"""
        results = []

        # 方式 1: ChromaDB 向量检索
        if self.chroma:
            try:
                chroma_results = self.collection.query(
                    query_texts=[query], n_results=top_k
                )
                if chroma_results.get("documents") and chroma_results["documents"][0]:
                    for doc in chroma_results["documents"][0]:
                        results.append(f"📝 {doc[:300]}")
            except Exception:
                pass

        # 方式 2: SQLite 关键词兜底
        if len(results) < top_k:
            words = query.split()
            for word in words[:3]:
                if len(word) < 2:
                    continue
                rows = self.conn.execute(
                    "SELECT intent, summary FROM memories WHERE intent LIKE ? OR context LIKE ? ORDER BY created_at DESC LIMIT ?",
                    (f"%{word}%", f"%{word}%", top_k)
                ).fetchall()
                for row in rows:
                    entry = f"📝 {row[0][:200]}"
                    if entry not in results:
                        results.append(entry)

        if not results:
            return "（无相关历史记忆）"

        return "相关历史记忆:\n" + "\n".join(results[:top_k])

    # ── 项目上下文 ──

    def save_project_context(self, key: str, value: str):
        """保存项目级知识（约定、规范、偏好）"""
        now = datetime.now().isoformat()
        self.conn.execute(
            "INSERT OR REPLACE INTO project_context (key, value, updated_at) VALUES (?, ?, ?)",
            (key, value, now)
        )
        self.conn.commit()

    def get_project_context(self) -> str:
        """读取所有项目上下文"""
        rows = self.conn.execute(
            "SELECT key, value FROM project_context ORDER BY updated_at DESC"
        ).fetchall()
        if not rows:
            return ""
        lines = ["\n## 项目知识库:"]
        for key, value in rows:
            lines.append(f"- {key}: {value[:200]}")
        return "\n".join(lines)

    # ── 统计 ──

    def stats(self) -> dict:
        count = self.conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
        chroma_count = self.collection.count() if self.chroma else 0
        return {"sqlite_entries": count, "chroma_vectors": chroma_count}

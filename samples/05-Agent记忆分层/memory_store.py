"""
基于 LangGraph Store 的长期记忆封装

Store API 映射到三层记忆：
- store.put(namespace, key, value)  → 写入记忆
- store.search(namespace, query, limit) → 语义搜索（内置 embedding）
- store.get(namespace, key) → 精确获取
- store.delete(namespace, key) → 标记过时

命名空间设计：
- ("memories", "{user_id}")              → 用户级长期记忆事实
- ("profiles", "{user_id}")             → 用户画像
- ("sessions", "{user_id}", "{date}")   → 每日会话摘要（情节记忆）
- ("agent", "{key}")                    → Agent 自身身份记忆

使用方式：
    from langgraph.store.memory import InMemoryStore
    store = InMemoryStore()
    memory = MemoryStoreManager(store, "user_001")

    # 写入记忆
    await memory.remember("用户偏好 TypeScript", category="preference", score=8)

    # 搜索记忆
    results = await memory.recall("TypeScript 配置", limit=5)

    # 更新画像
    await memory.update_profile({"preferred_language": "TypeScript"})
"""

import math
import hashlib
from datetime import date, datetime, timedelta
from typing import Optional

from langgraph.store.base import BaseStore


class MemoryStoreManager:
    """LangGraph Store 的记忆管理封装"""

    def __init__(self, store: BaseStore, user_id: str = "default"):
        self.store = store
        self.user_id = user_id

    # ── 长期记忆 CRUD ─────────────────────────────────────

    def remember(
        self,
        content: str,
        category: str = "knowledge",
        score: float = 5.0,
        confidence: float = 0.5,
        user_id: Optional[str] = None,
    ) -> str:
        """
        写入一条长期记忆。

        自动去重：Jaccard 相似度 ≥ 0.7 视为重复，仅更新 recall_count。
        返回 fact_id。
        """
        uid = user_id or self.user_id
        fact_id = hashlib.md5(f"{uid}:{content}".encode()).hexdigest()[:16]
        namespace = ("memories", uid)

        # 检查是否已有相似事实（利用 Store 的语义搜索 + Jaccard 过滤）
        try:
            existing_items = self.store.search(
                namespace,
                query=content[:200],
                limit=3,
            )
            for item in existing_items:
                existing_content = item.value.get("content", "")
                similarity = self._jaccard_similarity(content, existing_content)
                if similarity >= 0.7:
                    # 更新已有事实的 recall_count 和置信度
                    old_val = item.value
                    old_val["recall_count"] = old_val.get("recall_count", 0) + 1
                    old_val["last_recalled_at"] = datetime.now().isoformat()
                    old_val["confidence"] = max(old_val.get("confidence", 0.5), confidence)
                    self.store.put(namespace, item.key, old_val)
                    return item.key
        except Exception:
            # InMemoryStore 的 search 在某些版本中可能不支持
            pass

        # 新事实
        fact = {
            "fact_id": fact_id,
            "content": content,
            "category": category,
            "score": score,
            "confidence": confidence,
            "recall_count": 0,
            "created_at": datetime.now().isoformat(),
            "last_recalled_at": None,
            "superseded_by": None,
        }
        self.store.put(namespace, fact_id, fact)
        return fact_id

    def recall(
        self,
        query: str,
        limit: int = 5,
        user_id: Optional[str] = None,
        min_score: float = 1.0,
    ) -> list[dict]:
        """
        语义搜索长期记忆。

        LangGraph Store 的 search() 内置 embedding 搜索。
        后处理：时间衰减评分 + 回忆次数加权。
        """
        uid = user_id or self.user_id
        namespace = ("memories", uid)

        try:
            results = self.store.search(
                namespace,
                query=query,
                limit=limit * 2,
            )
        except Exception:
            return []

        # 后过滤 + 排序
        scored = []
        for item in results:
            val = item.value
            raw_score = val.get("score", 5.0)
            if raw_score < min_score:
                continue

            # 时间衰减
            effective_score = self._decayed_score(val)
            # 被频繁回忆的加权
            recall_bonus = val.get("recall_count", 0) * 0.1
            final_score = effective_score * (1 + recall_bonus)

            scored.append({
                **val,
                "effective_score": round(final_score, 2),
            })

        scored.sort(key=lambda x: x["effective_score"], reverse=True)
        return scored[:limit]

    def forget(self, fact_id: str, user_id: Optional[str] = None):
        """标记事实为被替代（而非物理删除）"""
        uid = user_id or self.user_id
        namespace = ("memories", uid)
        try:
            existing = self.store.get(namespace, fact_id)
            if existing:
                val = existing.value
                val["superseded_by"] = "manual_forget"
                self.store.put(namespace, fact_id, val)
        except Exception:
            pass

    # ── 情节记忆（会话摘要）──────────────────────────────

    def save_session_summary(
        self,
        summary: str,
        session_id: str,
        user_id: Optional[str] = None,
    ):
        """保存会话摘要到情节记忆"""
        uid = user_id or self.user_id
        today = date.today().isoformat()
        namespace = ("sessions", uid, today)

        self.store.put(
            namespace,
            session_id,
            {
                "summary": summary,
                "session_id": session_id,
                "saved_at": datetime.now().isoformat(),
            },
        )

    # ── 画像管理 ──────────────────────────────────────────

    def get_profile(self, user_id: Optional[str] = None) -> dict:
        """获取用户完整画像"""
        uid = user_id or self.user_id
        namespace = ("profiles", uid)
        try:
            result = self.store.get(namespace, "profile")
            if result:
                return result.value
        except Exception:
            pass
        return {
            "user_id": uid,
            "name": "",
            "role": "",
            "skill_level": "intermediate",
            "traits": {},
            "facts": [],
            "interaction_count": 0,
            "first_seen": datetime.now().isoformat(),
            "last_seen": datetime.now().isoformat(),
        }

    def update_profile(
        self,
        trait_updates: dict,
        confidence: float = 0.5,
        user_id: Optional[str] = None,
    ):
        """
        更新用户画像特征。

        使用 EMA（指数移动平均）平滑：
        new_conf = old_conf × 0.7 + new_confidence × 0.3
        """
        uid = user_id or self.user_id
        namespace = ("profiles", uid)
        profile = self.get_profile(uid)

        for trait, value in trait_updates.items():
            if trait in profile["traits"]:
                old = profile["traits"][trait]
                alpha = 0.3  # EMA 权重
                profile["traits"][trait] = {
                    "value": value,
                    "confidence": round(
                        old.get("confidence", 0.5) * (1 - alpha) + confidence * alpha, 2
                    ),
                    "updated_at": datetime.now().isoformat(),
                }
            else:
                profile["traits"][trait] = {
                    "value": value,
                    "confidence": confidence,
                    "first_seen": datetime.now().isoformat(),
                    "updated_at": datetime.now().isoformat(),
                }

        profile["interaction_count"] = profile.get("interaction_count", 0) + 1
        profile["last_seen"] = datetime.now().isoformat()
        self.store.put(namespace, "profile", profile)

    def add_profile_fact(
        self,
        fact: str,
        confidence: float = 0.5,
        user_id: Optional[str] = None,
    ):
        """添加一条用户画像事实（带去重）"""
        uid = user_id or self.user_id
        profile = self.get_profile(uid)

        # Jaccard 去重
        fact_words = set(fact.lower().split())
        for existing in profile.get("facts", []):
            existing_words = set(existing.get("fact", "").lower().split())
            if fact_words and existing_words:
                jaccard = len(fact_words & existing_words) / len(fact_words | existing_words)
                if jaccard >= 0.7:
                    existing["confidence"] = max(existing.get("confidence", 0.5), confidence)
                    existing["last_verified"] = date.today().isoformat()
                    self.store.put(("profiles", uid), "profile", profile)
                    return

        # 新事实
        profile.setdefault("facts", []).append({
            "fact": fact,
            "confidence": confidence,
            "created": date.today().isoformat(),
            "last_verified": date.today().isoformat(),
        })
        # 保留最近 50 条事实
        profile["facts"] = profile["facts"][-50:]
        self.store.put(("profiles", uid), "profile", profile)

    # ── Agent 自身记忆 ────────────────────────────────────

    def set_agent_memory(self, key: str, value: dict):
        """设置 Agent 自身的持久记忆（如 Persona、规则）"""
        self.store.put(("agent", key), "current", value)

    def get_agent_memory(self, key: str) -> Optional[dict]:
        """获取 Agent 自身的持久记忆"""
        try:
            result = self.store.get(("agent", key), "current")
            return result.value if result else None
        except Exception:
            return None

    # ── 工具方法 ──────────────────────────────────────────

    def _decayed_score(self, fact: dict, half_life_days: int = 30) -> float:
        """计算时间衰减后的评分：score × e^(-λ × days_old)"""
        created_str = fact.get("created_at", "")
        if not created_str:
            return fact.get("score", 5.0)
        try:
            created = datetime.fromisoformat(created_str).date()
            days = (date.today() - created).days
            lam = math.log(2) / half_life_days
            return fact.get("score", 5.0) * math.exp(-lam * days)
        except (ValueError, TypeError):
            return fact.get("score", 5.0)

    @staticmethod
    def _jaccard_similarity(a: str, b: str) -> float:
        """计算两个字符串的词级 Jaccard 相似度"""
        set_a = set(a.lower().split())
        set_b = set(b.lower().split())
        if not set_a or not set_b:
            return 0.0
        return len(set_a & set_b) / len(set_a | set_b)

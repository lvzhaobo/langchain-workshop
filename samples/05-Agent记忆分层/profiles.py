"""
基于 LangGraph Store 的画像引擎

使用 Store 的 namespace 实现作用域隔离：
- ("profiles", "{user_id}")  → 用户画像
- ("entities", "{entity_type}") → 实体目录

画像更新策略：
1. EMA 平滑：新值以 0.3 权重融入旧值，避免单次对话波动
2. 置信度管理：< 0.5 暂存为候选，≥ 0.7 直接用于决策
3. 去重：Jaccard ≥ 0.7 视为重复事实，仅更新验证时间
"""

from datetime import datetime, date
from typing import Optional

from langgraph.store.base import BaseStore


class ProfileManager:
    """
    用户画像管理器。

    使用 LangGraph Store 存储，支持：
    - 多用户隔离（通过 user_id 区分 namespace）
    - 特征 EMA 动态更新
    - 置信度管理
    - 事实去重
    """

    def __init__(self, store: BaseStore):
        self.store = store

    def get_profile(self, user_id: str) -> dict:
        """获取用户完整画像"""
        try:
            result = self.store.get(("profiles", user_id), "profile")
            if result:
                return result.value
        except Exception:
            pass
        return self._empty_profile(user_id)

    def update_trait(
        self,
        user_id: str,
        trait: str,
        value,
        confidence: float = 0.5,
    ):
        """
        更新单个画像特征（带 EMA 平滑）。

        EMA 公式：new_conf = old_conf × 0.7 + new_confidence × 0.3
        这确保画像稳定进化，不因单次对话剧烈波动。
        """
        profile = self.get_profile(user_id)
        alpha = 0.3

        if trait in profile["traits"]:
            old = profile["traits"][trait]
            profile["traits"][trait] = {
                "value": value,
                "confidence": round(
                    old.get("confidence", 0.5) * (1 - alpha) + confidence * alpha, 2
                ),
                "history": old.get("history", []) + [
                    {
                        "value": old["value"],
                        "confidence": old["confidence"],
                        "until": datetime.now().isoformat(),
                    }
                ],
                "updated_at": datetime.now().isoformat(),
            }
        else:
            profile["traits"][trait] = {
                "value": value,
                "confidence": confidence,
                "first_seen": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "history": [],
            }

        profile["last_seen"] = datetime.now().isoformat()
        self.store.put(("profiles", user_id), "profile", profile)

    def add_fact(
        self,
        user_id: str,
        fact: str,
        confidence: float = 0.5,
    ):
        """
        添加一条用户画像事实（带去重）。

        Jaccard 相似度 ≥ 0.7 → 仅更新已有事实的置信度和验证时间。
        """
        profile = self.get_profile(user_id)

        # Jaccard 去重
        fact_words = set(fact.lower().split())
        for existing in profile.get("facts", []):
            existing_words = set(existing.get("fact", "").lower().split())
            if fact_words and existing_words:
                jaccard = len(fact_words & existing_words) / len(fact_words | existing_words)
                if jaccard >= 0.7:
                    existing["confidence"] = max(existing.get("confidence", 0.5), confidence)
                    existing["last_verified"] = date.today().isoformat()
                    self.store.put(("profiles", user_id), "profile", profile)
                    return

        # 新事实
        profile.setdefault("facts", []).append({
            "fact": fact,
            "confidence": confidence,
            "created": date.today().isoformat(),
            "last_verified": date.today().isoformat(),
        })

        # 保留最近 50 条
        profile["facts"] = profile["facts"][-50:]
        self.store.put(("profiles", user_id), "profile", profile)

    def get_relevant_context(self, user_id: str) -> str:
        """
        获取格式化的画像上下文，用于注入 SystemMessage。

        包含：
        - 高置信度特征（≥ 0.7）
        - 最近验证的事实（最新 10 条）
        """
        profile = self.get_profile(user_id)
        parts = []

        high_conf_traits = {
            k: v for k, v in profile.get("traits", {}).items()
            if v.get("confidence", 0) >= 0.7
        }
        if high_conf_traits:
            parts.append("## 用户画像（高置信度）")
            for trait, info in high_conf_traits.items():
                parts.append(f"- {trait}: {info['value']} (置信度: {info['confidence']:.2f})")

        verified_facts = [
            f for f in profile.get("facts", [])
            if f.get("confidence", 0) >= 0.7
        ]
        if verified_facts:
            parts.append("\n## 已知事实")
            for f in verified_facts[-10:]:
                parts.append(f"- {f['fact']}")

        return "\n".join(parts) if parts else ""

    @staticmethod
    def _empty_profile(user_id: str) -> dict:
        """创建一个空的用户画像"""
        now = datetime.now().isoformat()
        return {
            "user_id": user_id,
            "name": "",
            "role": "",
            "skill_level": "intermediate",
            "traits": {},
            "facts": [],
            "interaction_count": 0,
            "first_seen": now,
            "last_seen": now,
        }

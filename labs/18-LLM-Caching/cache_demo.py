"""LLM Caching 演示 — 相同查询不重复调 API

运行：python cache_demo.py
依赖：pip install langchain langchain-openai
"""
import os
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))  # 自动读取课程根目录 .env

import hashlib
import json
import time
from typing import Optional


# ═══ 简易缓存层 ═══
class SimpleLLMCache:
    """精确匹配 + TTL 过期的 LLM 缓存"""

    def __init__(self, ttl_seconds: int = 3600):
        self._cache: dict = {}
        self.ttl = ttl_seconds
        self.hits = 0
        self.misses = 0

    def _make_key(self, model: str, messages: list) -> str:
        content = json.dumps(
            {"model": model, "messages": messages},
            ensure_ascii=False,
            sort_keys=True,
        )
        return hashlib.sha256(content.encode()).hexdigest()

    def get(self, model: str, messages: list) -> Optional[str]:
        key = self._make_key(model, messages)
        if key in self._cache:
            timestamp, cached_response = self._cache[key]
            if time.time() - timestamp < self.ttl:
                self.hits += 1
                return cached_response
            del self._cache[key]
        self.misses += 1
        return None

    def set(self, model: str, messages: list, response: str):
        key = self._make_key(model, messages)
        self._cache[key] = (time.time(), response)

    @property
    def stats(self) -> dict:
        total = self.hits + self.misses
        hit_rate = (self.hits / total * 100) if total > 0 else 0
        return {
            "命中次数": self.hits,
            "未命中次数": self.misses,
            "总查询次数": total,
            "命中率": f"{hit_rate:.1f}%",
            "缓存条目数": len(self._cache),
            "TTL（秒）": self.ttl,
        }

    def clear(self):
        self._cache.clear()
        self.hits = 0
        self.misses = 0


# ═══ 带缓存的 LLM 调用 ═══
from langchain_openai import ChatOpenAI

API_KEY = os.getenv("AGENT_API_KEY", "REPLACE_ME_NO_KEY")
API_BASE = os.getenv("AGENT_API_BASE", "https://api.deepseek.com/v1")
MODEL = os.getenv("AGENT_MODEL", "deepseek-chat")

cache = SimpleLLMCache(ttl_seconds=1800)


def ask_llm_with_cache(user_message: str, model: str = MODEL) -> tuple:
    """带缓存的 LLM 调用。返回 (回答, 是否缓存命中)"""
    messages = [
        {"role": "system", "content": "你是 5G 基站排障专家助手。回答专业、准确，基于知识给出具体步骤。"},
        {"role": "user", "content": user_message},
    ]

    cached = cache.get(model, messages)
    if cached is not None:
        return cached, True

    llm = ChatOpenAI(
        model=model,
        temperature=0,
        api_key=API_KEY,
        base_url=API_BASE,
    )
    response = llm.invoke(user_message)
    result = response.content
    cache.set(model, messages, result)
    return result, False


# ═══ 演示 ═══
if __name__ == "__main__":
    # ── 模拟排障场景 ——
    # 三个同事分别问同一个设备的同一个问题
    PROMPT_A = """设备 DEV-0001（华为 AAU5613）当前告警：
- [P0] 基站退服：SCTP 链路中断导致退服
请给出详细的排查步骤。"""

    PROMPT_B = """设备 DEV-0002（中兴 ZXRAN）当前告警：
- [P1] 光模块光功率异常：收光功率 -28dBm，低于门限
请给出排查建议。"""

    PROMPT_C = "光模块无光告警是什么原因？"

    queries = [
        ("同事A 问 DEV-0001", PROMPT_A),
        ("同事B 也问 DEV-0001", PROMPT_A),  # ← 相同！
        ("同事C 问 DEV-0002", PROMPT_B),
        ("同事A 又问 DEV-0001", PROMPT_A),  # ← 相同！
        ("同事B 问光模块", PROMPT_C),
        ("同事C 也问光模块", PROMPT_C),     # ← 相同！
    ]

    results = []
    for i, (label, prompt) in enumerate(queries, 1):
        print(f"\n{'='*60}")
        print(f"第 {i} 次调用：{label}")

        # 估算 Token
        start = time.time()
        reply, hit = ask_llm_with_cache(prompt)
        elapsed_ms = (time.time() - start) * 1000

        estimated_tokens = 0 if hit else len(prompt) + len(reply)

        marker = "🟢 CACHE HIT" if hit else "🔴 LLM CALL"
        print(f"  {marker}")
        if hit:
            print(f"  延迟: {elapsed_ms:.1f}ms（内存读取）")
            print(f"  Token 消耗: 0（零成本）")
        else:
            print(f"  延迟: {elapsed_ms:.1f}ms（API 调用）")
            print(f"  Token 估算: ~{estimated_tokens}")
        print(f"  回答预览: {reply[:80]}...")

        results.append({
            "标签": label,
            "缓存命中": hit,
            "Token消耗": estimated_tokens,
            "延迟(ms)": round(elapsed_ms, 1),
        })

    # ── 汇总对比 ──
    print(f"\n\n{'='*70}")
    print("对比：有缓存 vs 无缓存")
    print(f"{'='*70}")

    total_calls = len(queries)
    total_without_cache = sum(r["Token消耗"] if not r["缓存命中"] else 350 for r in results)  # 估算无缓存时全部调 API
    total_with_cache = sum(r["Token消耗"] for r in results)

    print(f"\n无缓存：{total_calls} 次全部调 LLM → ~{total_without_cache} tokens")
    print(f"有缓存：{total_calls} 次（{cache.stats['命中次数']} 次命中）→ ~{total_with_cache} tokens")
    print(f"节省 Token: {total_without_cache - total_with_cache} (~{(total_without_cache - total_with_cache) / max(total_without_cache, 1) * 100:.0f}%)")

    print(f"\n📊 缓存统计：")
    for k, v in cache.stats.items():
        print(f"  {k}: {v}")

    print(f"\n📌 关键发现：")
    print(f"  - 相同 Prompt 第二次查询：零 Token、零 API 费用")
    print(f"  - 不同 Prompt：正常走 LLM，互不影响")
    print(f"  - 缓存命中率取决于查询模式——排障场景下同事间问题重复率高，缓存收益大")
    print(f"  - TTL 控制数据新鲜度——设备分析设 10min，通用问答设 1h")

    # ── 缓存条目展示 ──
    print(f"\n📦 当前缓存条目（{cache.stats['缓存条目数']} 条）：")
    for key, (ts, resp) in cache._cache.items():
        remaining = max(0, cache.ttl - (time.time() - ts))
        print(f"  key={key[:12]}...  剩余TTL={remaining:.0f}s  回答长度={len(resp)}字")

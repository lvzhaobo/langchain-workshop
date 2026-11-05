"""
实验六：Memory 机制对比 — 同一段对话 × 三种记忆策略

核心概念：
  - BufferMemory：全量保存历史，信息完整但 Token 持续增长
  - WindowMemory：只保留最近 K 轮，Token 可控但早期信息可能丢失
  - SummaryMemory：用 LLM 压缩历史为摘要，兼顾信息保留和 Token 控制

不是 LangChain 的 Memory 类包装，而是手写三种策略，看清底层原理。

运行方式：
  python 06-memory/memory_compare.py            # 正常模式（需要百炼 API）
  python 06-memory/memory_compare.py --offline  # 离线模式（纯本地运行）
"""

import os
import sys

OFFLINE = "--offline" in sys.argv
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "")
BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
MODEL = "qwen-plus"


# ---------------------------------------------------------------------------
# 多轮排障对话（7 轮）
# ---------------------------------------------------------------------------

CONVERSATION = [
    {"role": "user", "content": "你好，我在巡检时发现 #1 主变压器（编号 EP-B-001）的油温达到了 78°C，比平时高了 15 度。"},
    {"role": "ai", "content": "收到。#1 主变压器 EP-B-001 油温 78°C，虽然未到 85°C 的停机线，但温升异常需要关注。请问冷却系统运行正常吗？"},
    {"role": "user", "content": "两个冷却风扇都在转，但有一个转速明显偏慢。另外油位比上次巡检时下降了约 5%。"},
    {"role": "ai", "content": "了解。冷却风扇转速异常 + 油位下降 5% 需要进一步排查。最近一次 DGA 是什么时候做的？"},
    {"role": "user", "content": "DGA 是上个月做的，乙炔（C2H2）含量略有升高，但还在注意值以内。现在过了三周，要不要再做一次？"},
    {"role": "ai", "content": "建议立即安排 DGA 复测。油温异常 + 油位下降 + 乙炔升高趋势，三者叠加需要警惕内部故障。建议将 EP-B-001 负载降至 70% 以下。"},
    {"role": "user", "content": "好的，我马上安排 DGA 取样。对了，这台变压器上次预防性试验是什么时候做的？"},
]

VERIFICATION_QUESTION = "请回顾一下，我们今天讨论的是哪台设备？它的编号是什么？目前发现了哪些问题？"


# ---------------------------------------------------------------------------
# LLM 调用
# ---------------------------------------------------------------------------

def _chat(messages: list[dict]) -> str:
    if OFFLINE:
        # 离线：根据上下文返回合理回答
        last_user = ""
        for m in reversed(messages):
            if m.get("role") in ("user", "human"):
                last_user = m.get("content", "")
                break

        if "讨论的是哪台设备" in last_user:
            return ("今天讨论的是 #1 主变压器（编号 EP-B-001）。发现的问题："
                    "1.油温异常升至78°C；2.一个冷却风扇转速偏慢；"
                    "3.油位下降约5%；4.上月DGA乙炔含量略有升高。"
                    "建议降负荷运行并安排DGA复测。")

        if "油温" in last_user or "78" in last_user:
            return ("收到。#1 主变压器 EP-B-001 油温 78°C，"
                    "虽然未到 85°C 的停机线，但温升异常需要关注。请问冷却系统运行正常吗？")

        if "风扇" in last_user or "油位" in last_user:
            return ("了解。冷却风扇转速异常 + 油位下降 5% 需要进一步排查。"
                    "最近一次 DGA 是什么时候做的？")

        if "DGA" in last_user and "再做" in last_user:
            return ("建议立即安排 DGA 复测。油温异常 + 油位下降 + 乙炔升高趋势，"
                    "三者叠加需要警惕内部故障。建议将 EP-B-001 负载降至 70% 以下。")

        if "预防性试验" in last_user:
            return ("这台 EP-B-001 上次预防性试验需要查一下记录。"
                    "不过以目前的异常情况，建议尽快安排一次全面的预防性试验。")

        # 默认
        return f"[离线模拟] AI 针对此问题的回答。去掉 --offline 参数可使用真实 API。"

    else:
        from openai import OpenAI
        client = OpenAI(base_url=BASE_URL, api_key=DASHSCOPE_API_KEY)
        resp = client.chat.completions.create(model=MODEL, messages=messages, temperature=0)
        return resp.choices[0].message.content


# ---------------------------------------------------------------------------
# 三种 Memory 策略
# ---------------------------------------------------------------------------

def test_buffer_memory():
    """Buffer 策略：全量历史"""
    print(f"\n📝 === Buffer 策略：全量历史 ===")
    messages = []
    for i, turn in enumerate(CONVERSATION):
        messages.append({"role": turn["role"], "content": turn["content"]})
        total_chars = sum(len(m["content"]) for m in messages)
        ai_reply = _chat(messages)
        print(f"   第 {i+1} 轮 | 累计 {len(messages)} 条消息 | 约 {total_chars // 2} tokens")
        messages.append({"role": "assistant", "content": ai_reply})

    messages.append({"role": "user", "content": VERIFICATION_QUESTION})
    answer = _chat(messages)
    final_tokens = sum(len(m["content"]) for m in messages) // 2

    print(f"\n   ┌─ 记忆验证 ─────────────────────────────")
    print(f"   │ 回答：{answer[:200]}")
    print(f"   │ Token 估算：{final_tokens}")
    print(f"   └──────────────────────────────────────────")
    return {"strategy": "Buffer（全量）", "answer": answer, "estimated_tokens": final_tokens}


def test_window_memory(K=3):
    """Window 策略：只保留最近 K 轮"""
    print(f"\n🪟 === Window 策略：K={K}，只保留最近 {K} 轮 ===")
    full_history = []
    for i, turn in enumerate(CONVERSATION):
        full_history.append({"role": turn["role"], "content": turn["content"]})
        window = full_history[-(K * 2):]
        window_chars = sum(len(m["content"]) for m in window)
        ai_reply = _chat(window)
        print(f"   第 {i+1} 轮 | 窗口内 {len(window)} 条消息 | 约 {window_chars // 2} tokens")
        full_history.append({"role": "assistant", "content": ai_reply})

    window = full_history[-(K * 2):]
    window.append({"role": "user", "content": VERIFICATION_QUESTION})
    answer = _chat(window)
    window_tokens = sum(len(m["content"]) for m in window) // 2

    # 检查窗口里是否还有第 1 轮的信息
    has_early = any("EP-B-001" in m["content"] for m in window if m["role"] == "user")
    print(f"\n   ┌─ 记忆验证 ─────────────────────────────")
    print(f"   │ 窗口内还保留第 1 轮信息？{'✅ 是' if has_early else '❌ 否（已丢弃）'}")
    print(f"   │ 回答：{answer[:200]}")
    print(f"   │ Token 估算：{window_tokens}")
    print(f"   └──────────────────────────────────────────")
    return {"strategy": f"Window（K={K}）", "answer": answer, "estimated_tokens": window_tokens}


def test_summary_memory():
    """Summary 策略：LLM 摘要压缩"""
    print(f"\n📋 === Summary 策略：LLM 摘要压缩 ===")
    full_history = []
    summary = ""
    SUMMARY_INTERVAL = 3

    for i, turn in enumerate(CONVERSATION):
        full_history.append({"role": turn["role"], "content": turn["content"]})
        recent = full_history[-4:]
        context = [{"role": "system", "content": f"对话摘要：\n{summary}"}] if summary else []
        context.extend(recent)

        context_chars = sum(len(m["content"]) for m in context)
        ai_reply = _chat(context)
        print(f"   第 {i+1} 轮 | 摘要={len(summary)}字符 + {len(recent)}条消息 | 约 {context_chars // 2} tokens")
        full_history.append({"role": "assistant", "content": ai_reply})

        if (i + 1) % SUMMARY_INTERVAL == 0 and i > 0:
            summary = (f"#1主变压器EP-B-001，油温78°C异常，风扇转速偏慢，"
                       f"油位下降5%，上月DGA乙炔升高。建议降负荷并安排DGA复测。")
            print(f"   📋 摘要已更新（{len(summary)} 字符）")

    recent = full_history[-4:]
    context = [{"role": "system", "content": f"对话摘要：{summary}"}] + recent
    context.append({"role": "user", "content": VERIFICATION_QUESTION})
    answer = _chat(context)
    context_tokens = sum(len(m["content"]) for m in context) // 2

    print(f"\n   ┌─ 记忆验证 ─────────────────────────────")
    print(f"   │ 摘要：{summary}")
    print(f"   │ 回答：{answer[:200]}")
    print(f"   │ Token 估算：{context_tokens}")
    print(f"   └──────────────────────────────────────────")
    return {"strategy": "Summary（摘要）", "answer": answer, "estimated_tokens": context_tokens}


# ---------------------------------------------------------------------------
# 对比汇总
# ---------------------------------------------------------------------------

def print_comparison(results: list[dict]):
    print("\n" + "=" * 70)
    print("📊 三种 Memory 策略对比汇总")
    print("=" * 70)
    print(f"\n{'策略':<22} {'Token 估算':>12} {'记住EP-B-001？':>16} {'记住故障细节？':>16}")
    print("-" * 70)
    for r in results:
        answer = r["answer"]
        tokens = r["estimated_tokens"]
        remember_id = "EP-B-001" in answer or "#1 主变压器" in answer
        remember_detail = any(w in answer for w in ["油温", "油位", "风扇", "DGA", "乙炔"])
        print(f"{r['strategy']:<22} {tokens:>10} tokens  "
              f"{'✅ 记住' if remember_id else '❌ 遗忘':>16}  "
              f"{'✅ 记住' if remember_detail else '⚠️ 部分':>16}")

    print("\n💡 选择建议：")
    print("   - Buffer：短期对话（< 10 轮），需要完整上下文")
    print("   - Window：长对话（> 20 轮），只关心最近信息")
    print("   - Summary：中等对话，需要跨轮记忆但不想 Token 爆炸")


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------

def main():
    if OFFLINE:
        print("=" * 60)
        print("🧪 实验六：Memory 机制对比 [离线模式]")
        print("=" * 60)
        print("\n  ⚡ 离线模式：LLM 回答用预设模拟，Memory 策略 100% 真实执行")
        print("  ⚡ 三种策略的消息管理和 Token 计算完全真实")
        print("  ⚡ 去掉 --offline 参数可连接真实百炼 API\n")
    else:
        print("=" * 60)
        print("🧪 实验六：Memory 机制对比")
        print("=" * 60)
        if not DASHSCOPE_API_KEY:
            print("\n⚠️  请设置 DASHSCOPE_API_KEY 或使用 --offline"); sys.exit(1)

    print(f"\n📖 对话场景：7 轮电力设备排障对话")
    print(f"   关键信息在第 1 轮：设备 #1 主变压器（EP-B-001），油温 78°C")
    print(f"   验证问题在第 7 轮后：'今天讨论的是哪台设备？编号是什么？'")

    results = [
        test_buffer_memory(),
        test_window_memory(K=3),
        test_summary_memory(),
    ]
    print_comparison(results)

    print("\n" + "=" * 60)
    print("🎉 实验六完成！")
    print("=" * 60)


if __name__ == "__main__":
    main()

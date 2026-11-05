"""Memory 三种策略对比 — 纯 Python 模拟

Buffer：全记 | Window：只记最近K轮 | Summary：旧消息自动摘要
模拟 Token 消耗和信息保留，无需 API 调用。

运行：python3 memory_compare.py
"""

# ── 7 轮对话 ──
CONVERSATION = [
    ("我负责北京市朝阳区望京SOHO站点的运维工作。", "好的，已记录：望京SOHO站点。"),
    ("我们站点有多少台告警设备？", "该站点目前 3 台设备在告警。"),
    ("华为 AAU5613 运行怎么样？", "AAU5613 运行中，无告警，各项指标正常。"),
    ("温度过高告警一般怎么处理？", "建议检查散热片积灰、风扇转速、环境温度。"),
    ("最常用的设备型号是什么？", "华为 AAU5613 占比最高。"),
    ("下午要开会吗？", "三点有周会。"),
    ("我们一开始说的是哪个站点？", ""),  # ← 第7轮：验证记忆
]


# ═══ 策略 1：Buffer — 全记 ═══
def run_buffer(conversation):
    print("\n" + "=" * 60)
    print("策略 1: Buffer（全记）— 保留全部对话历史")
    print("=" * 60)

    history = []
    total_tokens = 0

    for i, (user_msg, expected) in enumerate(conversation, 1):
        # 拼接全部历史
        context = "\n".join([f"用户：{u}\n助手：{a}" for u, a in history])

        # 模拟 Agent 回答（最后一条验证记忆）
        if isinstance(expected, str) and expected:
            reply = expected
        elif i == 7:
            reply = "望京SOHO站点" if "望京SOHO" in context else "不记得了"
        else:
            reply = "收到。"

        history.append((user_msg, reply))

        # Token 估算（中文 1字≈0.5 token）
        input_tokens = len(context) // 2 + len(user_msg) // 2
        output_tokens = len(reply) // 2
        total_tokens += input_tokens + output_tokens

        marker = " ← 关键验证" if i == 7 else ""
        print(f"\n第{i}轮: {user_msg}")
        print(f"      → {reply}{marker}")
        print(f"      本轮累计Token: ~{total_tokens}")

        if i == 7:
            remembered = "望京" in reply
            icon = "✅ 记住了" if remembered else "❌ 忘记了"
            print(f"\n记忆验证: {icon} | 总Token: ~{total_tokens}")

    return total_tokens, "望京" in reply


# ═══ 策略 2：Window — 只记最近 K 轮 ═══
def run_window(conversation, k=4):
    print("\n" + "=" * 60)
    print(f"策略 2: Window（K={k}）— 只保留最近 {k} 轮对话")
    print("=" * 60)

    history = []
    total_tokens = 0

    for i, (user_msg, expected) in enumerate(conversation, 1):
        # 只取最近 K 轮
        recent = history[-k:] if k > 0 else []
        context = "\n".join([f"用户：{u}\n助手：{a}" for u, a in recent])

        if isinstance(expected, str) and expected:
            reply = expected
        elif i == 7:
            reply = "望京SOHO站点" if "望京SOHO" in context else "不记得了，历史已被截断。"
        else:
            reply = "收到。"

        history.append((user_msg, reply))

        input_tokens = len(context) // 2 + len(user_msg) // 2
        output_tokens = len(reply) // 2
        total_tokens += input_tokens + output_tokens

        # 标记哪些历史被丢弃了
        discarded = len(history) - k if len(history) > k else 0
        discard_note = f" [已丢弃{discarded}轮]" if discarded > 0 else ""

        marker = " ← 关键验证" if i == 7 else ""
        print(f"\n第{i}轮: {user_msg}{discard_note}")
        print(f"      → {reply}{marker}")
        print(f"      本轮累计Token: ~{total_tokens}")

        if i == 7:
            remembered = "望京" in reply
            icon = "✅ 记住了" if remembered else "❌ 忘记了"
            print(f"\n记忆验证: {icon} | 总Token: ~{total_tokens}")

    return total_tokens, "望京" in reply


# ═══ 策略 3：Summary — 自动摘要 ═══
def run_summary(conversation, summary_trigger=4):
    print("\n" + "=" * 60)
    print(f"策略 3: Summary（摘要触发={summary_trigger}轮）— 旧消息自动压缩")
    print("=" * 60)

    history = []
    summary = ""
    total_tokens = 0
    summarized_rounds = set()

    for i, (user_msg, expected) in enumerate(conversation, 1):
        # 构建上下文：摘要 + 未压缩的最近消息
        recent_start = i - (i % summary_trigger) if i >= summary_trigger else 0
        recent = history[recent_start:]
        context = f"[摘要] {summary}\n\n" if summary else ""
        context += "\n".join([f"用户：{u}\n助手：{a}" for u, a in recent])

        if isinstance(expected, str) and expected:
            reply = expected
        elif i == 7:
            reply = "望京SOHO站点" if "望京SOHO" in context else "不记得了"
        else:
            reply = "收到。"

        history.append((user_msg, reply))

        # 触发摘要：历史超过阈值时压缩最旧的消息
        if len(history) > summary_trigger:
            old_count = len(history) - summary_trigger
            old = history[:old_count]
            if old and old_count > len(summarized_rounds):
                key_info = []
                for u, a in old:
                    if "望京" in u or "望京" in a:
                        key_info.append("运维负责望京SOHO站点")
                    if "AAU" in u or "AAU" in a:
                        key_info.append("讨论过AAU5613设备")
                summary = "摘要：" + "；".join(key_info) if key_info else "无关键信息。"
                summarized_rounds.update(range(old_count))
                print(f"\n      ⚡ 触发摘要：将前 {old_count} 轮压缩为 → {summary[:50]}")

        input_tokens = len(context) // 2 + len(user_msg) // 2
        output_tokens = len(reply) // 2
        total_tokens += input_tokens + output_tokens

        marker = " ← 关键验证" if i == 7 else ""
        print(f"\n第{i}轮: {user_msg}")
        if summary and i >= summary_trigger:
            print(f"      上下文: [摘要]{summary[:60]}... + 最近{len(recent)}轮")
        print(f"      → {reply}{marker}")
        print(f"      本轮累计Token: ~{total_tokens}")

        if i == 7:
            remembered = "望京" in reply
            icon = "✅ 记住了" if remembered else "❌ 忘记了"
            print(f"\n记忆验证: {icon} | 总Token: ~{total_tokens}")

    return total_tokens, "望京" in reply


# ═══════════════════════════════════════════════════════
if __name__ == "__main__":
    print("Memory 策略对比实验")
    print()
    print("模拟一段 7 轮运维对话：")
    print("  第1轮告知站点 → 中间5轮各种问题 → 第7轮问'是哪个站点'")
    print()

    results = {}
    tokens, ok = run_buffer(CONVERSATION)
    results["Buffer(全记)"] = (tokens, ok)

    tokens, ok = run_window(CONVERSATION, k=4)
    results["Window(K=4)"] = (tokens, ok)

    tokens, ok = run_summary(CONVERSATION)
    results["Summary(摘要)"] = (tokens, ok)

    # ── 对比总结 ──
    print(f"\n\n{'='*60}")
    print("三种策略对比总结")
    print(f"{'='*60}")
    print(f"{'策略':<18} {'Token消耗':>10} {'第7轮记忆':>12} {'适用场景'}")
    print(f"{'-'*60}")
    for name, (tokens, remembered) in results.items():
        icon = "✅ 记住" if remembered else "❌ 忘记"
        if "Buffer" in name:
            scene = "短对话、客服咨询"
        elif "Window" in name:
            scene = "只看最近几轮、实时问答"
        else:
            scene = "长对话、最佳性价比"
        print(f"{name:<18} {'~'+str(tokens):>10} {icon:>12}   {scene}")

    print(f"\n结论:")
    print(f"  Buffer：信息最全，Token最贵——适合短对话")
    print(f"  Window：Token恒定，旧信息丢失——K值决定记忆窗口")
    print(f"  Summary：既省Token又保留关键信息——生产环境首选")

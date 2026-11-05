"""Day4 Prompt A/B 对比 — 同一任务，两版 Prompt，对比输出稳定性

运行: python prompt_test.py
"""
import json

# 测试用例
TEST_CASES = [
    "查 DEV-0001 的状态",
    "DEV-0002 有什么告警",
    "光模块功率异常怎么处理",
    "P0 告警需要多久响应",
]

# Prompt A（简洁版）
PROMPT_A = "你是网络故障排查助手。回答简洁，不超过 100 字。"

# Prompt B（详细版）
PROMPT_B = """你是 5G 基站运维专家，精通 AAU/BBU/RU 设备。
回答规则：
1. 先给结论（一句话）
2. 再列步骤（最多 3 步）
3. 不确定时直言不知道，不要编造。
回答不超过 150 字。"""


def evaluate(prompt_name: str, prompt: str) -> dict:
    """模拟评测（生产环境需调 LLM 跑 4 条用例）"""
    scores = {"format": 0.0, "conciseness": 0.0, "actionable": 0.0}

    if "先给结论" in prompt and "列步骤" in prompt:
        scores["format"] = 0.9   # 明确格式要求 → 格式更稳定
    scores["conciseness"] = 0.8 if "不超过" in prompt else 0.5
    scores["actionable"] = 0.85 if "不要编造" in prompt else 0.4

    return scores


print("=" * 60)
print("Day4 Prompt A/B 对比测试")
print("=" * 60)
print(f"\n测试用例数: {len(TEST_CASES)}")
print(f"  1. {TEST_CASES[0]}")
print(f"  2. {TEST_CASES[1]}")
print(f"  3. {TEST_CASES[2]}")
print(f"  4. {TEST_CASES[3]}")

scores_a = evaluate("Prompt A", PROMPT_A)
scores_b = evaluate("Prompt B", PROMPT_B)

print(f"\n{'指标':<12} {'Prompt A':>10} {'Prompt B':>10} {'提升':>8}")
print("-" * 44)
for key in scores_a:
    diff = scores_b[key] - scores_a[key]
    print(f"{key:<12} {scores_a[key]:>10.0%} {scores_b[key]:>10.0%} {diff:>+8.0%}")

print(f"\n结论: Prompt B 更优（格式约束 + 防幻觉 + 字数限制）")
print(f"建议: 生产环境用 Prompt B，通过 LangSmith Trace 持续监控效果")

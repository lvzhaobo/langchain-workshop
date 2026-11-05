"""
sample-19：Agent 评估体系 — RAGAS 评测 + Prompt A/B 对比

评估 Agent 质量的三个维度：
  1. RAGAS：检索增强生成的自动评测（忠实度、相关性、精确度、召回率）
  2. Prompt A/B：同一问题，两版 Prompt 对比输出稳定性
  3. CI 集成：把评测加入自动化流水线

安装：pip install ragas datasets pandas（可选，概念演示不需要）
"""

import os, json, time
from dotenv import load_dotenv
load_dotenv()

print("=" * 60)
print("Agent 评估体系 — 三个维度量化 Agent 质量")
print("=" * 60)

# ══════════════════════════════════════════════════════════════
# Part 1: RAGAS — 检索增强生成自动评测
# ══════════════════════════════════════════════════════════════

print("\n1. RAGAS — 四个指标自动评测 RAG 质量\n")

print("""
  RAGAS（Retrieval Augmented Generation Assessment）：
  无需人工标注，自动计算四个指标。

  ┌──────────────┬──────────────────────────────────────┐
  │ 指标          │ 衡量什么                              │
  ├──────────────┼──────────────────────────────────────┤
  │ Faithfulness │ 生成内容是否基于检索到的文档（幻觉？） │
  │ Answer Relev │ 回答是否切题                          │
  │ Context Prec │ 检索到的文档是否精准                   │
  │ Context Rec  │ 是否漏掉了关键文档                     │
  └──────────────┴──────────────────────────────────────┘
""")

# 模拟评测数据
EVAL_DATA = [
    {"question": "光模块收光功率-30dBm怎么处理？",
     "answer": "收光功率-30dBm为严重故障，建议检查光纤接头、更换光模块。",
     "contexts": ["收光功率低于-28dBm为异常，低于-30dBm为严重。常见原因：光纤脏污、模块老化。"],
     "ground_truth": "检查光纤接头、清洁端面、测量对端发光功率、更换光模块"},
    {"question": "P1告警多久处理？",
     "answer": "P1告警需要在2小时内处理。",
     "contexts": ["P0：立即处理；P1：2小时内；P2：24小时内"],
     "ground_truth": "P1告警2小时内处理"},
    {"question": "AAU温度多少正常？",
     "answer": "AAU工作温度范围是-40°C至+55°C。",
     "contexts": ["AAU正常工作温度：-40°C至+55°C，发射功率不超过40W"],
     "ground_truth": "-40°C到+55°C"},
]

print("  评测数据集（模拟）：")
for i, item in enumerate(EVAL_DATA):
    print(f"  [{i+1}] Q: {item['question']}")
    print(f"      A: {item['answer'][:50]}...")
    print(f"      C: {item['contexts'][0][:50]}...")
    print()

# 简单评测逻辑（不用 ragas 包也能跑）
def simple_eval(item):
    """简单的评测：检查回答中的关键事实是否来自上下文"""
    ctx = item["contexts"][0]
    ans = item["answer"]
    # 忠实度：回答的核心事实在上下文中出现了多少
    facts_in_ctx = sum(1 for w in ["-30dBm","-28dBm","严重","光纤","模块","老化","检查"] if w in ans and w in ctx)
    facts_total = sum(1 for w in ["-30dBm","-28dBm","严重","光纤","模块","老化","检查"] if w in ans)
    faithfulness = facts_in_ctx / max(facts_total, 1)
    # 相关性：回答是否解决用户问题
    relevance = 0.85 if len(ans) > 10 else 0.5
    return {"faithfulness": round(faithfulness, 2), "relevance": round(relevance, 2)}

print("  简易评测结果：")
scores = []
for item in EVAL_DATA:
    s = simple_eval(item)
    scores.append(s)
    print(f"  {item['question'][:20]}... → faithfulness={s['faithfulness']}, relevance={s['relevance']}")

avg_f = sum(s["faithfulness"] for s in scores) / len(scores)
avg_r = sum(s["relevance"] for s in scores) / len(scores)
print(f"\n  平均: faithfulness={avg_f:.2f}, relevance={avg_r:.2f}")


# ══════════════════════════════════════════════════════════════
# Part 2: Prompt A/B 对比
# ══════════════════════════════════════════════════════════════

print("\n" + "=" * 60)
print("2. Prompt A/B 对比 — 哪版 Prompt 更稳定？")
print("=" * 60)

print("""
  同一任务，两版 Prompt 分别跑 12 条测试用例，对比输出质量。

  Prompt A（简洁版）：          Prompt B（详细版）：
  "你是网络故障排查助手。"      "你是 5G 基站运维专家，精通 AAU/BBU/RU。
                                 回答时先给结论，再列步骤。
                                 不确定时直言不知道，不要编造。"

  评估维度：
  ┌──────────────┬────────────────────────────────────┐
  │ 格式正确率    │ 是否按要求格式输出                  │
  │ 幻觉率        │ 是否编造了知识库没有的信息           │
  │ 覆盖率        │ 是否覆盖了问题的关键点              │
  │ 可操作度      │ 给出的建议是否具体可执行            │
  └──────────────┬────────────────────────────────────┘
""")

# 模拟 A/B 结果
AB_RESULTS = {
    "Prompt A": {"format": 0.72, "hallucination": 0.18, "coverage": 0.65, "actionable": 0.58},
    "Prompt B": {"format": 0.94, "hallucination": 0.06, "coverage": 0.82, "actionable": 0.79},
}

print("  模拟 A/B 对比结果（12 条用例 × 双版本）：")
for name, metrics in AB_RESULTS.items():
    bars = "".join("█" * int(v * 10) for v in metrics.values())
    print(f"  {name}: 格式={metrics['format']:.0%} 幻觉={metrics['hallucination']:.0%} "
          f"覆盖={metrics['coverage']:.0%} 可操作={metrics['actionable']:.0%}  {bars}")

better = "Prompt B" if AB_RESULTS["Prompt B"]["hallucination"] < AB_RESULTS["Prompt A"]["hallucination"] else "Prompt A"
print(f"\n  结论: {better} 更优（幻觉率更低、格式更稳定）")
print(f"  建议: 用 {better} 作为生产 Prompt，持续监控 LangSmith Trace")


# ══════════════════════════════════════════════════════════════
# Part 3: CI 集成
# ══════════════════════════════════════════════════════════════

print("\n" + "=" * 60)
print("3. CI 集成 — 把评测加入自动化流水线")
print("=" * 60)

print("""
  CI Pipeline（每次代码变更自动跑）：

  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
  │ 代码提交  │ → │ 跑评测集  │ → │ 对比基线  │ → │ 通过/拦截 │
  └──────────┘    └──────────┘    └──────────┘    └──────────┘
                   15 条用例        A/B 对比       阈值检查

  GitHub Actions 示例：
  ```yaml
  - name: Agent Evaluation
    run: |
      python eval.py --test-suite tests/eval_cases.json
      python eval.py --compare-baseline
    # faithfulness < 0.7 → CI 拦截，禁止合并
  ```

  关键阈值：
  - Faithfulness < 0.7  → 🚫 拦截（答案不基于知识库）
  - Hallucination > 0.15 → ⚠️  警告（幻觉率上升）
  - Format < 0.8         → ⚠️  警告（格式不稳定）
""")


# ══════════════════════════════════════════════════════════════
# Summary
# ══════════════════════════════════════════════════════════════

print("=" * 60)
print("评估体系 × 课程对照")
print("=" * 60)

print("""
  课程内容              评估体系落地
  ──────────────────────────────────────────────
  sample-14 RAG  → RAGAS 自动评测（faithfulness + relevance）
  sample-6 Agent  → Prompt A/B 对比（稳定性量化）
  Day 4 SDD       → CI 集成评测流水线
  LangSmith        → Trace + 评测结果可视化

  学员要能回答：
  1. 怎么证明 Agent 的回答质量？（RAGAS 四个指标）
  2. 改了 Prompt 怎么知道是变好还是变坏？（A/B 对比）
  3. 怎么防止上线后质量下降？（CI 拦截阈值）
""")

print("✅ sample-19 完成")

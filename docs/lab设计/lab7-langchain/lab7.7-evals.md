# Lab 7.7 — Evals 评测体系

> 设计评测数据集，写脚本自动跑评测，用指标量化 Agent 的质量——每次改完 Agent 后跑一遍，看分数涨了还是跌了。

---

## 🎯 实验目标

1. 理解评测驱动迭代的工作方式：每次改 Agent 配置后跑评测，数据说话
2. 设计手工标注的评测用例（问题 + 期望答案 + 来源文档）
3. 实现意图识别准确率、检索召回率、答案质量三个评测指标
4. 跑一遍评测，找到失败用例并分析原因

---

## 📋 前置条件

| 序号 | 条件 | 说明 |
|------|------|------|
| 1 | Python 3.9+ | 运行脚本 |
| 2 | 百炼 API Key | LLM 调用需要 |
| 3 | 完成 Lab 7.2 | 有可用的 RAG 管道 |
| 4 | 安装依赖 | `pip install langchain langchain-openai` |

---

## 📦 实验数据

| 文件路径 | 用途 | 说明 |
|----------|------|------|
| `demo/eval_dataset.json` | 评测数据集 | 10 条手工标注的问答对 |
| `demo/evals_skeleton.py` | 评测骨架 | 指标计算 + 评测循环框架 |

### 评测数据集结构

每条评测用例包含：
```json
{
  "id": "eval_001",
  "question": "变压器油温超过多少度需要停机？",
  "expected_answer": "85°C",
  "expected_source": "doc_001",
  "category": "故障诊断"
}
```

---

## 🔬 实验步骤

### Task 1：设计评测数据集

**目标**：手工创建 5-10 条评测用例，每条标注正确答案和来源文档。

**步骤**：

1. 基于 `knowledge_base.json` 中的 12 篇文档，设计覆盖不同类别的提问
2. 每条用例包含正确答案和期望的来源文档
3. 设计原则：
   - 覆盖不同类别（故障诊断、技术规范、巡检规程等）
   - 包含简单查询和需要综合多篇文档的复杂问题
   - 包含"知识库没有覆盖"的问题（测试 RAG 是否会编造）

**预期结果**：`eval_dataset.json` 有 ≥5 条标注用例。

---

### Task 2：实现评测指标

**目标**：实现三个评测指标的 Python 函数。

**步骤**：

1. **指标 1：意图识别准确率**（如果使用了 Router）
   - 检查 Agent 的意图分类是否和预期一致

2. **指标 2：检索召回率（Recall@K）**
   - 对于每条问题，检查检索结果中是否包含期望的来源文档
   - `recall = 期望文档是否在 Top-K 结果中`

3. **指标 3：答案质量（LLM 裁判）**
   - 用 Haiku 等便宜模型做裁判，对比 Agent 答案和期望答案
   - 评分标准：完全匹配（1.0）、部分匹配（0.5）、不匹配（0.0）

4. 实现评测循环：

```python
def run_evals(rag_func, dataset):
    results = []
    for case in dataset:
        answer = rag_func(case["question"])
        recall = check_recall(answer, case["expected_source"])
        quality = judge_answer(answer, case["expected_answer"])
        
        results.append({
            "id": case["id"],
            "question": case["question"],
            "recall": recall,
            "quality": quality,
            "passed": recall and quality >= 0.5,
        })
    
    # 汇总
    passed = sum(1 for r in results if r["passed"])
    print(f"通过率: {passed}/{len(results)} ({passed/len(results)*100:.0f}%)")
    return results
```

**预期结果**：每条用例有 recall 和 quality 两个分数。

---

### Task 3：跑评测 + 分析失败用例

**目标**：用你的 RAG 管道跑一遍评测，分析失败原因。

**步骤**：

1. 跑评测脚本
2. 对每条失败的用例，分析根因：
   - 检索没召回 → Embedding 模型问题 or 文档需要更细分块？
   - 答案不匹配 → Prompt 问题 or LLM 模型能力不够？
   - RAG 编造了内容 → Prompt 没强调"不要编造"？

3. 根据分析调整配置（Prompt、k 值、文档分块策略等），再跑一遍评测
4. 对比调整前后的分数变化

**预期结果**：找到至少一个可以改进的点，调整后评测分数有提升。

---

## 📸 打卡内容

| 序号 | 打卡项 | 具体要求 |
|------|--------|----------|
| 1 | **评测数据集** | ≥5 条手工标注的用例，覆盖不同类别 |
| 2 | **评测运行截图** | 通过率和每条用例的分数 |
| 3 | **改进前后对比** | 调整了某个配置项后，分数变化 |

---

**🎉 恭喜完成实验！**

# Day4 Sample — SDD 工程化交付

规范驱动开发 + 测试 + Skills 打包的工程化模板。

## 目录结构

```
sample-4days/day4/
├── spec.md               SDD 规范示例（验收标准 + 接口契约）
├── test_agent.py         pytest 测试用例（单元测试 + 回归测试）
├── prompt_test.py        Prompt A/B 对比测试（12 条用例 × 双版本）
├── skills/
│   └── 5g-ops-agent/     Skills 模板（开箱即用的 Agent 包）
│       ├── README.md
│       ├── agent.py
│       ├── tools.py
│       └── requirements.txt
├── overview.html         介绍页
└── README.md             本文档
```

## Day4 核心流程

```
Spec 撰写 → 单元测试 → Prompt A/B 回归 → Skills 打包
```

## 快速开始

```bash
# 运行测试
pip install pytest
pytest test_agent.py -v

# Prompt 对比
python prompt_test.py

# Skills 打包
cd skills/5g-ops-agent
pip install -r requirements.txt
cp .env.example .env
python agent.py
```

## 与 Day1-3 的关系

Day1-3 产出可运行的 Agent。Day4 把 Agent 变成可交付的工程产物：有 Spec 约束、有测试验证、有 Skills 包可分发。

# 四天课程包

> 一套按天组织的完整课程，四天从零到能写生产级 Agent。

## 目录

| 天 | 主题 | 内容 |
|---|---|---|
| Day 1 | 基础与护栏 | 应用骨架、输入/输出护栏、埋点 |
| Day 2 | RAG 与记忆 | 检索增强、四种记忆策略、效果大盘 |
| Day 3 |  Agent 与工具 | 工具设计、Agent 循环、异常分层 |
| Day 4 | 评测与上线 | 评测集、回归、Prompt 测试 |

每天目录下都有自己的 `README.md`，说明当天的目标、步骤和打卡要求。

## 怎么用

```bash
cd day2
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

每天是**独立可跑**的，不依赖前一天的环境。

## 和 `labs/` 的关系

- `labs/` 是**按能力**拆的 28 个单点实验，一个 lab 只讲一件事
- `samples/03` 是**按天**组织的课程，一天会串起多个能力

同一批知识点，两种切法。做培训时按天走，自学时按 lab 走。

## 注意

- 部分页面（`overview.html` / `prototype.html`）是纯前端演示，不需要后端
- 需要模型的地方走 OpenAI 兼容接口，配置见仓库根 [docs/模型配置.md](../../docs/模型配置.md)

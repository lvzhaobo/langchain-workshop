# 5G 设备智能运维平台

> 一个能跑的 Web 平台，把前 26 个 lab 里的 Agent 装进真实界面。

## 启动

```bash
python -m venv .venv && source .venv/bin/activate
pip install flask flask-cors langgraph langchain-openai
python app.py
```

打开 http://localhost:8100

## 结构

| 文件 | 作用 |
|---|---|
| `app.py` | Flask 服务 + 路由 |
| `agents/single_agent.py` | 单 Agent 实现 |
| `agents/tools.py` | 工具定义（查设备、查告警、搜知识库） |
| `data/devices.json` | 设备数据快照 |
| `templates/index.html` | 前端页面 |

## 这个 sample 的意义

前面所有 lab 都是命令行输出。到这一步才回答一个问题：

> **Agent 装进真实系统里，长什么样？**

具体体现在三件事：

1. **工具不再是玩具函数** —— `agents/tools.py` 里的工具要去查真实数据源
2. **要有降级** —— 平台没起、数据库连不上时，Agent 得能说清楚，而不是抛异常
3. **前端要能渲染** —— 工具返回结构化数据，页面才能画成卡片，而不是一段文字

## 依赖说明

- `flask` 起服务，`flask-cors` 允许前端跨域
- 数据源默认读 `data/devices.json`，换真实平台只需改 `agents/tools.py`

## 被其他 lab 依赖

`labs/09` `labs/17` `labs/21` 等都会尝试连这个平台（端口 8000/8025/8100），
**连不上时它们有本地兜底**，所以不启动也能跑那些 lab。

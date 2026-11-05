# Day3 Sample — 多 Agent 协作（Supervisor + HITL + Stream + Checkpoint）

Supervisor 中央调度 + 人工审批 + 流式输出 + 会话持久化的完整参考实现。

**真数据场景**：三个 Worker 不再用硬编码假数据——

| Worker | 数据源 | 干什么 |
|--------|--------|--------|
| detection | Day1 对象数据（HTTP 8081 优先 / `../day1/data/objects.json` 兜底） | LLM 分析真实指标+事件，定风险等级 |
| diagnosis | Day2 知识库 `../day2/data/knowledge/*.md` | 关键词检索阈值/手册，LLM 定根因（带来源） |
| disposal | — | LLM 按风险等级生成工单；P0 提示"需人工审批"→ 引出 HITL |

演示故障站：`OBJ-0006`（中兴 BBU，P0 光模块故障，收光 < -30dBm 链路中断）。

## 快速开始

```bash
pip install -r requirements.txt
cp .env.example .env   # 填 DEEPSEEK_API_KEY
python app.py          # → http://localhost:8301
```

## 目录结构

```
app.py                     Flask 入口（端口 8301）
agents/
  tools.py                 数据接入：day1 对象（HTTP/文件）+ day2 知识库检索
  supervisor_agent.py      Supervisor + 3 Worker（检测/诊断/处置，真调 LLM）
  hitl_agent.py            HITL 人工审批（interrupt + resume，诊断读真实对象）
templates/index.html       页面：Supervisor + HITL + Checkpoint
```

## 功能通道

| 通道 | 接口 | 说明 |
|------|------|------|
| Supervisor | `POST /agent/supervisor` | LLM 决定派哪个 Worker，Worker 干完回去再决策 |
| HITL 开始 | `POST /agent/hitl/start` | Agent 诊断后暂停，等待人工审批 |
| HITL 决定 | `POST /agent/hitl/decide` | 人点批准/拒绝，Agent 继续执行 |
| 会话列表 | `GET /sessions` | Checkpoint 存储的所有会话 |

## 验收

```bash
# Supervisor（OBJ-0006 是带 P0 故障的演示站，也可换其他 OBJ-XXXX）
curl -N -X POST http://localhost:8301/agent/supervisor \
  -H "Content-Type: application/json" \
  -d '{"question":"OBJ-0006 业务中断，全面排查"}'

# HITL
curl -X POST http://localhost:8301/agent/hitl/start \
  -H "Content-Type: application/json" \
  -d '{"device_name":"OBJ-0006"}'
# → {"status":"pending","thread_id":"hitl-123","action":"...","diagnosis":"...真实 P0 事件描述"}
curl -X POST http://localhost:8301/agent/hitl/decide \
  -H "Content-Type: application/json" \
  -d '{"thread_id":"hitl-123","approved":true}'
# → {"status":"completed","decision":"approved"}
```

## 与 Day1/2 的关系

Day1 = Agent 骨架，Day2 = 知识库+记忆，Day3 = 多 Agent 编排。
Day3 直接复用 Day1 的对象数据（8081 在跑就走 HTTP，没跑就读文件，可独立运行）和 Day2 的知识库 Markdown，三天数据链路串成一个故事。

# Lab 7.11 — Ops 监控：Token 用量 + 成本 + 延迟 Dashboard

> 给 AI Gateway 加上运维监控——实时追踪每个 Agent 的 Token 消耗和费用、记录每次调用的延迟、在 HTML Dashboard 上一目了然。当成本异常或延迟飙升时自动告警。

---

## 🎯 实验目标

1. 理解 Agent 运维监控的三个核心指标：Token 用量、成本、延迟
2. 在 Gateway 中增加用量日志，每个请求自动记录
3. 构建一个实时监控 Dashboard（HTML），可视化各 Agent 的运行状态
4. 设置告警阈值，当成本或延迟异常时触发通知

---

## 📋 前置条件

| 序号 | 条件 | 说明 |
|------|------|------|
| 1 | 完成 Lab 5.1 | AI Gateway 已启动 |
| 2 | 完成 Lab 7.9 | 了解 Flask + HTML 前端 |
| 3 | Python 3.9+ | |

---

## 📦 实验数据

### 监控指标体系

| 指标 | 计算方式 | 告警阈值（示例） |
|------|----------|:--:|
| **Token 消耗** | 每次 API 调用累加 | 单日超过 10 万 Token |
| **API 费用** | Token × 单价 | 单日超过 ¥5 |
| **调用次数** | 每次请求计数 | — |
| **平均延迟** | 每次请求的响应时间 | P95 超过 3 秒 |
| **错误率** | 错误响应 / 总请求 | 超过 5% |

### 日志格式

Gateway 每次 Agent 调用记录一条 JSON 日志：

```json
{
  "timestamp": "2025-07-13T14:30:00",
  "agent_id": "fault-diagnosis",
  "model": "qwen-plus",
  "tokens_prompt": 245,
  "tokens_completion": 512,
  "tokens_total": 757,
  "cost_estimate": 0.003,
  "latency_ms": 1234,
  "status": "success"
}
```

### 提示词清单

**提示词 1：给 Gateway 加用量日志**

```
在 agent-gateway.py 中增加用量日志功能。

要求：
1. 每次 Agent 调用完成后，自动记录一条 JSON 日志到 logs/usage.jsonl
2. 日志字段：timestamp, agent_id, model, tokens_prompt, tokens_completion, tokens_total, cost_estimate, latency_ms, status
3. Token 数从流式响应的 chunk 中累计（如果没有 usage 信息，按字符数估算：1 token ≈ 2 中文字符）
4. 新增一个 GET /api/metrics 端点，返回当天的用量摘要：
   {
     "date": "2025-07-13",
     "total_tokens": 15000,
     "total_cost": 0.06,
     "total_calls": 25,
     "avg_latency_ms": 890,
     "by_agent": {
       "fault-diagnosis": {"tokens": 8000, "cost": 0.032, "calls": 10},
       ...
     }
   }

代码不超过 80 行。
```

**提示词 2：构建监控 Dashboard**

```
基于 GET /api/metrics 的数据，生成一个 HTML 监控面板 ops_dashboard.html。

要求：
1. 纯静态 HTML，用 fetch 定时拉取 /api/metrics（每 10 秒刷新）
2. 页面布局（16:9 宽屏）：
   顶部：概览卡片行（今日 Token、今日费用、调用次数、平均延迟、错误率）
   左侧：Agent 用量柱状图（Chart.js，按 Agent 拆分 Token 消耗）
   右侧：延迟分布（P50/P95/P99 折线图）
   底部：最近 20 条调用记录表格
3. 告警功能：
   - 当日费用超过 ¥5 → 卡片变红，顶部显示黄色告警横幅
   - P95 延迟超过 3 秒 → 延迟卡片变黄
4. 样式：深色主题 Dashboard 风格，和专业监控面板一致

代码不超过 150 行。
```

**提示词 3：成本告警通知**

```
在 /api/metrics 端点中增加告警触发逻辑。

当检测到以下情况时，打印告警日志并写入 logs/alerts.jsonl：
- 单小时 Token 消耗超过日常均值的 2 倍
- 单次调用延迟超过 10 秒
- 错误率超过 10%

告警日志格式：
{
  "timestamp": "...",
  "level": "warning",
  "type": "cost_spike" | "high_latency" | "error_rate",
  "detail": "...",
  "current_value": ...,
  "threshold": ...
}

（不需要实现飞书通知——打印日志即可。框架预留了通知接口，后续可扩展。）
```

### 背景信息

#### 运维的三个层次

```
Level 1：看得到（Metrics Dashboard）
  → 本实验的目标：能用图表看到 Agent 的运行状态

Level 2：告得了（Alerting）
  → 成本异常、延迟飙升时自动通知

Level 3：自愈（Auto-Remediation）
  → 检测到小模型质量下降 → 自动切到大模型
  → 检测到某个 Agent 频繁超时 → 自动限流
```

#### 为什么指标要按 Agent 拆分

```
如果只看总数："今天消耗了 50,000 Token"
→ 无法判断是哪个 Agent 在烧钱

按 Agent 拆分后：
  fault-diagnosis：35,000 Token（70%）← 优化重点
  solution-generator：10,000 Token（20%）
  report-writer：5,000 Token（10%）
→ 一目了然：诊断 Prompt 可能太长，需要精简
```

---

## 🔬 实验步骤

### Task 1：给 Gateway 加用量日志

**目标**：每次 Agent 调用自动记录用量

**步骤**：

1. 用**提示词 1**在 agent-gateway.py 中增加用量日志
2. 调几次 Agent，检查 `logs/usage.jsonl` 是否在增长
3. 访问 `GET /api/metrics`，确认返回正确的统计

**预期结果**：每次 Agent 调用后，`logs/usage.jsonl` 追加一条日志

---

### Task 2：构建监控 Dashboard

**目标**：可视化展示所有监控指标

**步骤**：

1. 用**提示词 2**生成 `ops_dashboard.html`
2. 浏览器打开，确认数据正常加载
3. 多调几次不同 Agent，观察 Dashboard 实时变化
4. 检查告警横幅是否在费用/延迟超标时出现

**预期结果**：Dashboard 实时展示 Token、费用、延迟，超标时触发告警

---

### Task 3：告警触发测试

**目标**：验证告警逻辑正确触发

**步骤**：

1. 用**提示词 3**实现告警触发逻辑
2. 调低告警阈值（如费用阈值改为 ¥0.01），大量调用 Agent
3. 检查 `logs/alerts.jsonl` 是否记录了告警
4. 把阈值调回正常值

**预期结果**：成本超阈值时自动记录告警日志

---

## 📊 结果产出

| 产出 | 格式 | 说明 |
|------|------|------|
| 用量日志模块 | `.py` | agent-gateway.py 新增的 logging + /api/metrics |
| 监控 Dashboard | `.html` | ops_dashboard.html（深色主题） |
| 告警日志 | `.jsonl` | 至少 1 条告警记录 |

---

## 📸 打卡内容

| 序号 | 打卡项 | 具体要求 | 检查 |
|------|--------|----------|------|
| 1 | **用量日志截图** | `logs/usage.jsonl` 中有多条调用记录 | ☐ |
| 2 | **Dashboard 截图** | 展示概览卡片 + 图表 + 告警横幅 | ☐ |
| 3 | **告警日志截图** | `logs/alerts.jsonl` 中至少 1 条告警 | ☐ |

---

## ⚠️ 常见问题

| 问题 | 原因 | 解决方法 |
|------|------|----------|
| Token 数不准确 | 流式响应中不一定有 usage 信息 | 用字符数估算（中文字符×0.5 ≈ token 数） |
| Dashboard 数据不刷新 | fetch 请求失败 | 检查 /api/metrics 是否可访问，浏览器控制台看报错 |
| 告警不触发 | 阈值设置太高 | 临时降低阈值测试，确认后调回来 |
| Chart.js CDN 加载失败 | 网络问题 | 下载 Chart.js 本地引用 |

---

**🎉 恭喜完成实验！**

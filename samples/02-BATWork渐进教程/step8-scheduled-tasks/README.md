# Step 8: + 定时任务调度

> 基于 APScheduler 的定时任务系统。支持 Cron 表达式和 Interval 两种调度方式，定时触发 Agent 执行任务。

## 新增能力

| 能力 | 说明 |
|:---|:---|
| **Cron 调度** | 精确到分钟级别的周期性任务 |
| **Interval 调度** | 固定间隔（秒）的重复任务 |
| **任务热切换** | Web UI / API 实时启用/禁用任务 |
| **执行日志** | 每次任务执行结果持久化为 JSON |

## 启动方式

```bash
# 基础启动（含 Memory + Skill + Streaming + 主题切换）
python server.py --port 6001 --model qwen2.5:0.5b

# 启用定时任务调度器
python server.py --port 6001 --model qwen2.5:0.5b --enable-scheduler

# 自定义任务配置
python server.py --port 6001 --model qwen2.5:0.5b --enable-scheduler --tasks-config ./my-tasks.yaml
```

## 任务配置（tasks.yaml）

```yaml
# Cron 任务
- name: "每日销售数据汇总"
  schedule: "0 9 * * *"          # 每天 9:00
  type: cron
  prompt: "读取 sales.csv，统计昨日销售数据"
  enabled: true

# Interval 任务
- name: "数据完整性巡检"
  schedule: "1800"               # 每 30 分钟
  type: interval
  prompt: "检查 sales.csv 数据完整性"
  enabled: false
```

## 文件结构

```
step8-scheduled-tasks/
├── scheduler.py       # APScheduler 封装 + TaskScheduler 类
├── tasks.yaml         # 定时任务定义（YAML/JSON 兼容）
├── server.py          # Web 服务 + /api/scheduler/* 端点
├── ... (同 step7 的全部文件)
└── task_logs/         # 任务执行日志（自动生成）
```

## 新增 API

| 端点 | 方法 | 说明 |
|:---|:---|:---|
| `/api/scheduler/status` | GET | 返回调度器状态和任务列表 |
| `/api/scheduler/toggle/{name}` | POST | 启用/禁用指定任务 |

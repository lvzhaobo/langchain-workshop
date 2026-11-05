# Step 9: + 多智能体协作

> 基于 LangGraph 的多智能体显性调度系统。5 个专业化 Agent 角色（编排器 → 研究员 → 分析师 → 写手 ⇄ 审阅官）协作完成复杂任务，支持模拟模式（开箱即用）和 LLM 驱动模式（DeepSeek/OpenAI 兼容 API）。

## 新增能力

| 能力 | 说明 |
|:---|:---|
| **5 Agent 协作图** | 编排器→研究员→分析师→写手→审阅官，写手与审阅官可循环修订 |
| **双模式运行** | 模拟模式：内置规则驱动，无需 API Key；LLM 模式：DeepSeek/OpenAI 真实推理 |
| **可视化页面** | `/multi-agent` 页面实时展示 Agent 流转、状态和输出 |
| **流式推送** | WebSocket 推送每个 Agent 的启动/完成事件 |

## 启动方式

```bash
# 模拟模式（不需要 API Key）
python server.py --port 6001 --model qwen2.5:0.5b

# LLM 驱动模式（需要 DeepSeek API Key）
DEEPSEEK_API_KEY=sk-xxx python server.py --port 6001 --model qwen2.5:0.5b

# 浏览器打开多智能体页面
open http://localhost:6001/multi-agent
```

## Agent 角色与协作流程

```
🎯 编排器 → 理解任务类型，分发到对应 Agent
  ├── 🔍 研究员 → 收集数据、查找信息
  ├── 📊 分析师 → 分析数据、发现洞察
  └── ✍️ 写手   → 撰写输出
       └── 🔎 审阅官 ⇄ 写手（循环修订直到通过）
```

## 文件结构

```
step9-multi-agent/
├── multi_agent_graph.py  # 5 Agent LangGraph 定义
├── static/
│   ├── index.html        # 单 Agent 页面
│   └── multi-agent.html  # 多智能体可视化页面（新增）
├── server.py             # Web 服务 + /ws/multi-agent 端点
├── ... (同 step8 的全部文件)
└── memory_data/          # 记忆数据（自动生成）
```

## 新增 API

| 端点 | 方法 | 说明 |
|:---|:---|:---|
| `/multi-agent` | GET | 多智能体可视化页面 |
| `/ws/multi-agent` | WS | 多智能体流式 WebSocket |
| `/api/multi-agent/graph` | GET | 返回图结构定义（前端渲染用） |
| `/api/multi-agent/llm-status` | GET | LLM 就绪状态（判断是否显示 DeepSeek 开关） |

## 模拟模式 vs LLM 模式

| 维度 | 模拟模式 | LLM 模式 |
|:---|:---|:---|
| 依赖 | 无 | DeepSeek API Key |
| 推理质量 | 基于规则模板 | 真实 LLM 推理 |
| 响应速度 | 即时 | 取决于 API 延迟 |
| 适用场景 | 演示、教学、原型验证 | 真实任务执行 |

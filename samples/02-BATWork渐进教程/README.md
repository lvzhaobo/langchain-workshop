# BAT Work 仿制 — 8 步渐进式实现

> 每一步都是完整可运行的独立文件夹，后一步包含前一步的全部代码（冗余但自包含）。
- 从 Step 1 最简单的 3 节点 Agent Loop 开始，逐步叠加到 Step 8 的完整 BAT Work 风格 Web Agent（含定时任务）。

## 步骤总览

| Step | 文件夹 | 新增核心能力 | 节点数 | 条件边 | 状态 |
|:---|:---|:---|:---:|:---:|:---|
| **1** | [step1-langgraph-skeleton](step1-langgraph-skeleton/) | LangGraph Agent Loop 骨架 | 3 | 0 | ✅ |
| **2** | [step2-tool-system](step2-tool-system/) | + 工具注册表（6个工具）+ 任务规划 | 5 | 2 | ✅ |
| **3** | [step3-validation-loop](step3-validation-loop/) | + 校验 → 重试 → replan → 兜底 回路 | 7 | 3 | ✅ |
| **4** | [step4-memory](step4-memory/) | + ChromaDB 向量记忆 + SQLite 摘要 | 7 | 3 | ✅ |
| **5** | [step5-skill-system](step5-skill-system/) | + SKILL.md 技能定义（用户可教学） | 7 | 3 | ✅ |
| **6** | [step6-web-interface](step6-web-interface/) | + FastAPI Web 界面（BAT Work 暗色主题） | 7 | 3 | ✅ |
| **7** | [step7-streaming](step7-streaming/) | + Token 流式输出 + Skill 市场面板 + 深色/浅色主题 | 7 | 3 | ✅ |
| **8** | [step8-scheduled-tasks](step8-scheduled-tasks/) | + APScheduler 定时任务（Cron/Interval） | 7 | 3 | ✅ |

## Graph 拓扑演进

```
Step 1 (3 节点直线):
  understand_intent → enrich_context → generate_output → END

Step 2 (5 节点 + 2 条件边):
  understand_intent → enrich_context → plan_tasks ─┬─→ execute_tool（循环）
                                                     └─→ generate_output → END

Step 3-8 (7 节点 + 3 条件边):
  understand_intent → enrich_context → plan_tasks ─┬─→ execute_tool ⇄ validate_result
                                                     │        │
                                                     │        └─→ handle_error → END
                                                     │
                                                     └─→ generate_output → END
```

## 各步骤文件结构

```
stepN-xxx/
├── state.py         # AgentState 定义（每步字段递增）
├── nodes.py         # 节点函数（每步能力递增）
├── router.py        # 条件路由（Step 2+）
├── agent.py         # 图组装 + LLM 初始化 + 模块注入
├── main.py          # CLI 入口（含 Memory/Skill 初始化）
├── requirements.txt # Python 依赖
├── README.md        # 本步骤说明
├── workspace/       # 工作目录 + 示例数据
│   └── sales.csv    # 示例 CSV 数据
├── tools.py         # 工具注册表（Step 2+）
├── memory.py        # 记忆系统 ChromaDB + SQLite（Step 4+）
├── skill_loader.py  # Skill 解析器（Step 5+）
├── scheduler.py     # 定时任务调度器 APScheduler（Step 8+）
├── tasks.yaml       # 定时任务配置（Step 8+）
├── skills/          # Skill 定义目录（Step 5+）
│   └── example-skill/SKILL.md
├── server.py        # Web 服务 FastAPI + WebSocket（Step 6+）
└── static/          # Web 前端 BAT Work 暗色主题（Step 6+）
    └── index.html
```

## 能力演进一览

| 能力 | Step1 | Step2 | Step3 | Step4 | Step5 | Step6 | Step7 | Step8 |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| Agent Loop 编排 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 工具调用（6个） | — | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 自动重试/兜底 | — | — | ✅ | ✅ | ✅ | ✅ | ✅ |
| ChromaDB 记忆 | — | — | — | ✅ | ✅ | ✅ | ✅ |
| SKILL.md 教学 | — | — | — | — | ✅ | ✅ | ✅ | ✅ |
| Web 界面 | — | — | — | — | — | ✅ | ✅ | ✅ |
| Token 流式 | — | — | — | — | — | — | ✅ | ✅ |
| Skill 市场 | — | — | — | — | — | — | ✅ | ✅ |
| 深浅主题 | — | — | — | — | — | — | ✅ | ✅ |
| 定时任务 | — | — | — | — | — | — | — | ✅ |

## 快速开始

```bash
# 选择一个步骤，进入目录
cd step3-validation-loop

# 安装依赖
pip install -r requirements.txt

# 运行（需要本地 Ollama 或 OpenAI API Key）
python main.py --api-key ollama --base-url http://localhost:11434/v1 --model qwen2.5:0.5b -q "列出当前目录的文件"

# Step 5+ 加载 Skills
cd step5-skill-system
python main.py --api-key ollama --base-url http://localhost:11434/v1 --model qwen2.5:0.5b -i

# Step 8 启动 Web 界面 + 定时任务
cd step8-scheduled-tasks
python server.py --api-key ollama --base-url http://localhost:11434/v1 --model qwen2.5:0.5b --port 6001 --enable-scheduler
# 浏览器打开 http://localhost:6001
```

## 多模型支持

所有 Step 均支持以下模型（OpenAI 兼容协议）：

```bash
# Ollama 本地模型
python main.py --api-key ollama --base-url http://localhost:11434/v1 --model qwen2.5:0.5b

# OpenAI
python main.py --api-key sk-xxx --model gpt-4o-mini

# DeepSeek
python main.py --api-key $DEEPSEEK_KEY --base-url https://api.deepseek.com/v1 --model deepseek-chat

# 通义千问
python main.py --api-key $DASHSCOPE_KEY --base-url https://dashscope.aliyuncs.com/compatible-mode/v1 --model qwen-plus
```

## 设计理念

1. **渐进式学习**：每步只加一个核心能力，不会信息过载
2. **自包含冗余**：每步文件夹包含完整可运行代码，不需要跨步骤引用
3. **能力可见**：每一步的能力矩阵清晰可见，方便对比演进
4. **实战导向**：不是玩具代码，每步都能处理真实 CSV 数据分析场景
5. **解耦设计**：LLM 通过 OpenAI 协议与 Agent 解耦，支持任意模型切换

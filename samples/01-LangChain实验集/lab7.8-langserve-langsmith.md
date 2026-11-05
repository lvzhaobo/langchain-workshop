# Lab 7.8 — LangServe 部署 + LangSmith 追踪

> 一行代码把 LangGraph 工作流变成 REST API（带 Swagger + Playground），开启 LangSmith 追踪看每一步工具调用。

---

## 🎯 实验目标

1. 用 LangServe 把 lab7.5 的 StateGraph 暴露为 REST API（`/invoke`、`/stream`、`/playground`）
2. 配置 LangSmith 环境变量，开启全链路追踪
3. 在 Playground 中在线调试，在 LangSmith 中查看调用链
4. 理解 LangServe 和手写 Flask/FastAPI 的关系

---

## 📋 前置条件

| 序号 | 条件 | 说明 |
|------|------|------|
| 1 | Python 3.9+ | 运行脚本 |
| 2 | 百炼 API Key | LLM 调用需要 |
| 3 | 完成 Lab 7.5 | 有可编译的 StateGraph |
| 4 | LangSmith API Key | 追踪需要（可选，不影响 LangServe） |
| 5 | 安装依赖 | `pip install langchain langserve langsmith` |

---

## 📦 背景信息

### LangServe vs 手写 Flask

```
手写 Flask（如 demo/gateway/app.py）：
  你需要自己写：
  - @app.route 路由定义
  - 请求参数解析和校验
  - 响应格式化和错误处理
  - Swagger 文档配置
  - SSE 流式接口实现
  → 几十到几百行代码

LangServe（针对 LangChain）：
  add_routes(app, graph, path="/api/query")
  → 自动生成：
  POST /api/query/invoke    — 同步调用
  POST /api/query/stream    — SSE 流式
  POST /api/query/batch     — 批量调用
  GET  /api/query/playground — 在线调试页面
  → 1 行代码
```

LangServe 不是"替代 Flask"，而是"在 FastAPI 基础上自动生成 LangChain 专属端点"。

### LangSmith 追踪什么

```
LangSmith 自动追踪的内容：
  用户问题 → Router 节点的 Prompt → LLM 返回的 JSON
           → Diagnosis 节点的知识库查询
           → Solution 节点的 Prompt → LLM 返回的方案
           → Execute 节点的输出
           
  每一步的：
  - 耗时（latency）
  - Token 消耗
  - 输入输出（可脱敏）
  - 错误信息
```

---

## 🔬 实验步骤

### Task 1：用 LangServe 暴露 Graph 为 API

**目标**：创建 `api.py`，把 lab7.5 的 graph 变成可调用的 API。

**步骤**：

1. 创建 `api.py`：

```python
from fastapi import FastAPI
from langserve import add_routes
from langgraph_skeleton import build_graph

app = FastAPI(
    title="电力设备故障诊断 Agent",
    description="LangGraph 驱动的设备故障诊断工作流 API",
    version="1.0.0",
)

# 构建图
graph = build_graph()

# 一行代码：自动生成 /invoke /stream /batch /playground
add_routes(app, graph, path="/api/diagnosis")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

2. 启动服务：

```bash
pip install uvicorn
python api.py
```

3. 访问：
   - `http://localhost:8000/docs` — 自动生成的 Swagger
   - `http://localhost:8000/api/diagnosis/playground/` — 在线调试页面

4. 在 Playground 中直接输入设备故障描述，点 Execute 看结果

**预期结果**：Swagger 页面有三个端点（invoke、stream、batch），Playground 能在线交互。

---

### Task 2：开启 LangSmith 追踪

**目标**：配置环境变量，在 LangSmith 中看到完整的调用链。

**步骤**：

1. 在 `.env` 或环境变量中配置：

```bash
export LANGCHAIN_TRACING_V2=true
export LANGCHAIN_API_KEY=ls_...       # 从 langsmith.com 获取
export LANGCHAIN_PROJECT=power-inspection  # 项目名
```

2. 重新启动 API，发送几个请求
3. 打开 LangSmith 控制台（https://smith.langchain.com），找到 `power-inspection` 项目
4. 观察：
   - 每个请求的完整调用链（trace）
   - 每个节点内部的 LLM 调用耗时
   - Token 消耗汇总
   - 有没有错误或异常

**预期结果**：LangSmith 控制台能看到每条请求的 trace，展开后有 LLM 调用的详细参数和返回。

> **如果没有 LangSmith API Key**，可以对比：
> - 无追踪 → 出了错只能看终端日志
> - 有追踪 → 在控制台回放每一步的输入输出，快速定位问题

---

### Task 3：验证 SSE 流式输出

**目标**：测试 stream 端点，验证流式返回效果。

**步骤**：

```bash
curl -X POST http://localhost:8000/api/diagnosis/stream \
  -H "Content-Type: application/json" \
  -d '{"user_query": "EP-D-002 断路器拒分", "messages": []}'
```

观察：输出逐节点返回，不像 invoke 那样等全部完成才返回。

---

## 📸 打卡内容

| 序号 | 打卡项 | 具体要求 |
|------|--------|----------|
| 1 | **Playground 截图** | 浏览器打开 Playground 页面，输入测试问题 |
| 2 | **Swagger 截图** | `/docs` 页面显示三个端点 |
| 3 | **LangSmith Trace 截图** | 一条 trace 展开，能看到 LLM 调用的参数和返回（如果有 API Key） |
| 4 | **stream 终端截图** | curl stream 端点，逐节点返回 |

---

## ⚠️ 常见问题

| 问题 | 原因 | 解决方法 |
|------|------|----------|
| `add_routes` 报"not a Runnable" | graph 不是 Runnable 类型 | 确保传入的是 `workflow.compile()` 的返回值 |
| Playground 无法访问 | 端口被占用 | 换一个端口 `uvicorn.run(app, port=8001)` |
| LangSmith 没有数据 | 环境变量未生效 | 重启 API 进程，确认 `echo $LANGCHAIN_TRACING_V2` 输出 `true` |

---

**🎉 恭喜完成实验！**

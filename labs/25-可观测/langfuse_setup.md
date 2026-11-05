# Langfuse 自托管实验（lab 25 的进阶路线）

> 本地 Tracer 适合快速入门。当需要生产级可观测面板（搜索、聚合、时序对比），用 Langfuse 替代。

---

## Langfuse vs LangSmith 一句话

| | LangSmith | Langfuse |
|---|---|---|
| 关系 | LangChain 亲儿子（同一家公司） | 德国独立公司，开源 |
| 部署 | 仅 SaaS（数据出国） | **自托管 Docker** 或 Cloud |
| 企业适配 | 需海外网络 | 内网 `docker compose up` 即可 |

> **中国移动场景下选 Langfuse——排障数据不出机房，开源免费无上限。**

---

## 第一步：启动 Langfuse（Docker）

```bash
# 1. 克隆仓库（约 200MB）
git clone https://github.com/langfuse/langfuse.git
cd langfuse

# 2. 一键启动
docker compose up -d

# 3. 验证
curl http://localhost:3000
# → 看到 Langfuse 登录页表示成功
```

> 如果没有 Docker，也可用 Cloud 免费层：https://cloud.langfuse.com 注册 → 获取 public_key + secret_key。

---

## 第二步：安装 Python SDK

```bash
pip install langfuse
```

---

## 第三步：配置连接

```python
# 获取密钥：Web UI → Settings → API Keys → Create API Key
import os

os.environ["LANGFUSE_PUBLIC_KEY"] = "pk-lf-..."
os.environ["LANGFUSE_SECRET_KEY"] = "sk-lf-..."
os.environ["LANGFUSE_HOST"] = "http://localhost:3000"  # 自托管地址
```

---

## 第四步：接入 LangChain Agent

### 方式 A：Callback 一行接入（推荐）

```python
from langfuse.langchain import CallbackHandler

# 初始化
langfuse_handler = CallbackHandler()

# 注入到任意 Agent
agent.invoke(
    {"input": "DEV-0001 状态怎么样？"},
    config={"callbacks": [langfuse_handler]}
)
# → 自动上报 Trace 到 Langfuse Dashboard
```

> 无需手写 `start_span` / `end_span`。LangChain 内置 Callback 协议，Langfuse 的 `CallbackHandler` 自动捕获每次 LLM 调用、Tool 调用、Agent 决策。

### 方式 B：装饰器手动埋点

```python
from langfuse.decorators import observe, langfuse_context

@observe()
def diagnose_device(device_id: str):
    # 这段代码的执行会被自动记录为一个 Span
    result = query_device_api(device_id)
    langfuse_context.update_current_observation(
        metadata={"device_id": device_id}
    )
    return result
```

---

## 第五步：Web Dashboard 看什么？

完成一轮 Agent 调用后，打开 `http://localhost:3000`：

| 功能 | 说明 |
|------|------|
| **Trace 列表** | 每条用户请求一条 Trace，含总耗时 + Token |
| **Span 瀑布图** | 每个子步骤（LLM/Tool/Agent）的耗时叠加 |
| **Token 用量趋势** | 按时间/模型/用户聚合 |
| **评分 (Score)** | 手动给每次回答打分，追踪质量变化 |
| **数据集管理** | 导入测试用例，批量跑 Eval |
| **告警** | Token 异常飙升 / 延迟超标 自动通知 |

---

## 和 lab 25 本地 Tracer 的关系

| | 本地 Tracer | Langfuse |
|---|---|---|
| 使用场景 | 快速验证、不装 Docker | 持续开发、团队协作、生产监控 |
| 数据保留 | 本次运行 | 永久保留，可搜索 |
| 接入方式 | 手写 `start_span/end_span` | `CallbackHandler` 一行 |
| 门槛 | 零依赖 | 需要 Docker + 5 分钟初始化 |
| 选课建议 | 标准路径 | **进阶路径（自建 Langfuse）** |

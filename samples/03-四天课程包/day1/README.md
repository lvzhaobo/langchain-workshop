# Day1 Sample — Agent 平台（对象列表 + 详情 + 多 Agent 触发）

三条 Agent 通道 + 统一 SSE 流式协议的参考实现。数据为 5G 基站场景，**换场景只需替换 `data/objects.json` + 改两处 Prompt**，接口与页面不用动。

## 快速开始（只需改两个 Key）

```bash
pip install -r requirements.txt

# 1) DeepSeek Key
cp .env.example .env          # 编辑 .env，填 DEEPSEEK_API_KEY

# 2) Dify Key
#    编辑 dify_agents.json，填 base_url 和你的 Dify 应用 api_key（app- 开头）

python app.py                 # → http://localhost:8100
```

## 目录结构

```
app.py                  平台入口：页面 + 对象 API + 三条 SSE 通道
agents/
  single_agent.py       LangGraph ReAct Agent（换场景改 SYSTEM_PROMPT）
  tools.py              @tool 回调平台 API（query_object / query_events / list_objects）
data/objects.json       对象数据（换场景 = 换这个文件）
scripts/gen_data.py     数据生成脚本（含字段约定，可让 AI 照此生成你的场景数据）
templates/
  index.html            对象列表页（筛选 + 搜索）
  detail.html           详情页（信息 + 事件 + 3 个 Agent 按钮 + SSE 打字机）
dify_agents.json        Dify Agent 注册表（api_key 留空，需自己填）
.env.example            DeepSeek 配置模板
```

## 三条通道（统一 SSE：`data: {"content": ...}` → `data: [DONE]`）

| 通道 | 接口 | 说明 |
|---|---|---|
| ① DeepSeek 直连 | `POST /gateway/chat` | 原始 OpenAI 兼容 API + `stream: true`，平台把对象数据拼进 Prompt |
| ② Dify Agent | `POST /gateway/dify/chat` | `response_mode: streaming` 逐 chunk 转发 |
| ③ LangChain ReAct | `POST /agent/single` | Agent 自己决定调哪个工具回查平台 API，可看到工具轨迹 |

## 验收 curl

```bash
curl http://localhost:8100/health
curl http://localhost:8100/api/objects?status=fault
curl http://localhost:8100/api/objects/OBJ-0001
curl -N -X POST http://localhost:8100/gateway/chat \
  -H "Content-Type: application/json" \
  -d '{"question":"分析一下","object_id":"OBJ-0001"}'
curl -N -X POST http://localhost:8100/agent/single \
  -H "Content-Type: application/json" \
  -d '{"question":"帮我查 OBJ-0002 的异常并给出建议"}'
```

## 换成你自己的场景

1. 按 `scripts/gen_data.py` 顶部的字段约定，让 AI 生成 30~50 条你的场景数据，覆盖 `data/objects.json`
2. 改 `agents/single_agent.py` 的 `SYSTEM_PROMPT`（角色 + 分析要求）
3. 改 `app.py` 里 `/gateway/chat` 的 system prompt（可选）
4. 重启 `python app.py`，页面和接口全部自动适配

> 注：本 Sample 刻意不做失败降级/重试/容错，这部分留到 SDD 环节自己开发。

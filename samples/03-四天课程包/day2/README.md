# Day2 Sample — 知识库 + 记忆系统（RAG + Memory + Callbacks）

知识库检索增强生成 + 长期记忆持久化 + 调用链监控的参考实现。数据为 5G 基站场景，**换场景只需替换 `data/knowledge/` 下的 MD 文件**。

## 快速开始

```bash
pip install -r requirements.txt
cp .env.example .env          # 编辑 .env，填 DEEPSEEK_API_KEY
python app.py                 # → http://localhost:8200
```

## 目录结构

```
app.py                    平台入口：RAG 检索 + Memory 读写 + Metrics
agents/
  tools.py                @tool 工具集（search_kb / write_memory / read_memory）
data/knowledge/           知识库文档（换场景 = 换这里的 MD 文件）
  01-故障排查.md
  02-告警等级.md
  03-维护规范.md
templates/
  index.html              RAG 搜索 + Memory 面板 + 调用监控
memory.json               长期记忆文件（首次运行自动生成）
.env.example              配置模板
```

## 三条功能通道

| 通道 | 接口 | 说明 |
|------|------|------|
| RAG 检索+回答 | `POST /rag/search` | 关键词检索知识库 + LLM 基于文档生成回答 |
| Memory 读写 | `POST /memory/write` `GET /memory/read` | 长期记忆持久化，手动写入或 LLM 自主写入 |
| Callback 监控 | `GET /metrics` | 每次 RAG 调用记录时间+端点 |

## 验收 curl

```bash
# RAG 检索
curl -N -X POST http://localhost:8200/rag/search \
  -H "Content-Type: application/json" \
  -d '{"question":"光模块功率异常怎么排查"}'

# Memory 读写
curl -X POST http://localhost:8200/memory/write \
  -H "Content-Type: application/json" \
  -d '{"fact":"望京SOHO AAU-01 上次更换过光模块","category":"project"}'
curl http://localhost:8200/memory/read

# 健康检查
curl http://localhost:8200/health
```

## 换成你自己的场景

1. 替换 `data/knowledge/` 下的 MD 文件（保留文件名格式即可）
2. 改 `app.py` 中 RAG 的 System Prompt（如果需要）
3. 重启 `python app.py`

## 与 Day1 的关系

Day1 教怎么搭 Agent（ReAct 循环），Day2 教怎么给 Agent 加知识库和记忆。两个包独立运行，也可以叠加使用。

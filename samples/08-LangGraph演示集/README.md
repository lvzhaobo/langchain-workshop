# LangGraph 演示集

> 四个可以直接演示给客户看的完整例子。和 `labs/` 的区别：这些是**演示**，不是教学。

## 内容

| 目录 | 演示什么 | 看点 |
|---|---|---|
| `sample-17/` | MCP 工具协议 | MCP Server + Client，让 Agent 用标准协议接工具 |
| `sample-18/` | 单 Agent 问答 | 最小的完整链路 |
| `sample-19/` | 多 Agent 协作 | 多个 Agent 分工完成一个任务 |
| `sample-20/` | 单/多 Agent 对比 | 同一任务两种架构的差异 |
| `memory-demo/` | 记忆服务 | 带持久化的记忆读写 |

每个 `sample-*` 下通常有一对文件：
- `demo-XX.py` —— 演示脚本（按步骤打印，适合现场讲）
- `single-agent-qa.py` / `multi-agent-collab.py` —— 完整实现（适合给人看代码）

## 跑法

```bash
cd sample-18 && python demo-18.py
```

依赖见仓库根 `requirements.txt`。

## 和 `labs/` 的区别

| | `labs/` | `samples/08` |
|---|---|---|
| 目的 | 学一个知识点 | 演示一个完整效果 |
| 输出 | 有断言、可验收 | 打印过程，给人看 |
| 规模 | 单个能力 | 端到端 |

**做培训时**：lab 用来练手，这个用来收尾演示。

## 注意

这些是**原始态**的演示脚本，没有统一改造过（没有 `_mock_llm.py`），
需要配置 `.env` 里的 Key 才能完整跑。配置见 [docs/模型配置.md](../../docs/模型配置.md)。

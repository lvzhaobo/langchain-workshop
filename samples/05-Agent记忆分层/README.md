# Agent 记忆分层与画像系统

> 一个 Agent 要记住什么、记多久、放在哪 —— 这三件事分开设计，才不会越做越乱。

## 三层记忆

| 层 | 存什么 | 生命周期 | 对应文件 |
|---|---|---|---|
| 短期 | 当前对话上下文 | 一次会话 | `state.py` |
| 长期 | 跨会话的事实、偏好 | 永久 | `memory_store.py` |
| 工作区 | 当前任务相关的临时资料 | 一个任务 | `memory_graph.py` |

## 文件

| 文件 | 作用 |
|---|---|
| `state.py` | 图的状态定义（短期记忆） |
| `memory_store.py` | 长期记忆的存储层 |
| `memory_graph.py` | 记忆读写的图编排 |
| `profiles.py` | 用户/人物画像的提取与更新 |
| `demo.py` | 跑一遍完整流程 |
| `visual.html` | 记忆流转的可视化 |
| `1.md` | 完整设计说明 |

## 跑起来

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python demo.py
```

## 核心设计

**记忆不是"都塞进 context"**。分层的意义在于：

- 短期记忆要快、要全，但不能跨会话
- 长期记忆要准、要去重、要能更新（用户偏好变了要覆盖）
- 工作区记忆跟着任务走，任务结束就该清掉

三者混在一起，就会出现"用户三个月前说的偏好还在影响今天的回答"这种问题。

## 和 `labs/16-Memory` 的关系

`labs/16-Memory` 讲的是 LangChain/LangGraph 内置的几种记忆策略（Buffer / Window / Summary），
是**单会话内**的记忆管理。这个 sample 往上走一层，讲**跨会话**的持久化与画像。

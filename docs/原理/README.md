# 原理与设计文档

> 这些是**读的材料**，不是练的。练的在 `labs/`。

## 8 篇，按主题分

### A. LangGraph 底层机制

| 文档 | 讲什么 |
|---|---|
| `底层机制-Pregel-Checkpoint-State.md` | 图到底怎么跑起来的：调度、检查点、状态 |
| `Stream-HITL-Subgraph-Supervisor-Memory.md` | 五个进阶能力串讲 |
| `Agent模式-LangChain对比-State设计.md` | Agent 模式对比与 State 设计 |

### B. LangChain 家族全景

| 文档 | 讲什么 |
|---|---|
| `LangChain全家桶-实验-Demo平台-功能对比表.md` | 四个包各自负责什么 |
| `全家桶能力-实验-Demo对照表.md` | 能力 → 实验 → Demo 的三向对照 |

> CheatSheet 在 `docs/cheatsheet/`（md + html 两份）。

### C. 上下文与记忆

| 文档 | 讲什么 |
|---|---|
| `00-三层上下文模型.md` | Agent 的上下文分哪三层 |
| `00-知识点-Agent-Memory体系.md` | 记忆体系全景 |

## 建议阅读顺序

```
做 lab 01 之前   →  LangChain全家桶-实验-Demo平台-功能对比表
做完 lab 03 之后 →  底层机制-Pregel-Checkpoint-State
讲 Memory 之前   →  00-三层上下文模型
做 lab 22 之前   →  Stream-HITL-Subgraph-Supervisor-Memory
```


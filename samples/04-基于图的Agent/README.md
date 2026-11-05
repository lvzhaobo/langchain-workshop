# 基于图的 Agent —— 7 种编排模式

> LangGraph 的本质是把 Agent 的流程画成图。这 7 个文件就是 7 种基本画法。

## 七个模式，从简到繁

| 文件 | 模式 | 一句话 |
|---|---|---|
| `1_linear_chain.py` | 线性链 | A → B → C，最基础的串行 |
| `2_conditional_branch.py` | 条件分支 | 按状态选不同路径（if/else） |
| `3_parallel_fanout.py` | 并行扇出 | 同时跑多条，最后汇总 |
| `4_loop_retry.py` | 循环重试 | 不满足条件就回到上一步 |
| `5_supervisor.py` | Supervisor | 一个调度者决定下一个交给谁 |
| `6_human_in_loop.py` | 人工介入 | 关键节点停下来等人审批 |
| `7_subgraph.py` | 子图 | 把一张图当成另一张图的节点 |

**建议按编号顺序读**，每个文件只依赖前面讲过的概念。

## 还有两个

| 文件 | 作用 |
|---|---|
| `simple_graph.py` | 最小可运行示例，先看这个 |
| `graph_app.py` / `api.py` | 把图包成 Web 服务 |

## 可视化

- `patterns_compare.html` —— 7 种模式的图形对比
- `visual.html` —— 交互式演示

直接浏览器打开即可，不需要起服务。

## 详细讲解

[`1.md`](1.md) 是这 7 个模式的完整文字说明（含每个模式适用什么场景、坑在哪）。

## 和 `labs/22` 的关系

`labs/22-LangGraph多Agent` 讲的是**多 Agent 协作**，是这里的 `5_supervisor.py` 的深化版。
先看这里建立直觉，再看 lab 22 做完整实现。

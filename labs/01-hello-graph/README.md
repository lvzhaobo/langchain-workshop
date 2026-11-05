# Lab 01 · 最小 StateGraph：节点 + 条件边

**目标**：亲手写出一条「节点自己决定还要不要再跑一轮」的图
**时长**：20 分钟
**前置**：无（第一个 lab）

## 背景
LangGraph 的心智模型只有三个词：**State（共享状态）、Node（改状态的函数）、Edge（决定下一步去哪）**。
这个 lab 把三者都用一遍。

## 步骤
1. 打开 `main.py`，找到 `# TODO 1`
2. 补上条件边，让 `think` 节点循环 3 次后自动结束
3. 运行 `python main.py`

## 验收
```bash
python check.py          # 检查你写的 main.py
python check.py --solution   # 检查参考答案
```

## 你会看到
```
{'n': 3, 'trace': ['think-1', 'think-2', 'think-3']}
```

## 卡住了
对照 `solution.py`。关键是把 `should_continue` 作为**判断函数**传给 `add_conditional_edges`，
它返回的字符串就是下一个节点名，返回 `END` 就终止。

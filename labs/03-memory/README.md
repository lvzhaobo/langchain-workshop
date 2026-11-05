# Lab 03 · 持久化记忆：Checkpointer 与 thread_id

**目标**：让同一 `thread_id` 的多轮调用共享状态，不同 `thread_id` 互不干扰
**时长**：20 分钟
**前置**：lab-02

## 背景
这是 LangGraph 和普通函数链**最本质的区别**：图是可以「暂停、恢复、多会话并行」的。
实现它的东西叫 **checkpointer**，隔离它的键叫 **thread_id**。

## 步骤
1. 打开 `main.py`，找到 `# TODO 1`
2. 给 `compile()` 传入 `checkpointer=InMemorySaver()`
3. 找到 `# TODO 2`，给每次 `invoke` 带上 `thread_id`
4. 运行 `python main.py`

## 验收
```bash
python check.py
python check.py --solution
```

## 你会看到
```
thread A 第 1 次 → {'turns': 1}
thread A 第 2 次 → {'turns': 2}    ← 记住了
thread B 第 1 次 → {'turns': 1}    ← 完全隔离
```

## 卡住了
`checkpointer` 是 `compile()` 的参数；`thread_id` 放在 `config["configurable"]` 里。
少任何一个，状态都不会被记住。

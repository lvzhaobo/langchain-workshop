# Lab 02 · 工具调用循环：assistant → tools → 结束

**目标**：看懂 Agent 的本质 = 一个「模型要工具 → 执行工具 → 再给模型」的环
**时长**：25 分钟
**前置**：lab-01

## 背景
官方示例常让你先配 OpenAI Key。这里**故意用一个假模型**：它写死返回一个 tool_call。
这样你能在没有 Key、没有额度、没有网络的情况下，**看清循环本身**。
理解了循环，换成真模型只是把 `assistant` 节点换掉。

## 步骤
1. 打开 `main.py`，找到 `# TODO 1` 和 `# TODO 2`
2. 加上 `tools` 节点（`ToolNode(TOOLS)`）
3. 加上条件边，让「有 tool_calls 就走 tools，否则结束」
4. 运行 `python main.py`

## 验收
```bash
python check.py
python check.py --solution
```

## 你会看到
```
HumanMessage  → DEV-0001 现在什么状态？
AIMessage     → (tool_calls: get_device_status)
ToolMessage   → 在线，北京望京
```

## 卡住了
`ToolNode` 吃一个工具列表，自动读 `AIMessage.tool_calls` 并执行。
判断函数看最后一条消息有没有 `tool_calls` 属性即可。

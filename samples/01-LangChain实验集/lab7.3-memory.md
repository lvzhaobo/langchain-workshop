# Lab 7.3 — Memory 机制验证

> 同一段 7 轮排障对话，切换三种 Memory 类型，观察 AI 在不同记忆策略下的表现差异。

---

## 🎯 实验目标

1. 理解 Memory 在 Agent 中的角色：它不是在"存数据"，而是在"控制每轮传给 LLM 的上下文"
2. 实现三种 Memory 策略：完整历史（Buffer）、滑动窗口（Window）、摘要（Summary）
3. 同一段多轮排障对话，对比三种 Memory 的信息保留能力和 Token 消耗
4. 学会根据场景选择合适的 Memory 策略

---

## 📋 前置条件

| 序号 | 条件 | 说明 |
|------|------|------|
| 1 | Python 3.9+ | 运行脚本 |
| 2 | 百炼 API Key | LLM 调用需要 |
| 3 | 完成 Lab 7.1 | 了解基本的 LLM 调用方式 |
| 4 | 安装依赖 | `pip install langchain langchain-openai` |

---

## 📦 实验数据

### 数据文件

| 文件路径 | 用途 | 说明 |
|----------|------|------|
| `demo/memory_skeleton.py` | 骨架代码 | 7 轮排障对话已预写，三种 Memory 函数留空 |

### 对话场景

一段电力设备排障的 7 轮对话（已预写在骨架代码中）：

```
第 1 轮：用户报告 #1 主变压器 EP-B-001 油温 78°C，异常升高
第 2 轮：AI 询问冷却系统状态，用户反馈一个风扇转速偏慢
第 3 轮：用户补充油位下降 5%
第 4 轮：AI 询问 DGA 历史数据
第 5 轮：用户回复上月 DGA 乙炔略有升高
第 6 轮：AI 建议立即复测 DGA 并降负荷运行
第 7 轮：用户问上次预防性试验时间
```

### 背景信息

#### Memory 的本质：控制传给 LLM 的上下文窗口

很多人以为 Memory 是把数据"存储"起来——其实不是。Memory 的核心作用是**决定每一轮对话中，哪些历史消息会被放进 LLM 的上下文窗口**。

```
没有 Memory：
  第 N 轮 → 只传当前问题 → LLM 不知道之前在聊什么

有 Memory：
  第 N 轮 → 传（历史消息 + 当前问题）→ LLM 知道上下文
```

LLM 本身是无状态的——它不记得上一轮聊了什么。Memory 就是把"该记住的东西"拼回去。

#### 三种 Memory 策略对比

```
BufferMemory（完整历史）
  "记住所有"
  每轮传全部历史消息
  Token 消耗：持续增长（7 轮后可能几千 Token）
  信息完整度：100%
  适合：短对话、需要精确回顾细节的场景

BufferWindowMemory（滑动窗口）
  "只记住最近的 K 轮"
  每轮只传最近 K 轮消息
  Token 消耗：固定上限（K×每轮 Token）
  信息完整度：取决于窗口大小
  适合：长对话、早期信息不需要精确回顾的场景

SummaryMemory（摘要）
  "把旧对话压缩成摘要"
  旧对话 → LLM 生成摘要 → 每轮传（摘要 + 最近几轮）
  Token 消耗：中等
  信息完整度：保留关键信息，可能丢失细节
  适合：长对话、需要记住关键信息但可以接受细节丢失的场景
```

#### 本实验不使用 LangChain 内置 Memory 类

LangChain 提供了 `ConversationBufferMemory`、`ConversationBufferWindowMemory`、`ConversationSummaryMemory` 等内置类，但本实验**手动实现这三种策略**——目的是让你理解内部机制，而不是学会调 API。

---

## 🔬 实验步骤

### Task 1：理解对话场景

**目标**：通读预写的对话，识别哪些信息是"跨轮依赖"的。

**步骤**：

1. 打开 `demo/memory_skeleton.py`，阅读 `CONVERSATION` 列表
2. 找出对话中的跨轮依赖——后面的对话依赖于前面提到的信息：

```
第 1 轮：引出 → EP-B-001、油温 78°C
第 2 轮：引出 → 一个风扇转速偏慢
第 3 轮：引出 → 油位下降 5%
第 4 轮：引用 → "油位下降"（依赖第 3 轮）
第 5 轮：引出 → 上月 DGA 乙炔升高
第 6 轮：引用 → 油温 + 油位 + 乙炔 三者叠加（依赖 1/3/5 轮）
第 7 轮：引用 → "这台变压器"——哪台？（依赖第 1 轮）
```

3. 思考：如果第 7 轮时 AI 已经"忘"了第 1 轮的内容，会发生什么？

**预期结果**：能画出对话的跨轮依赖图，明白"记忆力"在这个场景中的重要性。

---

### Task 2：实现 BufferMemory（完整历史）

**目标**：实现 `test_conversation_buffer_memory`，让 AI 记住全部历史。

**步骤**：

1. 在 `memory_skeleton.py` 中找到 `test_conversation_buffer_memory` 函数
2. 完成实现：

```python
def test_conversation_buffer_memory(llm):
    messages = []
    
    for i, turn in enumerate(CONVERSATION):
        # 1. 把当前消息加入历史
        messages.append({"role": turn["role"], "content": turn["content"]})
        
        # 2. 只对 user 消息触发 AI 回复
        if turn["role"] != "user":
            continue
        
        # 3. 把完整历史传给 LLM
        response = llm.invoke(messages)
        messages.append({"role": "assistant", "content": response.content})
        
        print(f"第 {i+1} 轮 | 上下文长度: {len(str(messages))} 字符")
        print(f"    用户: {turn['content'][:60]}...")
        print(f"    AI: {response.content[:80]}...")
        print()
    
    # 验证记忆：问一个依赖第 1 轮信息的问题
    verify_q = "请回顾一下，我们今天讨论的是哪台设备？它的编号是什么？目前发现了哪些问题？"
    messages.append({"role": "user", "content": verify_q})
    
    response = llm.invoke(messages)
    print(f"\n🧪 记忆验证：")
    print(f"   问题: {verify_q}")
    print(f"   回答: {response.content}")
```

3. 运行并观察：
   - 每轮上下文字符数是否持续增长？
   - 最后一轮验证问题时，AI 能否完整回忆所有信息？

**预期结果**：AI 完整记住 7 轮中的所有信息（设备编号、油温、风扇、油位、乙炔），Token 消耗持续增长。

---

### Task 3：实现 WindowMemory（滑动窗口，K=3）

**目标**：实现 `test_conversation_buffer_window_memory`，只保留最近 3 轮。

**步骤**：

1. 找到 `test_conversation_buffer_window_memory` 函数
2. 完成实现：

```python
def test_conversation_buffer_window_memory(llm):
    messages = []
    WINDOW_SIZE = 6  # K=3 轮 × 2 条消息/轮 = 6 条消息
    
    for i, turn in enumerate(CONVERSATION):
        messages.append({"role": turn["role"], "content": turn["content"]})
        
        if turn["role"] != "user":
            continue
        
        # 关键差异：只传最近 WINDOW_SIZE 条消息
        context = messages[-WINDOW_SIZE:] if len(messages) > WINDOW_SIZE else messages[:]
        
        response = llm.invoke(context)
        messages.append({"role": "assistant", "content": response.content})
        
        print(f"第 {i+1} 轮 | 上下文窗口: {len(context)} 条消息 ({len(str(context))} 字符)")
        print(f"    用户: {turn['content'][:60]}...")
        print(f"    AI: {response.content[:80]}...")
        print()
    
    # 验证记忆：问同一个依赖第 1 轮信息的问题
    verify_q = "请回顾一下，我们今天讨论的是哪台设备？它的编号是什么？目前发现了哪些问题？"
    messages.append({"role": "user", "content": verify_q})
    context = messages[-WINDOW_SIZE:]
    
    response = llm.invoke(context)
    print(f"\n🧪 记忆验证（K=3）：")
    print(f"   问题: {verify_q}")
    print(f"   回答: {response.content}")
```

3. 运行并观察：
   - 第 7 轮时 AI 还能提到 EP-B-001 和油温 78°C 吗？
   - 哪些早期信息丢失了？

**预期结果**：AI 记得最近的讨论（DGA、预防性试验），但忘记了第一轮提到的设备编号和初始油温值。

---

### Task 4：实现 SummaryMemory（摘要模式）

**目标**：实现 `test_conversation_summary_memory`，用 LLM 压缩历史。

**步骤**：

1. 找到 `test_conversation_summary_memory` 函数
2. 完成实现：

```python
def test_conversation_summary_memory(llm):
    messages = []
    summary = ""
    
    for i, turn in enumerate(CONVERSATION):
        messages.append({"role": turn["role"], "content": turn["content"]})
        
        if turn["role"] != "user":
            continue
        
        # 每 3 轮用户消息（即 6 轮对话）后更新摘要
        user_turns = sum(1 for m in messages if m["role"] == "user")
        if user_turns > 0 and user_turns % 3 == 0 and len(messages) >= 6:
            # 让 LLM 总结历史
            summary_prompt = [
                {"role": "system", "content": "请用一段话总结以下排障对话的关键信息：设备编号、故障现象、已排查问题和处理建议。控制在 150 字以内。"},
                {"role": "user", "content": str(messages)},
            ]
            summary = llm.invoke(summary_prompt).content
        
        # 构造上下文：摘要 + 最近 2 轮消息（4 条）
        context = []
        if summary:
            context.append({"role": "system", "content": f"历史对话摘要：{summary}"})
        context.extend(messages[-4:])  # 最近 2 轮
        
        response = llm.invoke(context)
        messages.append({"role": "assistant", "content": response.content})
        
        print(f"第 {i+1} 轮 | 摘要长度: {len(summary)} 字符 | 上下文: {len(str(context))} 字符")
        print(f"    用户: {turn['content'][:60]}...")
        print(f"    AI: {response.content[:80]}...")
        print()
    
    # 验证记忆
    verify_q = "请回顾一下，我们今天讨论的是哪台设备？它的编号是什么？目前发现了哪些问题？"
    context = []
    if summary:
        context.append({"role": "system", "content": f"历史对话摘要：{summary}"})
    context.append({"role": "user", "content": verify_q})
    
    response = llm.invoke(context)
    print(f"\n🧪 记忆验证（Summary）：")
    print(f"   摘要内容: {summary}")
    print(f"   问题: {verify_q}")
    print(f"   回答: {response.content}")
```

3. 运行并观察：
   - 摘要多长？包含了哪些关键信息？
   - 验证问题的回答是否比 WindowMemory 更完整？
   - 有没有细节（如"油位下降 5%"这个精确数字）在摘要中丢失？

**预期结果**：AI 记住关键信息（设备 EP-B-001、油温异常、建议降负荷），但可能丢失精确数值（5%、78°C）。

---

### Task 5：对比三种 Memory 并填写结论表

**目标**：完成 `compare_memory_behaviors` 函数，量化对比。

**步骤**：

1. 完成 `compare_memory_behaviors` 函数
2. 对每种 Memory，用同一个验证问题：

```
"请回顾一下，我们今天讨论的是哪台设备？它的编号是什么？目前发现了哪些问题？"
```

3. 按以下表格记录结果：

| 维度 | BufferMemory | WindowMemory (K=3) | SummaryMemory |
|------|:---:|:---:|:---:|
| 记得设备编号 EP-B-001？ | ✅ | ? | ? |
| 记得油温 78°C？ | ✅ | ? | ? |
| 记得风扇转速偏慢？ | ✅ | ? | ? |
| 记得油位下降 5%？ | ✅ | ? | ? |
| 记得乙炔升高？ | ✅ | ? | ? |
| 第 7 轮上下文大小（字符） | ? | ? | ? |
| 适合什么场景 | ? | ? | ? |

4. 给出你的结论：对于"电力设备排障"这种场景，哪种 Memory 最合适？为什么？

**预期结果**：表格填写完整，有明确的场景选择理由。

---

## 📊 结果产出

| 产出 | 格式 | 位置 | 说明 |
|------|------|------|------|
| 完整 Memory 代码 | `.py` | `demo/memory_skeleton.py` | 三种 Memory 均已实现 |
| 对比表格 | 文本 | Task 5 表格 | 7 个维度的对比结果 |
| 选择建议 | 文本 | Task 5 结论 | 哪种 Memory 适合什么场景 |

---

## 📸 打卡内容

| 序号 | 打卡项 | 具体要求 | 检查 |
|------|--------|----------|------|
| 1 | **BufferMemory 运行截图** | 第 7 轮上下文大小明显增长 + 验证问题回答完整 | ☐ |
| 2 | **WindowMemory 运行截图** | 上下文大小稳定 + 验证问题缺失了哪些早期信息 | ☐ |
| 3 | **SummaryMemory 运行截图** | 摘要内容可见 + 验证问题回答对比 | ☐ |
| 4 | **三种 Memory 对比表格** | Task 5 表格填写完整 | ☐ |

---

## ⚠️ 常见问题

| 问题 | 原因 | 解决方法 |
|------|------|----------|
| SummaryMemory 的摘要太长 | Prompt 没限制字数 | 在摘要 Prompt 中加 `控制在 150 字以内` |
| WindowMemory K=3 验证时依然记住了早期信息 | K 不够小 或 对话不够长 | 把 `WINDOW_SIZE` 改小（如 4），或在更长的对话中测试 |
| 三种 Memory 都正确回答了验证问题 | 对话太短，上下文还没溢出 | 把 CONVERSATION 扩展为 10 轮以上，或把 WINDOW_SIZE 改更小 |
| LLM 在验证问题中"猜测"了设备编号 | LLM 有一定推理能力，从摘要推断出了编号 | 这不算 Memory 失效——关注它是否准确记住了精确数值（油温 78°C） |

---

**🎉 恭喜完成实验！**

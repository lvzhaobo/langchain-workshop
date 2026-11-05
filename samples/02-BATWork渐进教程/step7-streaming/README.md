# Step 7: + 流式输出

**相比 Step 6 新增**：Token 级别流式输出，像 ChatGPT 一样逐字显示。

```
WebSocket / SSE
    │
    ▼
Server ─→ Agent Graph ─→ ChatOpenAI(streaming=True)
    │                            │
    │   node_update              │  token_callback
    ▼                            ▼
前端 (实时渲染)              逐字追加到聊天气泡
```

**新增能力**：
- ✅ **LLM 流式调用**：`streaming=True` + `callbacks` 逐 Token 回调
- ✅ **WebSocket Token 推送**：每个 Token 实时推到前端
- ✅ **打字动画效果**：前端气泡逐字追加显示
- ✅ **执行追踪面板**：仍保留 node 级别进度

**全部能力总览（Step 1 → Step 7）**：
```
✅ Agent Loop 编排   ✅ 工具系统（6个）
✅ 校验-重试回路      ✅ Memory 记忆（ChromaDB + SQLite）
✅ Skill 系统         ✅ Web 界面（BAT Work 风格）
✅ 流式 Token 输出
```

**运行**：
```bash
pip install -r requirements.txt chromadb fastapi uvicorn
python server.py --api-key ollama --base-url http://localhost:11434/v1 --model qwen2.5:0.5b --port 6001
```

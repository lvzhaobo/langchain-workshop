# Step 6: + Web 界面

**相比 Step 5 新增**：BAT Work 暗色主题 Web 界面，FastAPI + WebSocket 流式。

```
浏览器 (localhost:6001)
    │  WebSocket
    ▼
FastAPI server.py ──调用──▶ Agent Graph
```

**新增能力**：
- ✅ **FastAPI 后端**（[server.py](server.py)）：WebSocket 端点 + Agent 调用
- ✅ **三栏布局**：左（文件列表）· 中（对话）· 右（执行追踪面板）
- ✅ **实时执行追踪**：7 个节点的运行状态（pending→running→done）实时展示
- ✅ **暗色主题**：BAT Work 风格配色
- ✅ **Markdown 渲染**：对话气泡支持简单 Markdown

**还不具备**：
- ❌ 无流式 Token 输出（等整个 node 完成才刷新）

**运行**：
```bash
pip install -r requirements.txt chromadb fastapi uvicorn
python server.py --api-key ollama --base-url http://localhost:11434/v1 --model qwen2.5:0.5b --port 6001
# 浏览器打开 http://localhost:6001
```

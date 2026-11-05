# Lab 7.9 — Web UI Flask 封装

> 用 Flask + SSE 把 LangGraph 工作流封装为带界面的 Web 应用，用户可以在浏览器中输入设备故障信息，实时看到诊断过程。

---

## 🎯 实验目标

1. 用 Flask 创建一个 Web 服务，接收用户输入并调用 LangGraph 工作流
2. 实现 SSE（Server-Sent Events）流式返回，用户能看到逐节点执行过程
3. 写一个简洁的 HTML 聊天界面，展示诊断过程和结果

---

## 📋 前置条件

| 序号 | 条件 | 说明 |
|------|------|------|
| 1 | Python 3.9+ | 运行脚本 |
| 2 | 百炼 API Key | LLM 调用需要 |
| 3 | 完成 Lab 7.5 | 有可编译的 StateGraph |
| 4 | 安装依赖 | `pip install flask langchain langchain-openai langgraph` |

---

## 📦 背景信息

### SSE 的原理

SSE 是一种服务器向浏览器单向推送数据的方式，比 WebSocket 简单：

```
浏览器                            Flask 服务器
  │                                   │
  │──── GET /chat/stream ────────────→│
  │                                   │
  │←── data: {"node":"router"} ──────│
  │←── data: {"node":"diagnosis"} ──│
  │←── data: {"node":"solution"} ───│
  │←── data: {"node":"done"} ───────│
  │                                   │
```

每个节点执行完 → Flask 发一条 SSE 消息 → 浏览器逐条展示。

### 架构

```
┌─────────────────────┐     SSE      ┌──────────────────┐
│  index.html         │ ←──────────→ │  Flask app.py    │
│  聊天界面            │   HTTP POST  │  /chat/stream    │
│  逐行展示诊断过程     │              │  调用 LangGraph   │
└─────────────────────┘              └──────────────────┘
```

---

## 🔬 实验步骤

### Task 1：创建 Flask 后端

**目标**：创建 `app.py`，实现 SSE 流式接口。

**步骤**：

1. 创建 `app.py`：

```python
import json
from flask import Flask, request, Response, render_template, stream_with_context
from langgraph_skeleton import build_graph

app = Flask(__name__)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/chat/stream", methods=["POST"])
def chat_stream():
    user_query = request.json.get("query", "")
    
    def generate():
        graph = build_graph()
        
        for event in graph.stream(
            {"user_query": user_query, "messages": []},
        ):
            for node_name, node_output in event.items():
                # 发送节点执行事件
                data = {
                    "node": node_name,
                    "intent": node_output.get("intent", ""),
                    "device_id": node_output.get("device_id", ""),
                    "diagnosis": node_output.get("diagnosis_result", "")[:200],
                    "severity": node_output.get("severity", ""),
                    "solution": node_output.get("solution", "")[:200],
                    "execution": node_output.get("execution_result", "")[:200],
                    "messages": node_output.get("messages", [])[-3:],  # 最近 3 条日志
                }
                yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
        
        yield "data: {\"node\": \"done\"}\n\n"
    
    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
    )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)
```

2. 启动后端：`python app.py`

---

### Task 2：创建前端聊天界面

**目标**：写一个简洁的 HTML 页面，发送请求并逐行展示诊断过程。

**步骤**：

1. 创建 `templates/index.html`：

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>电力设备故障诊断</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; background: #f5f5f5; }
        #chat { background: white; border-radius: 8px; padding: 20px; min-height: 400px; margin-bottom: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
        .msg { margin-bottom: 12px; padding: 8px 12px; border-radius: 6px; line-height: 1.6; }
        .user { background: #e3f2fd; text-align: right; }
        .node { background: #f3e5f5; font-size: 14px; color: #7b1fa2; }
        .done { background: #e8f5e9; color: #2e7d32; font-weight: bold; }
        #input-area { display: flex; gap: 10px; }
        #query { flex: 1; padding: 12px; border: 1px solid #ddd; border-radius: 6px; font-size: 16px; }
        button { padding: 12px 24px; background: #1976d2; color: white; border: none; border-radius: 6px; cursor: pointer; font-size: 16px; }
        button:disabled { background: #ccc; }
        .severity-critical { color: #d32f2f; font-weight: bold; }
        .severity-warning { color: #f57c00; }
        .severity-normal { color: #388e3c; }
    </style>
</head>
<body>
    <h1>⚡ 电力设备故障诊断</h1>
    <p style="color: #666; margin-bottom: 20px;">输入设备故障描述，LangGraph 工作流将逐节点执行诊断</p>
    
    <div id="chat"></div>
    
    <div id="input-area">
        <input id="query" placeholder="例如：EP-D-002 断路器拒分，操作电源正常但分闸失败..." />
        <button onclick="sendQuery()">诊断</button>
    </div>
    
    <script>
        function addMessage(text, className) {
            const div = document.createElement("div");
            div.className = "msg " + className;
            div.innerHTML = text;
            document.getElementById("chat").appendChild(div);
            div.scrollIntoView({ behavior: "smooth" });
        }
        
        async function sendQuery() {
            const query = document.getElementById("query").value.trim();
            if (!query) return;
            
            addMessage(query, "user");
            document.getElementById("query").value = "";
            document.querySelector("button").disabled = true;
            
            const response = await fetch("/chat/stream", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ query }),
            });
            
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = "";
            
            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                
                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split("\n");
                buffer = lines.pop() || "";
                
                for (const line of lines) {
                    if (line.startsWith("data: ")) {
                        const data = JSON.parse(line.slice(6));
                        
                        if (data.node === "done") {
                            addMessage("✅ 诊断完成", "done");
                        } else {
                            const msgs = data.messages || [];
                            const lastMsg = msgs[msgs.length - 1] || "";
                            addMessage(
                                `📍 <strong>${data.node}</strong>: ${lastMsg}`,
                                "node"
                            );
                        }
                    }
                }
            }
            
            document.querySelector("button").disabled = false;
        }
        
        // 回车发送
        document.getElementById("query").addEventListener("keydown", (e) => {
            if (e.key === "Enter") sendQuery();
        });
    </script>
</body>
</html>
```

3. 打开 `http://localhost:5001`，输入故障描述，观察逐节点执行

**预期结果**：浏览器中逐行显示 Router → Diagnosis → Solution → Execute 的执行过程。

---

### Task 3（选做）：美化界面 + 显示更多信息

**目标**：扩展界面，显示诊断结果卡片而非纯文本。

**步骤**：

1. 当 `node === "diagnosis"` 时，展示一个诊断结果卡片，包含严重程度（用颜色区分）
2. 当 `node === "solution"` 时，展示处置方案的步骤列表
3. 当 `node === "execute"` 时，展示最终执行摘要

---

## 📸 打卡内容

| 序号 | 打卡项 | 具体要求 |
|------|--------|----------|
| 1 | **Web 界面截图** | 浏览器中逐节点显示诊断过程 |
| 2 | **完整诊断结果截图** | 输入一个故障描述，看到 Router → Diagnosis → Solution → Execute 全部完成 |
| 3 | **Flask 后端代码截图** | `app.py` 的 SSE 实现 |

---

## ⚠️ 常见问题

| 问题 | 原因 | 解决方法 |
|------|------|----------|
| SSE 流不显示 | 浏览器缓存了响应 | 在 Response 中加 `Cache-Control: no-cache` |
| 前端收不到中间节点 | LangGraph 的 `stream_mode` 不对 | 默认 `stream_mode="values"` 会在每个节点完成后推送 |
| 模板找不到 | Flask 没找到 templates 目录 | 确保 `templates/` 目录和 `app.py` 同级 |

---

**🎉 恭喜完成实验！**

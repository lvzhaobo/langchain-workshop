#!/usr/bin/env python3
"""
BAT Work Web Server — FastAPI 后端 + WebSocket 流式 Agent 执行

Step 6 新增：Web 界面（BAT Work 暗色主题），含 Memory + Skill 支持

启动:
    python server.py --port 6001 --model qwen2.5:0.5b

    # 使用 OpenAI
    python server.py --api-key sk-xxx --model gpt-4o-mini --port 6001

    # 使用本地 Ollama（加载自定义 Skills）
    python server.py --api-key ollama --base-url http://localhost:11434/v1 --model qwen2.5:0.5b --port 6001 --skills-dir ./skills
"""

from __future__ import annotations
import os
import sys
import json
import argparse
import asyncio
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# ─── 构建 Agent Graph ───────────────────────────────────────────

def create_graph(args) -> Any:
    """根据命令行参数构建编译好的 Agent Graph（含 Memory + Skill）"""
    from agent import build_graph  # type: ignore[import-untyped]
    from memory import AgentMemory  # Step 4
    from skill_loader import load_skills  # Step 5

    # 初始化 Memory
    workspace_abs = os.path.abspath(args.workspace)
    memory = AgentMemory(persist_dir=os.path.join(workspace_abs, "..", "memory_data"))

    # 加载 Skills
    skills_dir = args.skills_dir if hasattr(args, 'skills_dir') else "./skills"
    skills = load_skills(skills_dir)
    if skills:
        print(f"🎯 已加载 {len(skills)} 个 Skill")

    return build_graph(
        model_name=args.model,
        api_key=args.api_key,
        base_url=args.base_url,
        memory=memory,
        skills=skills,
    )


# ─── FastAPI App ────────────────────────────────────────────────

app = FastAPI(title="BAT Work Agent")

# 全局 graph 实例（启动时初始化）
graph = None
workspace_path = ""


@app.get("/api/files")
async def list_files():
    """列出工作目录文件"""
    ws = workspace_path
    files = []
    if os.path.exists(ws):
        for f in sorted(os.listdir(ws)):
            full = os.path.join(ws, f)
            if os.path.isfile(full) and not f.startswith("."):
                files.append({
                    "name": f,
                    "size": os.path.getsize(full),
                })
    return {"files": files}


@app.websocket("/ws")
async def websocket_agent(websocket: WebSocket):
    """
    WebSocket 端点 — 接收用户消息，流式返回 Agent 每一步执行结果
    """
    await websocket.accept()

    while True:
        try:
            data = await websocket.receive_text()
        except WebSocketDisconnect:
            break

        try:
            msg = json.loads(data)
        except json.JSONDecodeError:
            await websocket.send_json({"type": "error", "message": "无效的 JSON"})
            continue

        query = msg.get("query", "").strip()
        if not query:
            continue

        # 发送开始信号
        await websocket.send_json({"type": "start", "query": query})

        import uuid
        session_id = str(uuid.uuid4())[:8]
        config = {"configurable": {"thread_id": f"web-{session_id}"}}

        initial_state = {
            "user_input": query,
            "workspace_path": workspace_path,
            "session_id": session_id,
            "intent": "",
            "enriched_context": "",
            "matched_skill": None,
            "plan": [],
            "current_step": 0,
            "tool_results": [],
            "validation_passed": False,
            "validation_feedback": "",
            "retry_count": 0,
            "final_output": "",
            "output_files": [],
        }

        try:
            # 用 astream 流式获取每个节点的状态更新
            async for chunk in graph.astream(initial_state, config, stream_mode="updates"):
                for node_name, node_output in chunk.items():
                    await websocket.send_json({
                        "type": "node_update",
                        "node": node_name,
                        "data": _serialize_node_output(node_name, node_output),
                    })
        except Exception as e:
            await websocket.send_json({"type": "error", "message": str(e)})
            continue

        # 发送完成信号
        await websocket.send_json({"type": "done"})


def _serialize_node_output(node_name: str, output: dict) -> dict:
    """把节点输出转为 JSON 可序列化格式"""
    result = {}
    for k, v in output.items():
        if k == "messages":
            result[k] = [m.content if hasattr(m, "content") else str(m) for m in v[-3:]]
        elif isinstance(v, (str, int, float, bool, type(None))):
            result[k] = v
        elif isinstance(v, list):
            result[k] = v[:50] if len(v) > 50 else v
        elif isinstance(v, dict):
            result[k] = v
        else:
            result[k] = str(v)[:500]
    return result


# ─── 静态文件 ───────────────────────────────────────────────────

@app.get("/")
async def index():
    return FileResponse(os.path.join(os.path.dirname(__file__), "static", "index.html"))


# ─── 入口 ───────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="BAT Work Web Server (Step 6: +Web UI)")
    parser.add_argument("--port", type=int, default=6001, help="服务端口（默认 6001）")
    parser.add_argument("--host", default="0.0.0.0", help="监听地址")
    parser.add_argument("--api-key", help="LLM API Key")
    parser.add_argument("--base-url", help="LLM API 地址")
    parser.add_argument("--model", help="模型名")
    parser.add_argument("--workspace", default="./workspace", help="工作目录")
    parser.add_argument("--skills-dir", default="./skills", help="Skills 目录（Step 5）")

    args = parser.parse_args()

    global graph, workspace_path
    workspace_path = os.path.abspath(args.workspace)

    print("🚀 正在初始化 Agent Graph（含 Memory + Skill）...")
    graph = create_graph(args)
    print(f"✅ Agent 就绪")
    print(f"📂 工作目录: {workspace_path}")
    print(f"🌐 启动 Web 服务: http://localhost:{args.port}")

    import uvicorn
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()

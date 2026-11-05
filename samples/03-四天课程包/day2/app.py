"""Day2 知识库 + 记忆系统 —— RAG 检索 + Memory 读写 + Callback 监控

启动：
    cp .env.example .env   # 填入 DEEPSEEK_API_KEY
    pip install -r requirements.txt
    python app.py          # → http://localhost:8200

三条功能通道（统一 SSE）：
    POST /rag/search       RAG 检索知识库 + LLM 回答
    POST /memory/write     写入长期记忆
    GET  /memory/read      读取长期记忆
    GET  /metrics          Token/延迟监控
"""
import json, os, sys, time
from pathlib import Path
from typing import Iterator

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv()

from flask import Flask, Response, jsonify, render_template, request
from langchain_openai import ChatOpenAI

app = Flask(__name__)

BASE_DIR = Path(__file__).parent
MEMORY_FILE = BASE_DIR / "memory.json"

# ═══ LLM ═══
LLM = ChatOpenAI(
    model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
    streaming=True,
)

# ═══ 页面 ═══
@app.route("/")
def index():
    return render_template("index.html")


# ═══ RAG 检索 ═══
@app.route("/rag/search", methods=["POST"])
def rag_search():
    from agents.tools import load_knowledge
    data = request.get_json() or {}
    q = data.get("question", "")

    def generate() -> Iterator[str]:
        if not os.getenv("DEEPSEEK_API_KEY"):
            yield f"data: {json.dumps({'content': '请先配置 .env 中的 DEEPSEEK_API_KEY'})}\n\n"
            yield "data: [DONE]\n\n"
            return

        # 检索知识库
        docs = load_knowledge(q)
        context = "\n\n".join(docs) if docs else "（知识库无匹配内容）"

        # LLM 基于知识库回答
        prompt = f"根据以下知识库内容回答问题。如果知识库没有相关信息，如实说不知道。\n\n知识库：\n{context}\n\n问题：{q}\n\n回答："
        try:
            for chunk in LLM.stream(prompt):
                if chunk.content:
                    yield f"data: {json.dumps({'content': chunk.content})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'content': f'[错误] {e}'})}\n\n"
        yield "data: [DONE]\n\n"

    return Response(generate(), mimetype="text/event-stream")


# ═══ Memory 读写 ═══
@app.route("/memory/write", methods=["POST"])
def memory_write():
    from agents.tools import write_memory
    data = request.get_json() or {}
    result = write_memory.invoke({"fact": data.get("fact", ""), "category": data.get("category", "general")})
    return jsonify({"status": "ok", "result": result})


@app.route("/memory/read", methods=["GET"])
def memory_read():
    from agents.tools import read_memory
    result = read_memory.invoke({"query": ""})
    return jsonify({"memory": result})


@app.route("/memory/reset", methods=["POST"])
def memory_reset():
    MEMORY_FILE.write_text("[]")
    return jsonify({"status": "ok"})


# ═══ Metrics ═══
_metrics: list[dict] = []

@app.route("/metrics", methods=["GET"])
def metrics():
    return jsonify({"calls": _metrics[-20:], "total": len(_metrics)})


@app.after_request
def track_metrics(response):
    if request.path.startswith("/rag/") and request.method == "POST":
        _metrics.append({"time": time.strftime("%H:%M:%S"), "endpoint": request.path, "status": response.status_code})
    return response


@app.route("/health")
def health():
    api_ok = bool(os.getenv("DEEPSEEK_API_KEY"))
    return jsonify({"status": "ok", "api_configured": api_ok})


if __name__ == "__main__":
    print("Day2 知识库+记忆系统: http://localhost:8200")
    app.run(host="0.0.0.0", port=8200, debug=True)

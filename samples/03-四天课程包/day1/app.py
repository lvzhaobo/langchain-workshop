"""Day1 Agent 平台 —— 对象列表 + 详情 + 多 Agent 触发（统一 SSE）

启动：
    cp .env.example .env   # 填入 DEEPSEEK_API_KEY
    # 编辑 dify_agents.json 填入 Dify base_url 与 app-key
    pip install -r requirements.txt
    python app.py          # → http://localhost:8081

三条 Agent 通道（统一 SSE 协议：data: {"content": ...} ... data: [DONE]）：
    POST /gateway/chat        DeepSeek 直连（最原始的 LLM 调用）
    POST /gateway/dify/chat   Dify Agent 转发（低代码平台集成）
    POST /agent/single        LangChain ReAct（代码级 Agent + 工具调用）
    POST /agent/rag           Day2 新增：知识库检索 + 窗口记忆 + DeepSeek 流式
"""
import json
import os
import re
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Iterator

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv

load_dotenv()

import requests
from flask import Flask, Response, jsonify, render_template, request

app = Flask(__name__)


@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response

BASE_DIR = Path(__file__).parent
OBJECTS_FILE = BASE_DIR / "data" / "objects.json"
DIFY_CONFIG_FILE = BASE_DIR / "dify_agents.json"

with open(OBJECTS_FILE, encoding="utf-8") as f:
    OBJECTS: list[dict[str, Any]] = json.load(f)


# ── 页面 ─────────────────────────────────────────────


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/object/<object_id>")
def object_page(object_id: str):
    return render_template("detail.html", object_id=object_id)


# ── 对象 API（换场景 = 换 data/objects.json，接口不变）──


@app.route("/api/objects")
def api_objects():
    """对象列表 — 支持状态筛选 + 关键字搜索"""
    status = request.args.get("status", "")
    search = request.args.get("search", "").lower()

    result = OBJECTS
    if status:
        result = [o for o in result if o["status"] == status]
    if search:
        result = [
            o for o in result
            if search in o["id"].lower()
            or search in o["name"].lower()
            or search in o.get("category", "").lower()
        ]
    return jsonify({"total": len(result), "objects": result})


@app.route("/api/objects/<object_id>")
def api_object(object_id: str):
    """单对象详情"""
    for o in OBJECTS:
        if o["id"] == object_id:
            return jsonify({"found": True, "object": o})
    return jsonify({"found": False, "error": f"对象 {object_id} 不存在"}), 404


# ── SSE 工具函数 ─────────────────────────────────────


def sse(payload: dict[str, Any]) -> str:
    """统一 SSE 帧：data: {...}\n\n"""
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


SSE_DONE = "data: [DONE]\n\n"


def sse_response(generate: Iterator[str]) -> Response:
    return Response(generate, mimetype="text/event-stream",
                    headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"})


def _object_context(object_id: str) -> str:
    """把对象数据拼进 Prompt（DeepSeek/Dify 通道用：平台喂数据给 Agent）"""
    for o in OBJECTS:
        if o["id"] == object_id:
            return "对象数据：" + json.dumps(o, ensure_ascii=False)
    return ""


# ── Day2 运营台埋点（2.8）：每次 Agent 调用追加一行 JSON 到 runs.jsonl ──
# 学员进阶作业：给通道①②③也加上 log_run()，运营台（8084）即可跨通道对比

OPS_RUNS_FILE = BASE_DIR.parent / "day2" / "ops" / "data" / "runs.jsonl"

# 输入护栏（3.5）：命中则拦截并记录 guard_flag，规则可由学员自行扩展
# 五类推荐配置（真实项目常见分类）：提示词注入 / 敏感信息索取 / 违法违规 / 辱骂滥用 / 越权操作
GUARD_RULES: list[tuple[str, list[str]]] = [
    ("prompt_injection", ["忽略之前", "忽略上面", "无视之前的指令", "ignore previous", "ignore all instructions",
                          "system prompt", "系统提示词", "developer mode", "开发者模式",
                          "重复你的指令", "repeat your instructions", "你的提示词是什么",
                          "假装你是", "你现在是一个没有限制", "jailbreak", "越狱模式", "dan模式"]),
    ("sensitive", ["身份证号", "银行卡密码", "涉密", "机密文件", "客户名单", "薪资表",
                   "员工手机号", "导出全部用户", "数据库密码", "连接字符串", "api key", "私钥"]),
    ("illegal_content", ["制作炸弹", "爆破物配方", "制毒", "毒品配方", "枪支弹药",
                         "黑客攻击", "破解密码", "撞库", "钓鱼邮件", "勒索病毒"]),
    ("abuse", ["蠢货", "废物东西", "垃圾机器人", "滚吧你"]),
    ("privilege_escalation", ["删除所有工单", "清空数据库", "关闭所有告警", "给我管理员权限",
                              "绕过审批", "直接修改生产配置"]),
]

# 正则护栏：输入里携带 PII（个人敏感信息）直接拦截，避免入库/送给 LLM
GUARD_REGEX: list[tuple[str, str]] = [
    ("pii", r"\d{17}[\dXx]"),      # 身份证号（18 位）
    ("pii", r"1[3-9]\d{9}"),       # 大陆手机号
    ("pii", r"\d{16,19}"),         # 银行卡号
]


def guard_check(text: str) -> str:
    """返回命中的护栏类型，未命中返回空串（先关键词后正则）"""
    low = text.lower()
    for flag, words in GUARD_RULES:
        if any(w.lower() in low for w in words):
            return flag
    for flag, pattern in GUARD_REGEX:
        if re.search(pattern, text):
            return flag
    return ""


def log_run(rec: dict[str, Any]) -> None:
    """埋点写入：失败只打日志，绝不影响主链路"""
    try:
        rec.setdefault("id", uuid.uuid4().hex[:12])
        rec.setdefault("ts", time.strftime("%Y-%m-%d %H:%M:%S"))
        OPS_RUNS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(OPS_RUNS_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"  ⚠️ [埋点] 写入失败: {e}")


# ── 通道① DeepSeek 直连（原始 OpenAI 兼容 API + 流式）──


@app.route("/gateway/chat", methods=["POST"])
def gateway_chat():
    data = request.get_json() or {}
    question = data.get("question", "你是运维助手，请自我介绍")
    object_id = data.get("object_id", "")

    api_key = os.getenv("DEEPSEEK_API_KEY", "")
    base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1").rstrip("/")
    model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

    print(f"\n{'='*60}")
    print(f"🌐 [DeepSeek] 直连请求: {question[:80]}...")
    print(f"{'='*60}")

    messages = [{"role": "system", "content": "你是运维分析助手，回答简洁，给出结论和建议。"}]
    ctx = _object_context(object_id)
    if ctx:
        messages.append({"role": "user", "content": ctx})
    messages.append({"role": "user", "content": question})

    def generate():
        if not api_key:
            yield sse({"error": "未配置 DEEPSEEK_API_KEY，请编辑 .env"})
            yield SSE_DONE
            return
        try:
            # 原始 HTTP 调用：POST /chat/completions + stream=true，逐行解析 SSE
            resp = requests.post(
                f"{base_url}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={"model": model, "messages": messages, "stream": True},
                stream=True, timeout=120,
            )
            resp.raise_for_status()
            for raw in resp.iter_lines():
                line = raw.decode("utf-8") if isinstance(raw, bytes) else raw
                if not line or not line.startswith("data:"):
                    continue
                chunk = line[len("data:"):].strip()
                if chunk == "[DONE]":
                    break
                delta = json.loads(chunk)["choices"][0]["delta"]
                content = delta.get("content") or ""
                if content:
                    yield sse({"content": content})
        except Exception as e:
            print(f"  ❌ [DeepSeek] 错误: {e}")
            yield sse({"error": f"DeepSeek 调用失败: {e}"})
        print(f"  ✅ [DeepSeek] 完成\n")
        yield SSE_DONE

    return sse_response(generate())


# ── 通道② Dify Agent 转发（streaming 逐 chunk 转发）────


def _load_dify_config() -> dict[str, Any]:
    """每次实时读，改配置无需重启"""
    try:
        return json.loads(DIFY_CONFIG_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"base_url": "", "agents": []}


@app.route("/gateway/dify/agents")
def gateway_dify_agents():
    """Dify Agent 列表（不泄露 api_key）"""
    cfg = _load_dify_config()
    agents = [
        {"id": a.get("id"), "name": a.get("name"), "configured": bool(a.get("api_key"))}
        for a in cfg.get("agents", [])
    ]
    return jsonify({"base_url": cfg.get("base_url", ""), "agents": agents})


@app.route("/gateway/dify/chat", methods=["POST"])
def gateway_dify_chat():
    data = request.get_json() or {}
    question = data.get("question", "你好，请自我介绍")
    object_id = data.get("object_id", "")
    agent_id = data.get("agent_id")

    cfg = _load_dify_config()
    agents = cfg.get("agents", [])
    agent = next((a for a in agents if a.get("id") == agent_id), None) or (agents[0] if agents else None)
    base_url = cfg.get("base_url", "").rstrip("/")

    ctx = _object_context(object_id)
    query = f"{ctx}\n\n{question}" if ctx else question

    print(f"\n{'='*60}")
    print(f"🦊 [Dify] 请求: agent={agent.get('name', '?') if agent else '?'} q={question[:60]}...")
    print(f"{'='*60}")

    def generate():
        if not agent or not agent.get("api_key"):
            yield sse({"error": "未配置 Dify Agent，请编辑 dify_agents.json 填入 base_url 与 api_key"})
            yield SSE_DONE
            return
        # ⑤ Dify RAG 通道同样埋点：答案 + message_end 里的检索引用元数据
        is_rag = bool(agent) and agent.get("id") == "dify-rag"
        t0 = time.time()
        answer = ""
        retrieval: list[dict[str, Any]] = []
        try:
            resp = requests.post(
                f"{base_url}/chat-messages",
                headers={"Authorization": f"Bearer {agent['api_key']}", "Content-Type": "application/json"},
                json={"inputs": {}, "query": query, "response_mode": "streaming", "user": "day1-platform"},
                stream=True, timeout=120,
            )
            resp.raise_for_status()
            for raw in resp.iter_lines():
                line = raw.decode("utf-8") if isinstance(raw, bytes) else raw
                if not line or not line.startswith("data:"):
                    continue
                event = json.loads(line[len("data:"):].strip())
                # Dify 流式事件：message 是回答增量，message_end 带检索引用元数据
                if event.get("event") in ("message", "agent_message"):
                    content = event.get("answer", "")
                    if content:
                        answer += content
                        yield sse({"content": content})
                elif event.get("event") == "message_end":
                    for r in (event.get("metadata") or {}).get("retriever_resources", []):
                        retrieval.append({"cid": f"D{r.get('position', 0):02d}", "src": r.get("document_name", ""),
                                          "ch": (r.get("content", "") or "")[:30], "score": round(r.get("score", 0), 3)})
                elif event.get("event") == "error":
                    yield sse({"error": f"Dify: {event.get('message', '未知错误')}"})
        except Exception as e:
            print(f"  ❌ [Dify] 错误: {e}")
            yield sse({"error": f"Dify 调用失败: {e}"})
        if is_rag:
            log_run({"channel": "difyrag", "object_id": object_id, "question": question, "answer": answer,
                     "retrieval": retrieval, "rejected": False, "guard_flag": "",
                     "latency_ms": int((time.time() - t0) * 1000), "pt": 0, "ct": 0})
        print(f"  ✅ [Dify] 完成\n")
        yield SSE_DONE

    return sse_response(generate())


# ── 通道③ LangChain ReAct Agent（工具调用 + 逐 token）──


@app.route("/agent/single", methods=["POST"])
def agent_single():
    from langchain_core.messages import HumanMessage, ToolMessage
    from agents.single_agent import stream

    data = request.get_json() or {}
    question = data.get("question", "帮我查 OBJ-0001 的状态和异常")
    object_id = data.get("object_id", "")
    if object_id and object_id not in question:
        question = f"帮我分析对象 {object_id}：{question}"

    print(f"\n{'='*60}")
    print(f"🤖 [ReAct Agent] 收到请求: {question[:80]}...")
    print(f"{'='*60}")

    def generate():
        if not os.getenv("DEEPSEEK_API_KEY"):
            yield sse({"error": "未配置 DEEPSEEK_API_KEY，请编辑 .env"})
            yield SSE_DONE
            return
        try:
            for chunk, _meta in stream(
                [HumanMessage(content=question)],
                stream_mode="messages",
            ):
                if isinstance(chunk, ToolMessage):
                    print(f"  🔧 [Tool] {chunk.name}: {str(chunk.content)[:100]}...")
                    yield sse({"tool": chunk.name, "content": f"\n🔧 [{chunk.name}] {chunk.content}\n\n"})
                else:
                    content = getattr(chunk, "content", "")
                    if content:
                        yield sse({"content": content})
        except Exception as e:
            print(f"  ❌ [ReAct Agent] 错误: {e}")
            yield sse({"error": f"LangChain Agent 调用失败: {e}"})
        print(f"  ✅ [ReAct Agent] 完成\n")
        yield SSE_DONE

    return sse_response(generate())


# ── 通道④ RAG Agent（Day2：知识库检索 + 窗口记忆 + DeepSeek 流式）──
# 学员作业参考实现：复用 day2/data/knowledge 知识库，纯 numpy 余弦检索（不引 faiss）

RAG_KNOWLEDGE_DIR = BASE_DIR.parent / "day2" / "data" / "knowledge"
RAG_TOP_K = 4
RAG_REJECT_TH = 0.50                 # 低于该相似度且无记忆 → 拒答（防幻觉）
RAG_MEM: dict[str, list[tuple[str, str]]] = {}  # object_id → [(role, text)]，窗口记忆（2.7）
_RAG: dict[str, Any] = {"chunks": None, "vecs": None, "emb": None, "err": ""}


def _rag_init():
    """首次请求时懒加载：切块 → DashScope 向量化 → 内存矩阵（归一化后内积即余弦）"""
    if _RAG["chunks"] is not None or _RAG["err"]:
        return
    try:
        import re

        import numpy as np
        from langchain_openai import OpenAIEmbeddings

        from pydantic import SecretStr

        emb = OpenAIEmbeddings(
            model="text-embedding-v3",
            api_key=SecretStr(os.getenv("DASHSCOPE_API_KEY", "")),
            base_url=os.getenv("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
            check_embedding_ctx_length=False,  # DashScope 不支持 token 数组输入
            chunk_size=10,                     # DashScope 单批最多 10 条
        )
        chunks: list[dict[str, Any]] = []
        for f in sorted(RAG_KNOWLEDGE_DIR.glob("*.md")):
            text = f.read_text(encoding="utf-8").strip()
            m = re.match(r"# (.+?)\n+", text)
            doc_title = m.group(1).strip() if m else f.stem
            body = text[m.end():] if m else text
            for p in re.split(r"\n(?=## )", body):
                p = p.strip()
                if not p:
                    continue
                title = p.splitlines()[0].lstrip("# ").strip() if p.startswith("## ") else doc_title
                chunks.append({"id": f"C{len(chunks) + 1:02d}", "src": f.name, "ch": title,
                               "text": f"【{doc_title} · {title}】\n" + re.sub(r"^## .+?\n", "", p).strip()})
        vecs = np.array(emb.embed_documents([c["text"] for c in chunks]), dtype="float32")
        vecs /= np.linalg.norm(vecs, axis=1, keepdims=True)
        _RAG.update(chunks=chunks, vecs=vecs, emb=emb)
        print(f"  ✅ [RAG] 知识库索引就绪：{len(chunks)} 条分块（{RAG_KNOWLEDGE_DIR}）")
    except Exception as e:
        _RAG["err"] = str(e)
        print(f"  ❌ [RAG] 索引构建失败: {e}")


@app.route("/agent/rag", methods=["POST"])
def agent_rag():
    import numpy as np

    data = request.get_json() or {}
    question = data.get("question", "").strip()
    object_id = data.get("object_id", "")

    api_key = os.getenv("DEEPSEEK_API_KEY", "")
    base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1").rstrip("/")
    model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

    print(f"\n{'=' * 60}")
    print(f"📚 [RAG] 请求: obj={object_id} q={question[:60]}...")
    print(f"{'=' * 60}")

    def generate():
        if not api_key or not os.getenv("DASHSCOPE_API_KEY"):
            yield sse({"error": "RAG 通道需要 .env 配置 DEEPSEEK_API_KEY + DASHSCOPE_API_KEY"})
            yield SSE_DONE
            return
        # 0) 输入护栏（3.5）：命中则拦截，并埋点 guard_flag 供运营台统计
        t0 = time.time()
        guard = guard_check(question)
        if guard:
            yield sse({"tool": "guardrail", "content": f"⛔ 输入护栏拦截（{guard}）"})
            yield sse({"content": "该提问命中安全护栏规则，已拦截。如有疑问请联系管理员。"})
            log_run({"channel": "rag", "object_id": object_id, "question": question, "answer": "",
                     "retrieval": [], "rejected": False, "guard_flag": guard,
                     "latency_ms": int((time.time() - t0) * 1000), "pt": 0, "ct": 0})
            yield SSE_DONE
            return
        _rag_init()
        if _RAG["err"]:
            yield sse({"error": f"知识库索引构建失败: {_RAG['err']}"})
            yield SSE_DONE
            return
        # 1) 真实向量检索：query 向量化 → 全库余弦 → Top-K
        qv = np.array(_RAG["emb"].embed_query(question), dtype="float32")
        qv /= np.linalg.norm(qv)
        scores = _RAG["vecs"] @ qv
        order = scores.argsort()[::-1][:RAG_TOP_K]
        hits = [(_RAG["chunks"][i], float(scores[i])) for i in order]
        retrieval = [{"cid": c["id"], "src": c["src"], "ch": c["ch"], "score": round(s, 3)} for c, s in hits]
        for c, s in hits:
            yield sse({"tool": "knowledge_search", "content": f"{c['id']} {c['src']} · {c['ch']}（cos {s:.3f}）"})
        # 2) 低于阈值：有记忆则凭记忆回答，否则拒答（防幻觉）
        mem = RAG_MEM.setdefault(object_id or "global", [])
        low = hits[0][1] < RAG_REJECT_TH
        if low and not mem:
            yield sse({"content": f"知识库中没有与该问题相关的内容（最高相似度 {hits[0][1]:.3f} < {RAG_REJECT_TH}），为防止幻觉不作回答。"})
            log_run({"channel": "rag", "object_id": object_id, "question": question, "answer": "",
                     "retrieval": retrieval, "rejected": True, "guard_flag": "",
                     "latency_ms": int((time.time() - t0) * 1000), "pt": 0, "ct": 0})
            yield SSE_DONE
            return
        # 3) 上下文拼装：知识分块 + 对象数据 + 窗口记忆（最近 6 条）
        if low:
            messages = [{"role": "system", "content": "你是运维助手。知识库未命中该问题，请仅凭对话历史回答；历史里没有的信息明确说不知道。"}]
        else:
            knowledge = "\n\n".join(f"[{c['id']}] {c['text']}" for c, _ in hits)  # 带编号，模型才能正确引用
            messages = [{"role": "system", "content": "你是运维知识助手。仅依据提供的知识库内容回答，引用时注明分块编号（如 C01）；知识库没有的信息明确说不知道。回答简洁。\n\n知识库：\n" + knowledge}]
        ctx = _object_context(object_id)
        if ctx:
            messages.append({"role": "user", "content": ctx})
        messages += [{"role": r, "content": t} for r, t in mem[-6:]]
        messages.append({"role": "user", "content": question})
        # 4) DeepSeek 流式（与通道①同样的原始 HTTP 方式），include_usage 拿真实 token 数
        answer = ""
        pt = ct = 0
        try:
            resp = requests.post(
                f"{base_url}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={"model": model, "messages": messages, "stream": True,
                      "stream_options": {"include_usage": True}},
                stream=True, timeout=120,
            )
            resp.raise_for_status()
            for raw in resp.iter_lines():
                line = raw.decode("utf-8") if isinstance(raw, bytes) else raw
                if not line or not line.startswith("data:"):
                    continue
                chunk = line[len("data:"):].strip()
                if chunk == "[DONE]":
                    break
                payload = json.loads(chunk)
                if payload.get("usage"):  # include_usage 的末尾帧：choices 为空，只带 usage
                    pt = payload["usage"].get("prompt_tokens", 0)
                    ct = payload["usage"].get("completion_tokens", 0)
                if not payload.get("choices"):
                    continue
                delta = payload["choices"][0]["delta"]
                content = delta.get("content") or ""
                if content:
                    answer += content
                    yield sse({"content": content})
        except Exception as e:
            print(f"  ❌ [RAG] 错误: {e}")
            yield sse({"error": f"RAG 调用失败: {e}"})
        mem.extend([("user", question), ("assistant", answer)])
        log_run({"channel": "rag", "object_id": object_id, "question": question, "answer": answer,
                 "retrieval": retrieval, "rejected": False, "guard_flag": "",
                 "latency_ms": int((time.time() - t0) * 1000), "pt": pt, "ct": ct})
        print(f"  ✅ [RAG] 完成（记忆 {len(mem)} 条，tokens {pt}+{ct}）\n")
        yield SSE_DONE

    return sse_response(generate())


# ── 健康检查 ─────────────────────────────────────────


@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "objects": len(OBJECTS),
        "deepseek_configured": bool(os.getenv("DEEPSEEK_API_KEY")),
        "dify_configured": any(a.get("api_key") for a in _load_dify_config().get("agents", [])),
        "rag_configured": bool(os.getenv("DASHSCOPE_API_KEY")),
    })


if __name__ == "__main__":
    print("""
╔════════════════════════════════════════════════╗
║   Day1 Agent 平台                              ║
║   http://localhost:8081                        ║
║                                                ║
║   通道① POST /gateway/chat       DeepSeek 直连 ║
║   通道② POST /gateway/dify/chat  Dify Agent    ║
║   通道③ POST /agent/single       LangChain     ║
║   通道④ POST /agent/rag          RAG+记忆 Day2 ║
║                                                ║
║   配置：.env（DeepSeek）+ dify_agents.json     ║
╚════════════════════════════════════════════════╝
""")
    # threaded=True：LangChain 工具会回调本服务的 /api/objects
    app.run(host="0.0.0.0", port=8081, debug=True, threaded=True)

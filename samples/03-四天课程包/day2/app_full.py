"""Day2 知识库 + 记忆系统 —— 完整真实版（真 Embedding + 真 LLM + 真 Token 计费）

启动：
    pip install -r requirements.txt
    python app_full.py     # → http://localhost:8082

与 app.py（简化版 8200）的区别：全部走真实链路
    2.1/2.2  FAISS + DashScope text-embedding-v3 真向量检索
    2.3      /api/sim   真实 1024 维向量余弦相似度拆解
    2.5      /api/chat  检索 → DeepSeek 真流式回答（SSE）
    2.7      服务端维护 4 种记忆策略，摘要由真 LLM 压缩
    2.8      真实 token_usage 成本追踪（/api/cost）
    2.9      LLM 缓存（重复问题 0 Token 秒回）
    2.10     /api/eval  评测集真跑检索命中率
    2.11     /api/sql   LLM 生成 SQL → SQLite 真执行 → LLM 总结
"""
import json, os, re, sqlite3, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

import numpy as np
from flask import Flask, Response, jsonify, render_template, request
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

app = Flask(__name__)
BASE_DIR = Path(__file__).parent
KNOWLEDGE_DIR = BASE_DIR / "data" / "knowledge"

WINDOW_K = 6      # ②窗口记忆保留条数
SUMMARY_N = 3     # ③每 N 轮 LLM 压缩一次摘要
TOP_K = 4         # 检索返回条数（可通过 /api/config 在前端拖拽调整）
REJECT_TH = 0.50  # 余弦相似度低于该值拒答（embedding 空间有 0.4 左右底噪，真实命中普遍 0.6+）

# ═══ LLM（DeepSeek，真流式 + 真 token 用量） ═══
LLM = ChatOpenAI(
    model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
    streaming=True, stream_usage=True, temperature=0.3,
)

# ═══ Embeddings（DashScope text-embedding-v3，OpenAI 兼容模式） ═══
# 三个兼容要点：国内 base_url / check_embedding_ctx_length=False / chunk_size<=10
EMB = None
EMB_ERR = ""
try:
    if os.getenv("DASHSCOPE_API_KEY"):
        EMB = OpenAIEmbeddings(
            model="text-embedding-v3",
            api_key=os.getenv("DASHSCOPE_API_KEY"),
            base_url=os.getenv("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
            check_embedding_ctx_length=False,
            chunk_size=10,
        )
    else:
        EMB_ERR = "未配置 DASHSCOPE_API_KEY"
except Exception as e:
    EMB_ERR = str(e)


# ═══ 知识库：切块 → 向量化 → FAISS 入库（2.1） ═══
def load_chunks() -> list[dict]:
    chunks, idx = [], 0
    for f in sorted(KNOWLEDGE_DIR.glob("*.md")):
        text = f.read_text(encoding="utf-8").strip()
        # 提取文档标题（# 行），正文按 ## 二级标题切块（每块 = 一个知识点）
        m = re.match(r"# (.+?)\n+", text)
        doc_title = m.group(1).strip() if m else f.stem
        body = text[m.end():] if m else text
        for p in re.split(r"\n(?=## )", body):
            p = p.strip()
            if not p:
                continue  # 标题下没有引言正文时跳过
            idx += 1
            title = p.splitlines()[0].lstrip("# ").strip() if p.startswith("## ") else doc_title
            chunks.append({"id": f"C{idx:02d}", "src": f.name, "ch": title,
                           "text": f"【{doc_title} · {title}】\n" + re.sub(r"^## .+?\n", "", p).strip()})
    return chunks

CHUNKS = load_chunks()
INDEX = None          # FAISS IndexFlatIP（归一化后内积 = 余弦）
CHUNK_VECS = None     # (n, dim) 归一化向量矩阵

def build_index():
    global INDEX, CHUNK_VECS, EMB_ERR
    if EMB is None:
        return
    try:
        import faiss
        vecs = np.array(EMB.embed_documents([c["text"] for c in CHUNKS]), dtype="float32")
        vecs /= np.linalg.norm(vecs, axis=1, keepdims=True)
        INDEX = faiss.IndexFlatIP(vecs.shape[1])
        INDEX.add(vecs)
        CHUNK_VECS = vecs
        print(f"✅ FAISS 索引就绪：{len(CHUNKS)} 条分块 × {vecs.shape[1]} 维（text-embedding-v3）")
    except Exception as e:
        EMB_ERR = f"建索引失败：{e}"
        print(f"❌ {EMB_ERR}")

def embed_query(q: str) -> np.ndarray:
    v = np.array(EMB.embed_query(q), dtype="float32")
    return v / np.linalg.norm(v)

def retrieve(q: str, top_k: int | None = None) -> tuple[list[dict], np.ndarray]:
    """真实向量检索：返回 [{chunk, score}] 与 query 向量"""
    top_k = top_k or TOP_K
    qv = embed_query(q)
    scores, ids = INDEX.search(qv.reshape(1, -1), top_k)
    hits = [{"chunk": CHUNKS[i], "score": float(s)} for s, i in zip(scores[0], ids[0]) if i >= 0]
    return hits, qv


# ═══ 记忆（2.7）：服务端维护，摘要走真 LLM ═══
MEM = {"all": [], "summaries": [], "turn": 0}

def summarize_recent() -> dict:
    """每 SUMMARY_N 轮：真 LLM 压缩最近几轮为一段摘要"""
    recent = MEM["all"][-SUMMARY_N * 2:]
    convo = "\n".join(f"{'用户' if m['role']=='user' else '助手'}：{m['content'][:150]}" for m in recent)
    prompt = f"把以下 {SUMMARY_N} 轮运维问答压缩成一段 60 字以内的中文摘要，保留关键结论：\n{convo}"
    t0 = time.time()
    resp = LLM.invoke(prompt)
    usage = resp.usage_metadata or {}
    track_cost("（记忆摘要压缩）", time.time() - t0, usage, kind="summary")
    s = MEM["turn"] - SUMMARY_N + 1
    entry = {"range": f"第{s}~{MEM['turn']}轮", "text": resp.content.strip()}
    MEM["summaries"].append(entry)
    return entry

def push_turn(uq: str, ans: str) -> dict:
    """记一轮对话，返回四种策略的变化说明（前端黄条展示）"""
    MEM["turn"] += 1
    MEM["all"].append({"turn": MEM["turn"], "role": "user", "content": uq})
    MEM["all"].append({"turn": MEM["turn"], "role": "assistant", "content": ans[:200]})
    deltas = [f"①全量 +2 条（累计 {len(MEM['all'])}）"]
    over = len(MEM["all"]) - WINDOW_K
    if over > 0:
        deltas.append(f"②窗口 移出 {min(2, over)} 条旧消息（只留最近 {WINDOW_K} 条）")
    else:
        deltas.append(f"②窗口 +2 条（{len(MEM['all'])}/{WINDOW_K} 未满）")
    new_summary = None
    if MEM["turn"] % SUMMARY_N == 0:
        new_summary = summarize_recent()
        deltas.append(f"③摘要 <b>+1 段</b>（真 LLM 压缩：{new_summary['text'][:24]}…）")
    else:
        deltas.append(f"③摘要 缓冲 {MEM['turn'] % SUMMARY_N}/{SUMMARY_N} 轮")
    deltas.append(f"④混合 = {len(MEM['summaries'])} 段摘要 + 最近 {min(len(MEM['all']), WINDOW_K)} 条原文")
    return {"turn": MEM["turn"], "deltas": deltas}

def memory_context() -> str:
    """④混合策略：摘要 + 窗口原文，拼入 Prompt（真实生效）"""
    parts = []
    if MEM["summaries"]:
        parts.append("【历史摘要】" + "；".join(s["text"] for s in MEM["summaries"]))
    win = MEM["all"][-WINDOW_K:]
    if win:
        parts.append("【近期对话】" + "\n".join(
            f"{'用户' if m['role']=='user' else '助手'}：{m['content'][:120]}" for m in win))
    return "\n".join(parts)


# ═══ 成本（2.8）+ 缓存（2.9） ═══
COST = {"calls": []}
CACHE: dict[str, dict] = {}
PRICE_IN, PRICE_OUT = 2e-7, 8e-7  # DeepSeek 参考价 $/token

def track_cost(q: str, elapsed: float, usage: dict, kind="chat", cached=False):
    pt = usage.get("input_tokens", 0)
    ct = usage.get("output_tokens", 0)
    COST["calls"].append({
        "time": time.strftime("%H:%M:%S"), "q": q[:20], "kind": kind,
        "elapsed": round(elapsed, 2), "pt": pt, "ct": ct,
        "cost": pt * PRICE_IN + ct * PRICE_OUT, "cached": cached,
    })


def sse(obj) -> str:
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"


# ═══ 页面 ═══
@app.route("/")
def index():
    return render_template("full.html")


@app.route("/api/health")
def health():
    return jsonify({
        "llm": bool(os.getenv("DEEPSEEK_API_KEY")),
        "embedding": INDEX is not None,
        "embedding_err": EMB_ERR,
        "chunks": len(CHUNKS),
        "dim": int(CHUNK_VECS.shape[1]) if CHUNK_VECS is not None else 0,
    })


# ═══ /api/chat：真实 RAG 链路（2.1+2.5+2.7+2.8+2.9），SSE ═══
@app.route("/api/chat", methods=["POST"])
def chat():
    q = (request.get_json() or {}).get("question", "").strip()

    def gen():
        if INDEX is None:
            yield sse({"type": "error", "msg": f"向量索引未就绪：{EMB_ERR}"})
            return
        # ── 2.9 缓存命中：0 Token 秒回（缓存键含 top_k，调整 Top-K 后不会误命旧答案）──
        ck = f"{TOP_K}|{q}"
        if ck in CACHE:
            hit = CACHE[ck]
            t0 = time.time()
            yield sse({"type": "sources", "sources": hit["sources"], "cached": True})
            yield sse({"type": "content", "content": hit["answer"]})
            track_cost(q, time.time() - t0, {}, cached=True)
            delta = push_turn(q, hit["answer"])
            yield sse({"type": "done", "cached": True, "usage": {"pt": 0, "ct": 0},
                       "elapsed": 0.01, "delta": delta, "memory": MEM})
            return

        t0 = time.time()
        # ── 2.1 真实向量检索 ──
        hits, _ = retrieve(q)
        sources = [{"id": h["chunk"]["id"], "src": h["chunk"]["src"], "ch": h["chunk"]["ch"],
                    "text": h["chunk"]["text"][:80], "score": round(h["score"], 4)} for h in hits]
        yield sse({"type": "sources", "sources": sources, "elapsed_retrieve": round(time.time() - t0, 2)})

        best = hits[0]["score"] if hits else 0
        if best < REJECT_TH:
            # 未命中知识库：若有对话记忆则走"记忆问答"（真 LLM 仅凭记忆回答，验证 2.7 记忆生效），否则拒答防幻觉
            if MEM["all"]:
                mem_ctx = memory_context()
                prompt = ("你是 5G 基站运维助手。知识库中没有与该问题相关的内容。"
                          "如果问题是在询问之前的对话（如\"刚才问了什么\"），请根据下面的对话记忆如实回答；"
                          "否则明确说知识库没有相关信息。回答简洁。\n\n"
                          f"对话记忆：\n{mem_ctx}\n\n问题：{q}\n\n回答：")
                answer, usage = "", {}
                try:
                    for chunk in LLM.stream(prompt):
                        if chunk.content:
                            answer += chunk.content
                            yield sse({"type": "content", "content": chunk.content})
                        if chunk.usage_metadata:
                            usage = chunk.usage_metadata
                except Exception as e:
                    yield sse({"type": "error", "msg": str(e)})
                    return
                elapsed = time.time() - t0
                track_cost(q, elapsed, usage)
                delta = push_turn(q, answer)
                yield sse({"type": "done", "cached": False, "memory_only": True,
                           "usage": {"pt": usage.get("input_tokens", 0), "ct": usage.get("output_tokens", 0)},
                           "elapsed": round(elapsed, 2), "delta": delta, "memory": MEM})
                return
            ans = f"知识库中没有与该问题足够相关的内容（最高相关度 {best:.2f} < 阈值 {REJECT_TH}），拒绝作答以避免幻觉。"
            yield sse({"type": "content", "content": ans})
            track_cost(q, time.time() - t0, {})
            delta = push_turn(q, ans)
            yield sse({"type": "done", "cached": False, "usage": {"pt": 0, "ct": 0},
                       "elapsed": round(time.time() - t0, 2), "delta": delta, "memory": MEM,
                       "rejected": True})
            return

        # ── 2.5 + 2.7：知识库上下文 + ④混合记忆 → DeepSeek 真流式 ──
        context = "\n\n".join(f"[{h['chunk']['id']} {h['chunk']['src']}] {h['chunk']['text']}" for h in hits)
        mem_ctx = memory_context()
        prompt = (
            "你是 5G 基站运维助手。仅根据知识库内容回答，如果知识库没有相关信息就如实说不知道。回答简洁分点，重点数值加粗（**x**）。\n\n"
            + (f"对话记忆（可用于理解指代）：\n{mem_ctx}\n\n" if mem_ctx else "")
            + f"知识库：\n{context}\n\n问题：{q}\n\n回答："
        )
        answer, usage = "", {}
        try:
            for chunk in LLM.stream(prompt):
                if chunk.content:
                    answer += chunk.content
                    yield sse({"type": "content", "content": chunk.content})
                if chunk.usage_metadata:
                    usage = chunk.usage_metadata
        except Exception as e:
            yield sse({"type": "error", "msg": str(e)})
            return
        elapsed = time.time() - t0
        track_cost(q, elapsed, usage)
        CACHE[ck] = {"answer": answer, "sources": sources}
        delta = push_turn(q, answer)
        yield sse({"type": "done", "cached": False,
                   "usage": {"pt": usage.get("input_tokens", 0), "ct": usage.get("output_tokens", 0)},
                   "elapsed": round(elapsed, 2), "delta": delta, "memory": MEM})

    return Response(gen(), mimetype="text/event-stream")


# ═══ /api/config：运行时可调参数（前端滑块 → 全局生效） ═══
@app.route("/api/config", methods=["GET", "POST"])
def config():
    global TOP_K
    if request.method == "POST":
        body = request.get_json() or {}
        if "top_k" in body:
            TOP_K = max(1, min(8, int(body["top_k"])))
    return jsonify({"top_k": TOP_K, "reject_th": REJECT_TH, "chunks": len(CHUNKS)})


# ═══ /api/sim：真实向量余弦拆解（2.3） ═══
@app.route("/api/sim", methods=["POST"])
def sim():
    q = (request.get_json() or {}).get("question", "").strip()
    if INDEX is None:
        return jsonify({"error": EMB_ERR}), 500
    t0 = time.time()
    qv = embed_query(q)
    scores = CHUNK_VECS @ qv  # 已归一化 → 内积即余弦
    order = np.argsort(-scores)[:3]
    rows = [{"id": CHUNKS[i]["id"], "src": CHUNKS[i]["src"], "ch": CHUNKS[i]["ch"],
             "score": round(float(scores[i]), 4)} for i in order]
    return jsonify({
        "dim": int(qv.shape[0]),
        "qvec_head": [round(float(x), 4) for x in qv[:8]],
        "rows": rows, "elapsed": round(time.time() - t0, 2),
        "all_scores": [round(float(s), 4) for s in scores],
    })


# ═══ /api/sql：LLM 生成 SQL → SQLite 真执行 → LLM 总结（2.11） ═══
def init_db() -> sqlite3.Connection:
    db = sqlite3.connect(":memory:", check_same_thread=False)
    db.execute("CREATE TABLE devices(id TEXT, vendor TEXT, model TEXT, site TEXT, status TEXT, temp REAL)")
    import random
    random.seed(42)
    vendors = [("华为", "AAU5613"), ("华为", "BBU5900"), ("中兴", "A9611"), ("诺基亚", "AEQB")]
    statuses = ["normal"] * 6 + ["warning"] * 2 + ["fault"]
    rows = []
    for i in range(50):
        v, m = random.choice(vendors)
        st = random.choice(statuses)
        rows.append((f"NE{i+1:03d}", v, m, f"站点-{random.randint(1,12):02d}", st,
                     round(random.uniform(35, 78), 1)))
    db.executemany("INSERT INTO devices VALUES(?,?,?,?,?,?)", rows)
    return db

DB = init_db()

@app.route("/api/sql", methods=["POST"])
def text2sql():
    q = (request.get_json() or {}).get("question", "").strip()
    t0 = time.time()
    schema = "devices(id 网元编号, vendor 厂商, model 型号, site 站点, status 状态[normal/warning/fault], temp 温度℃)，共 50 行"
    gen_prompt = (f"你是 SQL 专家。根据表结构生成一条 SQLite SELECT 查询（只输出 SQL，不要解释、不要 markdown 代码块）。\n"
                  f"表结构：{schema}\n需求：{q}\nSQL：")
    resp = LLM.invoke(gen_prompt)
    usage1 = resp.usage_metadata or {}
    sql = re.sub(r"```(sql)?|```", "", resp.content).strip().rstrip(";")
    # 只读白名单：只允许单条 SELECT
    if not re.match(r"(?is)^\s*select\b", sql) or ";" in sql:
        return jsonify({"error": f"SQL 被拦截（仅允许只读 SELECT）：{sql}"}), 400
    try:
        cur = DB.execute(sql)
        cols = [d[0] for d in cur.description]
        rows = cur.fetchmany(20)
    except Exception as e:
        return jsonify({"error": f"SQL 执行失败：{e}", "sql": sql}), 400
    sum_prompt = f"用一两句中文总结这个查询结果（面向运维主管）。\n需求：{q}\nSQL：{sql}\n结果：{cols} {rows[:10]}"
    resp2 = LLM.invoke(sum_prompt)
    usage2 = resp2.usage_metadata or {}
    elapsed = time.time() - t0
    merged = {"input_tokens": usage1.get("input_tokens", 0) + usage2.get("input_tokens", 0),
              "output_tokens": usage1.get("output_tokens", 0) + usage2.get("output_tokens", 0)}
    track_cost(q, elapsed, merged, kind="sql")
    delta = push_turn(q, f"生成 SQL 并返回 {len(rows)} 行：{resp2.content[:80]}")
    return jsonify({"sql": sql, "cols": cols, "rows": rows, "summary": resp2.content.strip(),
                    "usage": merged, "elapsed": round(elapsed, 2), "delta": delta, "memory": MEM})


# ═══ /api/eval：评测集真跑（2.10） ═══
EVAL_CASES = [
    {"q": "光模块收光功率多少算异常", "expect": "光模块故障"},
    {"q": "端口 Down 了怎么排查", "expect": "端口Down"},
    {"q": "AAU 发射功率超标怎么办", "expect": "AAU 发射功率异常"},
    {"q": "P0 告警的处理时限", "expect": "告警等级"},
    {"q": "AAU 多久巡检一次", "expect": "维护"},  # 巡检周期在"通用维护"分块（每季度全设备巡检）
    {"q": "设备维护有什么通用要求", "expect": "通用维护"},
    {"q": "今天天气怎么样", "expect": None},
]

@app.route("/api/eval", methods=["POST"])
def run_eval():
    if INDEX is None:
        return jsonify({"error": EMB_ERR}), 500
    t0 = time.time()
    rows = []
    for c in EVAL_CASES:
        hits, _ = retrieve(c["q"], 1)
        top = hits[0]
        rejected = top["score"] < REJECT_TH
        actual = "拒答" if rejected else top["chunk"]["ch"]
        passed = rejected if c["expect"] is None else (not rejected and c["expect"] in top["chunk"]["ch"])
        rows.append({"q": c["q"], "expect": c["expect"] or "拒答", "actual": actual,
                     "score": round(top["score"], 3), "pass": passed})
    hit = sum(r["pass"] for r in rows)
    return jsonify({"rows": rows, "hit": hit, "total": len(rows),
                    "threshold": REJECT_TH, "elapsed": round(time.time() - t0, 2)})


# ═══ 面板数据 ═══
@app.route("/api/chunks")
def chunks():
    return jsonify({"chunks": [{"id": c["id"], "src": c["src"], "ch": c["ch"], "text": c["text"][:80]}
                               for c in CHUNKS],
                    "dim": int(CHUNK_VECS.shape[1]) if CHUNK_VECS is not None else 0})

@app.route("/api/memory")
def get_memory():
    return jsonify(MEM)

@app.route("/api/memory/reset", methods=["POST"])
def reset_memory():
    global MEM
    MEM = {"all": [], "summaries": [], "turn": 0}
    return jsonify({"status": "ok"})

@app.route("/api/cost")
def get_cost():
    calls = COST["calls"]
    return jsonify({"calls": calls[-30:],
                    "total": {"n": len(calls),
                              "tk": sum(c["pt"] + c["ct"] for c in calls),
                              "cost": sum(c["cost"] for c in calls),
                              "cached": sum(1 for c in calls if c["cached"])}})


if __name__ == "__main__":
    build_index()
    print("Day2 完整真实版: http://localhost:8082")
    app.run(host="0.0.0.0", port=8082, debug=False, threaded=True)

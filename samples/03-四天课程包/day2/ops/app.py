"""Day2 Sample — Agent 运营台（8084）

真实客户项目的"水面之下"：chatbot 前台（day1 8081）负责对话，
运营台负责质检与统计 —— 对话记录 / RAG 命中率 / LLM-as-Judge 质量评测 / 安全护栏报表。

数据链路（全 JSON 文件，无数据库）：
    day1 通道④⑤ 每次调用 → 追加一行到 data/runs.jsonl（埋点，2.8）
    运营台读取 runs.jsonl → 聚合指标（2.10 / 3.5 / 3.6）
    Judge 评分 / 人工反馈 → 就地回写 runs.jsonl

启动：
    python3 app.py          # → http://localhost:8084
    python3 seed.py         # 可选：生成演示数据（冷启动）
"""
import json
import os
import re
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR.parent / ".env")   # 复用 day2/.env（DEEPSEEK_API_KEY）

import requests

app = Flask(__name__)

RUNS_FILE = BASE_DIR / "data" / "runs.jsonl"
DAY1_URL = os.getenv("DAY1_URL", "http://localhost:8081")
HIT_TH = 0.50            # 与 day1 通道④ 的拒答阈值一致
PRICE_IN, PRICE_OUT = 2.0, 8.0   # DeepSeek 元/百万 token（估算用）


# ── JSON 文件存储（教学版：全量读入 → 修改 → 原子重写，课堂量级足够）──


def load_runs() -> list[dict[str, Any]]:
    if not RUNS_FILE.exists():
        return []
    runs = []
    for line in RUNS_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                runs.append(json.loads(line))
            except json.JSONDecodeError:
                pass  # 手工编辑损坏的行直接跳过
    return runs


def save_runs(runs: list[dict[str, Any]]) -> None:
    RUNS_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = RUNS_FILE.with_suffix(".tmp")
    tmp.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in runs), encoding="utf-8")
    tmp.replace(RUNS_FILE)


def update_run(run_id: str, patch: dict[str, Any]) -> bool:
    runs = load_runs()
    for r in runs:
        if r.get("id") == run_id:
            r.update(patch)
            save_runs(runs)
            return True
    return False


def top1(r: dict[str, Any]) -> float:
    rt = r.get("retrieval") or []
    return rt[0].get("score", 0.0) if rt else 0.0


# ── 页面 ──


@app.route("/")
def index():
    return render_template("ops.html")


# ── 对话记录 ──


@app.route("/api/runs")
def api_runs():
    channel = request.args.get("channel", "")
    limit = int(request.args.get("limit", "200"))
    runs = load_runs()
    if channel:
        runs = [r for r in runs if r.get("channel") == channel]
    runs = runs[::-1][:limit]  # 最新在前
    return jsonify({"total": len(runs), "runs": runs})


@app.route("/api/runs/<run_id>")
def api_run_detail(run_id: str):
    for r in load_runs():
        if r.get("id") == run_id:
            return jsonify({"found": True, "run": r})
    return jsonify({"found": False}), 404


# ── 指标大盘（2.10 命中率 + 3.5 护栏 + 3.6 可观测 + 成本）──


@app.route("/api/stats")
def api_stats():
    runs = load_runs()
    by_channel: dict[str, int] = {}
    doc_heat: dict[str, int] = {}
    guard: dict[str, int] = {}
    gaps: list[dict[str, Any]] = []
    hit = miss = rejected = 0
    pt = ct = lat_sum = lat_n = 0
    judged: list[dict[str, Any]] = []
    fb_up = fb_down = 0

    for r in runs:
        by_channel[r.get("channel", "?")] = by_channel.get(r.get("channel", "?"), 0) + 1
        pt += r.get("pt", 0)
        ct += r.get("ct", 0)
        if r.get("latency_ms"):
            lat_sum += r["latency_ms"]
            lat_n += 1
        if r.get("guard_flag"):
            guard[r["guard_flag"]] = guard.get(r["guard_flag"], 0) + 1
            continue  # 被护栏拦截的不计入命中率
        # 命中判定：top1 >= 阈值 即认为知识库覆盖了该问题
        s = top1(r)
        if r.get("rejected"):
            rejected += 1
        elif r.get("retrieval"):
            if s >= HIT_TH:
                hit += 1
            else:
                miss += 1
        # 知识库缺口：拒答或低分（运营据此决定补哪些文档）
        if r.get("rejected") or (r.get("retrieval") and s < HIT_TH):
            gaps.append({"id": r.get("id"), "ts": r.get("ts"), "question": r.get("question"), "top1": s})
        # 文档引用热力：只统计过阈值（真正被答案使用）的分块来源
        for it in r.get("retrieval") or []:
            if it.get("score", 0) >= HIT_TH:
                doc_heat[it.get("src", "?")] = doc_heat.get(it.get("src", "?"), 0) + 1
        if r.get("judge"):
            judged.append(r["judge"])
        if r.get("feedback") == "up":
            fb_up += 1
        elif r.get("feedback") == "down":
            fb_down += 1

    total_eval = hit + miss + rejected
    dims = ["faithful", "relevant", "citation"]
    judge_avg = {d: round(sum(j.get(d, 0) for j in judged) / len(judged), 2) for d in dims} if judged else {}
    # Judge 分数分布（每维度 1-5 分各多少条）+ 低分待整改清单（均分 ≤ 2.5）
    judge_dist = {d: {str(s): 0 for s in range(1, 6)} for d in dims}
    for j in judged:
        for d in dims:
            s = j.get(d, 0)
            if 1 <= s <= 5:
                judge_dist[d][str(s)] += 1
    low_quality = [{"id": r.get("id"), "ts": r.get("ts"), "question": r.get("question"),
                    "avg": round(sum(r["judge"].get(d, 0) for d in dims) / 3, 1),
                    "comment": r["judge"].get("comment", "")}
                   for r in runs if r.get("judge") and sum(r["judge"].get(d, 0) for d in dims) / 3 <= 2.5]
    return jsonify({
        "total": len(runs), "by_channel": by_channel,
        "hit": hit, "miss": miss, "rejected": rejected,
        "hit_rate": round(hit / total_eval, 3) if total_eval else None,
        "reject_rate": round(rejected / total_eval, 3) if total_eval else None,
        "doc_heat": dict(sorted(doc_heat.items(), key=lambda kv: -kv[1])),
        "gaps": gaps[::-1][:20],
        "guard": guard,
        "judge_count": len(judged), "judge_avg": judge_avg,
        "judge_dist": judge_dist, "low_quality": low_quality[::-1][:10],
        "judge_pending": len([r for r in runs if r.get("answer") and not r.get("judge")]),
        "feedback": {"up": fb_up, "down": fb_down},
        "tokens": {"pt": pt, "ct": ct},
        "cost_cny": round(pt * PRICE_IN / 1e6 + ct * PRICE_OUT / 1e6, 4),
        "avg_latency_ms": int(lat_sum / lat_n) if lat_n else 0,
        "hit_th": HIT_TH,
    })


# ── 人工反馈（👍👎，真实项目质检标配）──


@app.route("/api/feedback", methods=["POST"])
def api_feedback():
    body = request.get_json() or {}
    ok = update_run(body.get("id", ""), {"feedback": body.get("feedback", "")})
    return jsonify({"ok": ok})


# ── LLM-as-Judge（2.10）：离线异步质检，不在对话链路上 ──

JUDGE_PROMPT = """你是大模型回答质检员。请根据【检索到的知识库片段】给【回答】打分（三个维度各 1-5 分，整数）：
- faithful 忠实度：回答内容是否都有知识库依据，无编造
- relevant 相关性：回答是否切中【问题】
- citation 引用规范：是否正确标注了分块编号（如 C01）

只输出 JSON：{"faithful": n, "relevant": n, "citation": n, "comment": "一句话点评"}

【问题】{q}
【检索到的知识库片段】{ctx}
【回答】{a}"""


def judge_one(r: dict[str, Any]) -> dict[str, Any] | None:
    api_key = os.getenv("DEEPSEEK_API_KEY", "")
    base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1").rstrip("/")
    ctx = "\n".join(f"{it['cid']} {it['src']}·{it['ch']}（{it['score']}）" for it in r.get("retrieval") or [])
    prompt = JUDGE_PROMPT.replace("{q}", r.get("question", "")).replace("{ctx}", ctx or "（无）").replace("{a}", r.get("answer", ""))
    resp = requests.post(
        f"{base_url}/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={"model": os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
              "messages": [{"role": "user", "content": prompt}], "temperature": 0},
        timeout=60,
    )
    resp.raise_for_status()
    text = resp.json()["choices"][0]["message"]["content"]
    m = re.search(r"\{.*\}", text, re.S)
    return json.loads(m.group()) if m else None


@app.route("/api/judge", methods=["POST"])
def api_judge():
    """批量评测：挑出「有回答且未评过」的记录，逐条 LLM 打分后回写"""
    if not os.getenv("DEEPSEEK_API_KEY"):
        return jsonify({"error": "未配置 DEEPSEEK_API_KEY"}), 500
    limit = int((request.get_json() or {}).get("limit", 5))
    runs = load_runs()
    todo = [r for r in runs if r.get("answer") and not r.get("judge")][-limit:]
    done, t0 = [], time.time()
    for r in todo:
        try:
            j = judge_one(r)
            if j:
                r["judge"] = j
                done.append({"id": r["id"], "question": r["question"][:30], "judge": j})
        except Exception as e:
            done.append({"id": r.get("id"), "error": str(e)})
    save_runs(runs)
    return jsonify({"judged": len([d for d in done if "judge" in d]), "detail": done,
                    "remaining": len([r for r in runs if r.get("answer") and not r.get("judge")]),
                    "elapsed": round(time.time() - t0, 1)})


# ── Golden Set 回归（复用 8082 的 7 题）：真打 day1 /agent/rag ──

GOLDEN_CASES = [
    {"q": "光模块收光功率多少算异常", "expect": "光模块故障"},
    {"q": "端口 Down 了怎么排查", "expect": "端口Down"},
    {"q": "AAU 发射功率超标怎么办", "expect": "AAU 发射功率异常"},
    {"q": "P0 告警的处理时限", "expect": "告警等级"},
    {"q": "AAU 多久巡检一次", "expect": "维护"},
    {"q": "设备维护有什么通用要求", "expect": "通用维护"},
    {"q": "今天天气怎么样", "expect": None},   # 期望拒答
]


@app.route("/api/golden/cases")
def api_golden_cases():
    """题库预览：让学员先看到固定题集长什么样，再理解“回归”在回归什么"""
    return jsonify({"cases": [{"q": c["q"], "expect": c["expect"] or "拒答"} for c in GOLDEN_CASES],
                    "hit_th": HIT_TH})


@app.route("/api/golden", methods=["POST"])
def api_golden():
    """逐题调 day1 通道④（每题独立 object_id，互不带记忆），判命中/拒答；产生的 runs 自动进埋点"""
    rows, t0 = [], time.time()
    session = f"GOLDEN-{int(t0)}"
    for i, c in enumerate(GOLDEN_CASES):
        row: dict[str, Any] = {"q": c["q"], "expect": c["expect"] or "拒答"}
        try:
            resp = requests.post(f"{DAY1_URL}/agent/rag",
                                 json={"question": c["q"], "object_id": f"{session}-{i}"},
                                 stream=True, timeout=120)
            tools, content = [], ""
            for raw in resp.iter_lines():
                line = raw.decode("utf-8") if isinstance(raw, bytes) else raw
                if not line.startswith("data:") or line[5:].strip() == "[DONE]":
                    continue
                d = json.loads(line[5:].strip())
                if d.get("tool"):
                    tools.append(d.get("content", ""))
                elif d.get("content"):
                    content += d["content"]
            m = re.search(r"cos ([\d.]+)", tools[0]) if tools else None
            score = float(m.group(1)) if m else 0.0
            if c["expect"] is None:
                row.update(passed="不作回答" in content, top1=score, got="拒答" if "不作回答" in content else content[:40])
            else:
                row.update(passed=bool(tools) and c["expect"] in tools[0] and score >= HIT_TH,
                           top1=score, got=tools[0][:60] if tools else "无检索")
        except Exception as e:
            row.update(passed=False, top1=0, got=f"调用失败: {e}")
        rows.append(row)
    return jsonify({"rows": rows, "passed": sum(1 for r in rows if r["passed"]), "total": len(rows),
                    "elapsed": round(time.time() - t0, 1)})


@app.route("/health")
def health():
    return jsonify({"status": "ok", "runs": len(load_runs()), "runs_file": str(RUNS_FILE),
                    "day1": DAY1_URL, "judge_configured": bool(os.getenv("DEEPSEEK_API_KEY"))})


if __name__ == "__main__":
    print(f"""
╔══════════════════════════════════════════════════╗
║   Day2 Sample — Agent 运营台                     ║
║   http://localhost:8084                          ║
║                                                  ║
║   数据源: {str(RUNS_FILE)[-38:]:<38} ║
║   前台:   day1 平台 {DAY1_URL:<28} ║
║   冷启动: python3 seed.py 生成演示数据           ║
╚══════════════════════════════════════════════════╝
""")
    app.run(host="0.0.0.0", port=8084, debug=False, threaded=True)

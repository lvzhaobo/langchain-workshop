"""RAG 评测脚本——检索质量 + 回答质量

运行：python evaluate_rag.py
依赖：pip install langchain langchain-openai langchain-community faiss-cpu
"""
import os
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))  # 自动读取课程根目录 .env

import json
import time
from pathlib import Path

from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_community.vectorstores import FAISS

API_KEY = os.getenv("AGENT_API_KEY", "REPLACE_ME_NO_KEY")
API_BASE = os.getenv("AGENT_API_BASE", "https://api.deepseek.com/v1")
MODEL = os.getenv("AGENT_MODEL", "deepseek-chat")

DATA_DIR = Path(__file__).parent / "data"


# ═══ 数据加载 ═══
def load_eval_cases():
    with open(DATA_DIR / "eval_cases.json", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("cases", data)


def load_vectorstore():
    embeddings = OpenAIEmbeddings(
        model="text-embedding-v3",
        api_key=os.getenv("DASHSCOPE_API_KEY"),
        base_url=os.getenv("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
        check_embedding_ctx_length=False,
        chunk_size=10,
    )
    return FAISS.load_local(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "faiss_index"),
        embeddings,
        allow_dangerous_deserialization=True,
    )


# ═══ 第一层：检索质量评测 ═══
def evaluate_retrieval(vectorstore, cases, k=3):
    """Recall@K / MRR / Precision@K"""
    total_recall = 0
    total_mrr = 0
    total_precision = 0
    detail_results = []
    valid_count = 0

    for case in cases:
        relevant = set(case.get("relevant_docs", []))
        if not relevant:
            detail_results.append({**case, "skip": True, "skip_reason": "无预期文档"})
            continue

        docs = vectorstore.similarity_search_with_relevance_scores(
            case["query"], k=k
        )

        retrieved_filenames = set()
        for doc, score in docs:
            source = doc.metadata.get("source", "")
            filename = source.split("/")[-1] if "/" in source else source
            retrieved_filenames.add(filename)

        hits = relevant & retrieved_filenames
        recall = len(hits) / len(relevant)
        precision = len(hits) / len(docs) if docs else 0

        mrr = 0
        for rank, (doc, _) in enumerate(docs, 1):
            source = doc.metadata.get("source", "").split("/")[-1]
            if source in relevant:
                mrr = 1.0 / rank
                break

        total_recall += recall
        total_mrr += mrr
        total_precision += precision
        valid_count += 1

        detail_results.append({
            **case,
            "skip": False,
            "recall": round(recall, 3),
            "mrr": round(mrr, 3),
            "precision": round(precision, 3),
            "retrieved": sorted(retrieved_filenames),
            "hits": sorted(hits),
            "top_scores": [round(score, 3) for _, score in docs],
        })

    n = max(valid_count, 1)
    metrics = {
        "Recall@" + str(k): round(total_recall / n, 3),
        "MRR": round(total_mrr / n, 3),
        "Precision@" + str(k): round(total_precision / n, 3),
        "评测用例数": len(cases),
        "有效用例数": valid_count,
    }
    return metrics, detail_results


# ═══ 第二层：LLM Judge 回答质量评测 ═══
def evaluate_answer_quality(query, answer, expected_summary):
    """用 LLM 当裁判评分"""
    judge_llm = ChatOpenAI(
        model=MODEL,
        temperature=0,
        api_key=API_KEY,
        base_url=API_BASE,
    )

    judge_prompt = f"""你是一个 RAG 回答质量评估专家。对以下回答评分。

用户问题：{query}

助手回答：
{answer}

预期要点：{expected_summary}

四维度评分（1-5）：
1. 完整性 — 是否覆盖所有方面
2. 准确性 — 每条陈述是否正确
3. 相关性 — 是否紧扣问题
4. 可溯源性 — 是否引用文档

严格只输出 JSON：{{"完整性":X,"准确性":X,"相关性":X,"可溯源性":X,"总分":X,"评语":"一句话"}}"""

    try:
        response = judge_llm.invoke(judge_prompt)
        content = response.content

        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]
        result = json.loads(content.strip())
        return result
    except (json.JSONDecodeError, IndexError, Exception) as e:
        return {"error": str(e), "raw": content if "content" in dir() else ""}


# ═══ 用 2.5 的 RAG Agent 生成回答 ═══
# 注：2.5 目录的 agent_rag.py 不在本目录，需要手动配置路径
def rag_answer(query):
    """调用 RAG Agent 得到回答。请将 14-RAG-Agent/ 目录添加到 Python path"""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent / "14-RAG-Agent"))
    from agent_rag import create_rag_agent
    agent = create_rag_agent()
    result = agent.invoke({"input": query})
    return result["output"]


# ═══ 主程序 ═══
if __name__ == "__main__":
    print("RAG 评测系统")
    print("=" * 60)

    # ── 加载数据和向量库 ──
    cases = load_eval_cases()
    print(f"加载 {len(cases)} 条评测用例")

    try:
        vectorstore = load_vectorstore()
        print("向量库加载成功")
    except Exception as e:
        print(f"向量库加载失败：{e}")
        print("请确保已完成实验 2.1，FAISS 索引路径正确")
        exit(1)

    # ═══ 第一层：检索质量 ═══
    print(f"\n{'='*60}")
    print("第一层：检索质量评测")
    print(f"{'='*60}")

    for k_val in [1, 3, 5]:
        metrics, details = evaluate_retrieval(vectorstore, cases, k=k_val)
        print(f"\nTop-{k_val}:")
        for metric, value in metrics.items():
            if metric.startswith("Recall") or metric in ("MRR", "Precision"):
                print(f"  {metric}: {value}")

    # 逐条详情
    metrics_k3, details_k3 = evaluate_retrieval(vectorstore, cases, k=3)

    print(f"\n{'-'*60}")
    print("逐条详情：")
    for d in details_k3:
        if d.get("skip"):
            print(f"  ⊘ {d['id']} [{d['category']}]: {d['query'][:40]}... (跳过)")
            continue
        status = "✅" if d["recall"] > 0 else ("⚠️" if d["recall"] > 0 else "❌")
        print(f"  {status} {d['id']} [{d['category']}]")
        print(f"     Q: {d['query'][:50]}...")
        print(f"     Recall={d['recall']}, MRR={d['mrr']}, Precision={d['precision']}")
        print(f"     检索到: {d['retrieved']}")
        print(f"     命中: {d['hits']}")
        print(f"     相似度: {d['top_scores']}")

    # ── 按类别汇总 ──
    print(f"\n{'-'*60}")
    print("按类别汇总检索质量：")
    categories = {}
    for d in details_k3:
        cat = d["category"]
        if cat not in categories:
            categories[cat] = {"recall": [], "mrr": [], "precision": [], "total": 0}
        if not d.get("skip"):
            categories[cat]["recall"].append(d["recall"])
            categories[cat]["mrr"].append(d["mrr"])
            categories[cat]["precision"].append(d["precision"])
            categories[cat]["total"] += 1

    for cat, vals in categories.items():
        avg_recall = sum(vals["recall"]) / len(vals["recall"]) if vals["recall"] else 0
        avg_mrr = sum(vals["mrr"]) / len(vals["mrr"]) if vals["mrr"] else 0
        avg_prec = sum(vals["precision"]) / len(vals["precision"]) if vals["precision"] else 0
        print(f"  {cat:<10} ({vals['total']}条): "
              f"Recall={avg_recall:.2f}, MRR={avg_mrr:.2f}, Precision={avg_prec:.2f}")

    # ═══ 第二层：回答质量（LLM Judge）═══
    print(f"\n{'='*60}")
    print("第二层：LLM Judge 回答质量评测")
    print(f"{'='*60}")
    print("（此部分需先运行 RAG Agent 生成回答，耗时较长）")
    print("\n如果要跑回答质量评测，输入 y：")
    choice = input(">>> ").strip().lower()
    if choice == "y":
        run_quality_eval()


def run_quality_eval():
    """LLM Judge 回答质量评测"""
    cases = load_eval_cases()
    answerable = [c for c in cases if c["category"] != "不能回答"][:5]

    quality_results = []
    for case in answerable:
        print(f"\n评测 {case['id']}: {case['query'][:40]}...")

        # 生成回答 — RAG Agent 在 2.5 目录
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent / "14-RAG-Agent"))
        try:
            from agent_rag import create_rag_agent
            agent = create_rag_agent()
            result = agent.invoke({"input": case["query"]})
            answer = result["output"]
        except Exception as e:
            answer = f"无法生成回答：{e}"

        print(f"  回答: {answer[:100]}...")

        # LLM 评分
        score = evaluate_answer_quality(
            case["query"], answer, case["expected_answer_summary"]
        )
        score["id"] = case["id"]
        score["query"] = case["query"][:50]
        quality_results.append(score)
        print(f"  评分: 完整性={score.get('完整性','?')}, 准确性={score.get('准确性','?')}")

    # 汇总
    if quality_results:
        def avg(key):
            vals = [r.get(key, 0) for r in quality_results if isinstance(r.get(key), (int, float))]
            return sum(vals) / len(vals) if vals else 0

        print(f"\n回答质量汇总：")
        for dim in ["完整性", "准确性", "相关性", "可溯源性"]:
            print(f"  {dim}: {avg(dim):.2f}/5")

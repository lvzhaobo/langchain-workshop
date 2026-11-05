"""
实验二：FAISS 向量检索 + RAG 知识问答

核心概念：
  - Embedding：把文本变成向量，语义相近 → 向量距离近
  - FAISS：Facebook 开源的高效向量检索库，纯本地、无需服务端
  - RAG 管道：检索相关文档 → 拼到 Prompt → LLM 生成答案

运行方式：
  python 02-rag-faiss/rag_faiss.py            # 正常模式（需要百炼 API）
  python 02-rag-faiss/rag_faiss.py --offline  # 离线模式（纯本地运行）

前置条件：
  export DASHSCOPE_API_KEY=你的百炼Key   # 仅正常模式需要
  pip install langchain langchain-openai langchain-community faiss-cpu  # 离线模式只需 faiss-cpu
"""

import json
import os
import sys
from pathlib import Path

# 离线模式：不依赖任何外部 API
OFFLINE = "--offline" in sys.argv

# 确保能从子目录导入 _offline_utils
sys.path.insert(0, str(Path(__file__).parent.parent))

# FAISS 在两种模式下都需要（离线模式用 MockEmbeddings + FAISS）
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document

if not OFFLINE:
    from openai import OpenAI

DATA_DIR = Path(__file__).parent.parent
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "")
BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
MODEL = "qwen-plus"
EMBEDDING_MODEL = "text-embedding-v1"


# ---------------------------------------------------------------------------
# Embedding 模型（线上线下不同实现）
# ---------------------------------------------------------------------------

if OFFLINE:
    from _offline_utils import MockEmbeddings

    def _make_embeddings():
        return MockEmbeddings()

    def _make_llm_client():
        return None  # 用 _mock_chat 代替
else:
    from langchain_core.embeddings import Embeddings

    class DashScopeEmbeddings(Embeddings):
        """DashScope Embedding 封装 — 绕过 langchain_openai 的 input 字段格式问题"""

        def __init__(self, client, model):
            self.client = client
            self.model = model

        def embed_documents(self, texts: list[str]) -> list[list[float]]:
            result = self.client.embeddings.create(model=self.model, input=texts)
            return [d.embedding for d in result.data]

        def embed_query(self, text: str) -> list[float]:
            return self.embed_documents([text])[0]

    def _make_embeddings():
        client = OpenAI(base_url=BASE_URL, api_key=DASHSCOPE_API_KEY)
        return DashScopeEmbeddings(client, EMBEDDING_MODEL)

    def _make_llm_client():
        return OpenAI(base_url=BASE_URL, api_key=DASHSCOPE_API_KEY)


# ---------------------------------------------------------------------------
# 模拟 LLM 回答（离线模式）
# ---------------------------------------------------------------------------

def _mock_chat(prompt: str) -> str:
    """离线模式：根据 prompt 内容返回模拟回答"""
    prompt_lower = prompt.lower()

    if "sf6" in prompt_lower and "泄漏" in prompt_lower:
        return ("根据 GIS设备SF6气体管理要求（doc_005），SF6气体年泄漏率不应超过0.5%。"
                "检测方法：使用SF6检漏仪沿密封面、焊缝、阀门等部位逐点检测。"
                "发现泄漏后应立即标记泄漏点，安排停电处理，并补充SF6气体至额定压力。")

    if "变压器油温" in prompt and ("85" in prompt or "处理" in prompt):
        return ("根据变压器油温异常诊断规程（doc_001），油温超过85°C应发出告警，"
                "超过95°C应考虑减负荷或停机。处理措施：1.检查冷却系统运行状态；"
                "2.检测油中溶解气体（DGA）；3.检查是否过负荷运行。")

    if "开关柜" in prompt and "局部放电" in prompt:
        return ("根据开关柜局部放电检测与评估（doc_007），10kV开关柜局部放电量"
                "应小于10pC（暂行标准）。检测方法包括暂态地电压法（TEV）和超声波法，"
                "建议每季度进行一次普测。")

    if "防雷" in prompt:
        return ("根据架空线路防雷保护措施（doc_012），主要措施包括：1.架设避雷线；"
                "2.降低杆塔接地电阻；3.安装线路避雷器；4.加强绝缘配合。")

    if "风力发电" in prompt or "叶片" in prompt:
        return "资料中未提供相关信息。"

    # 默认：从 prompt 中提取关键词作为模拟参考
    return f"[离线模拟] 基于知识库检索结果，针对该问题的回答。去掉 --offline 参数可使用真实 API。"


# ---------------------------------------------------------------------------
# 数据加载
# ---------------------------------------------------------------------------

def load_knowledge_base():
    with open(DATA_DIR / "knowledge_base.json", "r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# 向量索引构建
# ---------------------------------------------------------------------------

def build_faiss_index(embeddings):
    print("   📚 加载知识库...")
    kb = load_knowledge_base()
    print(f"      共 {len(kb)} 篇文档")

    documents = []
    for doc in kb:
        documents.append(Document(
            page_content=doc["content"],
            metadata={"title": doc["title"], "category": doc["category"], "doc_id": doc["id"]}
        ))

    print(f"   🧮 Embedding 模型：{'MockEmbeddings（本地哈希向量）' if OFFLINE else f'DashScope {EMBEDDING_MODEL}'}")
    print("   🔨 构建 FAISS 向量索引...")
    vector_store = FAISS.from_documents(documents=documents, embedding=embeddings)

    print(f"   ✅ 索引构建完成，共 {vector_store.index.ntotal} 条向量")
    if OFFLINE:
        print(f"   ⚡ 离线模式提示：向量来自 MD5 哈希，语义相似度有限，但索引结构和检索流程完全真实")
    return vector_store


# ---------------------------------------------------------------------------
# 检索
# ---------------------------------------------------------------------------

def similarity_search(vector_store, query: str, k: int = 3):
    return vector_store.similarity_search_with_relevance_scores(query, k=k)


# ---------------------------------------------------------------------------
# RAG 回答
# ---------------------------------------------------------------------------

def _chat(client, prompt: str) -> str:
    if OFFLINE:
        return _mock_chat(prompt)
    resp = client.chat.completions.create(
        model=MODEL, messages=[{"role": "user", "content": prompt}], temperature=0)
    return resp.choices[0].message.content


def rag_answer(vector_store, question: str, client) -> dict:
    docs_with_scores = similarity_search(vector_store, question, k=3)

    context_parts = []
    sources = []
    for doc, score in docs_with_scores:
        context_parts.append(f"【文档标题：{doc.metadata['title']}】\n{doc.page_content}")
        sources.append({"title": doc.metadata['title'], "score": round(score, 4)})

    context = "\n\n---\n\n".join(context_parts)

    prompt = f"""你是一个电力设备运维专家。请根据以下技术资料回答问题。
如果资料中找不到相关信息，请明确说"资料中未提供相关信息"，不要编造。

技术资料：
{context}

问题：{question}

请基于以上资料回答："""

    answer = _chat(client, prompt)
    return {"answer": answer, "sources": sources}


# ---------------------------------------------------------------------------
# 对比实验
# ---------------------------------------------------------------------------

def compare_rag_vs_no_rag(vector_store, client):
    questions = [
        "变压器油温超过85度应该怎么处理？",
        "10kV开关柜局部放电的检测标准是什么？",
        "架空线路防雷有哪些措施？",
        "风力发电机的叶片维护周期是多少？",
    ]

    for q in questions:
        print(f"\n{'─'*60}")
        print(f"❓ {q}")

        answer_no_rag = _chat(client, q)
        print(f"\n📝 无 RAG（LLM 直接回答）：")
        print(f"   {answer_no_rag[:250]}")

        result = rag_answer(vector_store, q, client)
        print(f"\n📚 有 RAG（检索后回答）：")
        print(f"   答案：{result['answer'][:250]}")
        print(f"   来源：")
        for s in result['sources']:
            print(f"     - [{s['score']:.4f}] {s['title']}")


# ---------------------------------------------------------------------------
# 检索效果演示
# ---------------------------------------------------------------------------

def demo_semantic_search(vector_store):
    print("\n🔬 语义检索效果演示：")
    test_queries = [
        ("精确匹配", "变压器油温过高怎么处理？"),
        ("口语化表达", "电缆要做哪些测试才能投运？"),
        ("专业术语变体", "主变绝缘老化试验标准是啥？"),
        ("无关查询", "今天午饭吃什么？"),
    ]
    for label, query in test_queries:
        print(f"\n   [{label}] 查询：{query}")
        results = similarity_search(vector_store, query, k=2)
        for doc, score in results:
            print(f"      [{score:.4f}] {doc.metadata['title']}")
    if OFFLINE:
        print(f"\n   ⚡ 离线提示：向量基于文本哈希，相同/相似的文本距离更近")


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------

def main():
    if OFFLINE:
        print("=" * 60)
        print("🧪 实验二：FAISS 向量检索 + RAG 知识问答 [离线模式]")
        print("=" * 60)
        print("\n  ⚡ 离线模式：Embedding 用 MD5 哈希，LLM 回答用预设模拟")
        print("  ⚡ FAISS 索引构建和检索 100% 真实执行")
        print("  ⚡ 去掉 --offline 参数即可使用真实百炼 API\n")
    else:
        print("=" * 60)
        print("🧪 实验二：FAISS 向量检索 + RAG 知识问答")
        print("=" * 60)

        if not DASHSCOPE_API_KEY:
            print("\n⚠️  请先设置环境变量 DASHSCOPE_API_KEY")
            print("   export DASHSCOPE_API_KEY=sk-...")
            print("   或者用 --offline 参数在离线模式下运行")
            sys.exit(1)

    # 1. 构建索引
    print("\n📦 [1/4] 构建 FAISS 向量索引...")
    embeddings = _make_embeddings()
    vector_store = build_faiss_index(embeddings)

    # 2. 语义检索演示
    print("\n🔍 [2/4] 语义检索效果演示...")
    demo_semantic_search(vector_store)

    # 3. RAG 问答测试
    print("\n🤖 [3/4] RAG 问答测试...")
    client = _make_llm_client()
    question = "SF6气体泄漏的标准和处理方法是什么？"
    print(f"\n   ❓ {question}")
    result = rag_answer(vector_store, question, client)
    print(f"   📚 答案：{result['answer'][:300]}")
    print(f"   📎 来源：{[s['title'] for s in result['sources']]}")

    # 4. 对比实验
    print("\n📊 [4/4] 对比实验：有 RAG vs 无 RAG...")
    compare_rag_vs_no_rag(vector_store, client)

    print("\n" + "=" * 60)
    print("🎉 实验二完成！")
    print("=" * 60)


if __name__ == "__main__":
    main()

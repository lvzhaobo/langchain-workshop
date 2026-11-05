"""
Lab 7.2 — RAG 骨架代码

学员需要完成的内容：
  1. build_vector_index() — 文档分块 → Embedding → 构建 ChromaDB 索引
  2. similarity_search() — 检索最相关的文档
  3. rag_answer() — 检索 → 拼 Prompt → LLM 生成答案
  4. compare_rag_vs_no_rag() — 对比有 RAG 和无 RAG 的答案

运行方式：
  python rag_skeleton.py
"""

import json
import os
from pathlib import Path

from langchain_openai import ChatOpenAI, OpenAIEmbeddings

# ---------------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------------
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "你的百炼 API Key")
DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
MODEL = "qwen-plus"

DATA_DIR = Path(__file__).parent


# ---------------------------------------------------------------------------
# 数据加载
# ---------------------------------------------------------------------------

def load_knowledge_base():
    """加载知识库文档"""
    with open(DATA_DIR / "knowledge_base.json", "r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# 向量索引构建
# ---------------------------------------------------------------------------

def build_vector_index():
    """构建 ChromaDB 向量索引

    步骤：
    1. 加载知识库文档
    2. 将每篇文档按段落分块（每篇文档作为一个块）
    3. 用百炼 Embedding 模型将文本转为向量
    4. 用 ChromaDB 存储向量和原始文本
    5. 返回可检索的 vector_store 对象
    """
    # ===================================================================
    # TODO: 构建向量索引
    # 提示：
    #   - 使用 langchain_community.embeddings import DashScopeEmbeddings
    #     或者使用 OpenAIEmbeddings(api_key=..., base_url=...)
    #     （百炼的 text-embedding-v1 是兼容的）
    #   - 使用 langchain_community.vectorstores import Chroma
    #   - 或者使用 from langchain_chroma import Chroma
    #   - 每篇文档包装为 langchain_core.documents.Document
    #     Document(page_content=doc["content"], metadata={"title": doc["title"], ...})
    # ===================================================================
    pass


# ---------------------------------------------------------------------------
# 检索
# ---------------------------------------------------------------------------

def similarity_search(vector_store, query: str, k: int = 3):
    """检索与查询最相关的 k 篇文档"""
    # ===================================================================
    # TODO: 执行相似度检索
    # 提示：调用 vector_store.similarity_search(query, k=k)
    # ===================================================================
    pass


# ---------------------------------------------------------------------------
# RAG 回答
# ---------------------------------------------------------------------------

def rag_answer(vector_store, question: str) -> str:
    """RAG 流程：检索 → 拼 Prompt → LLM 生成

    步骤：
    1. 检索与问题相关的文档
    2. 将检索结果格式化为上下文文本
    3. 构造 Prompt："根据以下资料回答问题..."
    4. 调用 LLM 生成答案
    5. 返回答案（和检索到的来源标题）
    """
    # ===================================================================
    # TODO: 完成 RAG 回答流程
    # ===================================================================
    pass


# ---------------------------------------------------------------------------
# 对比实验
# ---------------------------------------------------------------------------

def compare_rag_vs_no_rag(vector_store):
    """对比：有 RAG vs 无 RAG 的答案质量"""
    # ===================================================================
    # TODO: 完成对比实验
    # 设计 2-3 个需要专业知识的问题
    # 对每个问题：
    #   1. 用 LLM.invoke 直接问（无 RAG）
    #   2. 用 rag_answer 问（有 RAG）
    #   3. 打印对比
    # ===================================================================
    pass


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 50)
    print("Lab 7.2 — 向量检索 + RAG 骨架")
    print("=" * 50)

    if DASHSCOPE_API_KEY == "你的百炼 API Key":
        print("\n⚠️  请先设置环境变量 DASHSCOPE_API_KEY")
        exit(1)

    # TODO: 完成上述函数后，取消以下注释来测试
    # print("\n📚 加载知识库...")
    # kb = load_knowledge_base()
    # print(f"   共 {len(kb)} 篇文档")

    # print("\n🔨 构建向量索引...")
    # vector_store = build_vector_index()

    # print("\n🔍 检索测试...")
    # results = similarity_search(vector_store, "变压器油温过高怎么处理？")
    # for i, doc in enumerate(results):
    #     print(f"   [{i+1}] {doc.metadata['title']}")
    #     print(f"       {doc.page_content[:100]}...")

    # print("\n🤖 RAG 问答测试...")
    # answer = rag_answer(vector_store, "SF6气体泄漏的标准和处理方法是什么？")
    # print(f"   回答：{answer}")

    # print("\n📊 对比实验...")
    # compare_rag_vs_no_rag(vector_store)

    print("\n👆 请完成代码中的 TODO 部分，然后取消 main 中的注释来运行")

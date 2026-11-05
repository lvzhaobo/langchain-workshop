"""2.1 FAISS 向量库 — 构建持久化索引

读取 ./data/*.md → 切割 → DashScope text-embedding-v3 向量化 → 存 ./faiss_index/
下游 2.5 / 3.1 / 3.2 / 3.3 等 lab 通过 FAISS.load_local 复用本索引。

运行：python build_index.py
依赖：pip install langchain-openai langchain-community faiss-cpu langchain-text-splitters
"""
import os
from pathlib import Path
from dotenv import dotenv_values

ENV_PATH = os.path.join(os.path.dirname(__file__), "..", "..", ".env")  # 课程根目录 .env
_env = dotenv_values(ENV_PATH)  # 直接读取 .env，不写入 os.environ

from langchain_openai import OpenAIEmbeddings
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_community.vectorstores import FAISS
from langchain_text_splitters import RecursiveCharacterTextSplitter

DATA_DIR = Path(__file__).parent / "data"
INDEX_DIR = Path(__file__).parent / "faiss_index"


def build():
    # 1. 加载排障文档
    loader = DirectoryLoader(str(DATA_DIR), glob="**/*.md", loader_cls=TextLoader)
    documents = loader.load()
    print(f"📄 加载 {len(documents)} 篇文档")

    # 2. 切割
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=50,
        separators=["\n## ", "\n### ", "\n", "。"],
    )
    chunks = splitter.split_documents(documents)
    print(f"✂️  切割为 {len(chunks)} 个文本段")

    # 3. DashScope 向量化（国内端点，兼容模式需关闭本地 token 切分）
    embeddings = OpenAIEmbeddings(
        model="text-embedding-v3",
        api_key=_env.get("DASHSCOPE_API_KEY"),
        base_url=_env.get("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
        check_embedding_ctx_length=False,
        chunk_size=10,  # DashScope v3 单批上限 10 条
    )
    try:
        vectorstore = FAISS.from_documents(chunks, embeddings)
    except Exception as e:
        print("🔢 向量化失败：请检查 .env 中 DASHSCOPE_API_KEY 是否有效")
        print(f"   错误：{str(e)[:160]}")
        raise SystemExit(1)

    # 4. 持久化
    vectorstore.save_local(str(INDEX_DIR))
    print(f"✅ FAISS 索引已保存到 {INDEX_DIR}")

    # 5. 自检：跑一条检索
    hits = vectorstore.similarity_search("光模块收光功率异常怎么排查", k=2)
    print(f"🔍 自检检索命中 {len(hits)} 段，Top1 预览：{hits[0].page_content[:60]}...")


if __name__ == "__main__":
    build()

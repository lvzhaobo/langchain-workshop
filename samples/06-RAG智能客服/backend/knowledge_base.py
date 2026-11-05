"""
知识库管理模块
负责文档加载、切分、向量化和存储
"""
from langchain.text_splitter import CharacterTextSplitter
from langchain_community.document_loaders import TextLoader
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma
import os

class KnowledgeBase:
    def __init__(self, data_path: str, persist_directory: str = "./chroma_db"):
        """
        初始化知识库
        
        Args:
            data_path: 知识文档路径
            persist_directory: 向量数据库持久化路径
        """
        self.data_path = data_path
        self.persist_directory = persist_directory
        self.embeddings = OpenAIEmbeddings()
        
    def load_and_split(self):
        """加载并切分文档"""
        # 加载文档
        loader = TextLoader(self.data_path, encoding='utf-8')
        documents = loader.load()
        
        # 切分文档
        text_splitter = CharacterTextSplitter(
            chunk_size=200,  # 每块大小
            chunk_overlap=50,  # 重叠部分
            separator="\n\n"  # 分隔符
        )
        chunks = text_splitter.split_documents(documents)
        print(f"✅ 文档已切分为 {len(chunks)} 个块")
        return chunks
    
    def create_vectorstore(self):
        """创建向量数据库"""
        chunks = self.load_and_split()
        
        # 创建并持久化向量数据库
        vectorstore = Chroma.from_documents(
            documents=chunks,
            embedding=self.embeddings,
            persist_directory=self.persist_directory
        )
        print(f"✅ 向量数据库已创建，保存在 {self.persist_directory}")
        return vectorstore
    
    def load_vectorstore(self):
        """加载已有向量数据库"""
        if not os.path.exists(self.persist_directory):
            print("⚠️  向量数据库不存在，正在创建...")
            return self.create_vectorstore()
        
        vectorstore = Chroma(
            persist_directory=self.persist_directory,
            embedding_function=self.embeddings
        )
        print("✅ 向量数据库已加载")
        return vectorstore

# 测试代码
if __name__ == "__main__":
    import sys
    sys.path.append(os.path.dirname(__file__))
    
    print("=" * 50)
    print("知识库测试")
    print("=" * 50)
    
    kb = KnowledgeBase("data/product_faq.txt")
    vectorstore = kb.create_vectorstore()
    
    # 测试检索
    test_queries = ["产品价格是多少", "防水功能", "如何连接手机"]
    for query in test_queries:
        print(f"\n查询: {query}")
        results = vectorstore.similarity_search(query, k=2)
        for i, doc in enumerate(results):
            print(f"  结果 {i+1}: {doc.page_content[:100]}...")
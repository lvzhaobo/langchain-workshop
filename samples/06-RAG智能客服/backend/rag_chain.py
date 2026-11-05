"""
RAG Chain 核心模块
负责构建检索增强生成链
"""
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain.schema.runnable import RunnablePassthrough
from langchain.schema.output_parser import StrOutputParser
from knowledge_base import KnowledgeBase

class RAGChain:
    def __init__(self, data_path: str):
        """初始化RAG Chain"""
        print("=" * 50)
        print("初始化 RAG Chain")
        print("=" * 50)
        
        # 加载知识库
        self.kb = KnowledgeBase(data_path)
        self.vectorstore = self.kb.load_vectorstore()
        self.retriever = self.vectorstore.as_retriever(
            search_kwargs={"k": 3}  # 检索top 3相关文档
        )
        print("✅ 知识库加载完成")
        
        # 初始化LLM
        self.llm = ChatOpenAI(
            model_name="gpt-3.5-turbo",
            temperature=0.7
        )
        print("✅ LLM 初始化完成")
        
        # 创建prompt模板
        self.prompt = PromptTemplate.from_template(
            """你是一个专业的智能客服助手。请根据以下知识库内容回答用户问题。

知识库内容：
{context}

用户问题：{question}

回答要求：
1. 优先使用知识库中的信息
2. 如果知识库中没有相关信息，请诚实说明"抱歉，这个问题我暂时无法回答"
3. 回答要简洁友好，避免重复
4. 如果涉及价格或功能对比，请列出具体信息

回答："""
        )
        
        # 构建Chain
        self.chain = self._build_chain()
        print("✅ RAG Chain 构建完成")
    
    def _build_chain(self):
        """构建RAG Chain"""
        chain = (
            {
                "context": self.retriever | self._format_docs,
                "question": RunnablePassthrough()
            }
            | self.prompt
            | self.llm
            | StrOutputParser()
        )
        return chain
    
    @staticmethod
    def _format_docs(docs):
        """格式化检索结果"""
        return "\n\n".join(doc.page_content for doc in docs)
    
    def query(self, question: str) -> str:
        """查询接口"""
        try:
            print(f"\n📝 用户问题: {question}")
            answer = self.chain.invoke(question)
            print(f"✅ 生成回答: {answer[:100]}...")
            return answer
        except Exception as e:
            print(f"❌ 处理错误: {str(e)}")
            return f"抱歉，处理您的问题时出现错误：{str(e)}"
    
    def query_with_sources(self, question: str):
        """查询并返回来源"""
        # 先检索
        docs = self.retriever.invoke(question)
        context = self._format_docs(docs)
        
        # 生成回答
        prompt_value = self.prompt.format(context=context, question=question)
        answer = self.llm.invoke(prompt_value)
        
        # 返回结果和来源
        return {
            "answer": answer.content,
            "sources": [
                {
                    "content": doc.page_content,
                    "metadata": doc.metadata
                } for doc in docs
            ]
        }

# 测试代码
if __name__ == "__main__":
    import sys
    import os
    sys.path.append(os.path.dirname(__file__))
    
    print("=" * 50)
    print("RAG Chain 测试")
    print("=" * 50)
    
    rag = RAGChain("data/product_faq.txt")
    
    # 测试问题
    questions = [
        "你们的产品有什么功能？",
        "智能手表多少钱？",
        "怎么连接手机？",
        "可以退换货吗？",
        "支持哪些运动模式？"
    ]
    
    for q in questions:
        print(f"\n{'=' * 50}")
        result = rag.query_with_sources(q)
        print(f"问题: {q}")
        print(f"回答: {result['answer']}")
        print(f"引用来源: {len(result['sources'])} 条")
"""
FastAPI 应用主文件
提供智能客服API接口
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from rag_chain import RAGChain
import uvicorn
import os
import sys

# 添加当前目录到系统路径
sys.path.append(os.path.dirname(__file__))

# 创建FastAPI应用
app = FastAPI(
    title="智能客服API",
    description="基于RAG的智能客服系统",
    version="1.0.0"
)

# 配置CORS（允许移动端访问）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应限制来源
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载前端静态文件
frontend_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
if os.path.exists(frontend_path):
    app.mount("/frontend", StaticFiles(directory=frontend_path, html=True), name="frontend")
    print(f"✅ 前端静态文件已挂载: {frontend_path}")

# 初始化RAG Chain（延迟加载）
rag_chain = None

def get_rag_chain():
    """获取或创建RAG Chain实例"""
    global rag_chain
    if rag_chain is None:
        data_path = os.path.join(os.path.dirname(__file__), "data", "product_faq.txt")
        rag_chain = RAGChain(data_path)
    return rag_chain

# 请求模型
class QueryRequest(BaseModel):
    question: str

# 响应模型
class QueryResponse(BaseModel):
    answer: str
    success: bool
    error: str = None

class QueryWithSourcesResponse(BaseModel):
    answer: str
    sources: list
    success: bool
    error: str = None

@app.get("/")
async def root():
    """健康检查"""
    return {
        "message": "智能客服API运行中",
        "version": "1.0.0",
        "status": "healthy"
    }

@app.get("/api/health")
async def health():
    """健康检查接口"""
    return {"status": "ok"}

@app.post("/api/query", response_model=QueryResponse)
async def query(request: QueryRequest):
    """
    查询接口
    
    Args:
        request: 包含用户问题的请求
        
    Returns:
        包含回答的响应
    """
    if not request.question or not request.question.strip():
        return QueryResponse(
            answer="",
            success=False,
            error="问题不能为空"
        )
    
    try:
        chain = get_rag_chain()
        answer = chain.query(request.question.strip())
        return QueryResponse(
            answer=answer,
            success=True
        )
    except Exception as e:
        print(f"❌ API错误: {str(e)}")
        return QueryResponse(
            answer="",
            success=False,
            error=str(e)
        )

@app.post("/api/query/sources", response_model=QueryWithSourcesResponse)
async def query_with_sources(request: QueryRequest):
    """
    查询接口（包含来源）
    
    Args:
        request: 包含用户问题的请求
        
    Returns:
        包含回答和来源的响应
    """
    if not request.question or not request.question.strip():
        return QueryWithSourcesResponse(
            answer="",
            sources=[],
            success=False,
            error="问题不能为空"
        )
    
    try:
        chain = get_rag_chain()
        result = chain.query_with_sources(request.question.strip())
        return QueryWithSourcesResponse(
            answer=result["answer"],
            sources=result["sources"],
            success=True
        )
    except Exception as e:
        print(f"❌ API错误: {str(e)}")
        return QueryWithSourcesResponse(
            answer="",
            sources=[],
            success=False,
            error=str(e)
        )

@app.on_event("startup")
async def startup_event():
    """应用启动时初始化"""
    print("\n" + "=" * 50)
    print("🚀 智能客服API 正在启动...")
    print("=" * 50)
    print("API地址: http://localhost:8000")
    print("API文档: http://localhost:8000/docs")
    print("=" * 50 + "\n")

if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
# LangChain RAG 智能客服系统

## 项目结构

```
langchain/
├── backend/                  # 后端服务
│   ├── data/                 # 知识库数据
│   │   └── product_faq.txt   # 产品FAQ文档
│   ├── knowledge_base.py     # 知识库管理
│   ├── rag_chain.py          # RAG Chain核心
│   ├── main.py               # FastAPI应用
│   └── requirements.txt      # Python依赖
│
└── frontend/                 # 前端应用
    └── index.html            # 移动端H5界面
```

## 快速启动

### 后端启动

```bash
cd backend

# 1. 安装依赖
pip install -r requirements.txt

# 2. 设置OpenAI API Key
export OPENAI_API_KEY="your-api-key"

# 3. 启动服务
python main.py
```

### 前端访问

打开浏览器访问：http://localhost:8000/frontend/index.html

或直接在后端运行时访问：http://localhost:8000/docs 查看API文档

## API接口

### 基础查询
```bash
curl -X POST "http://localhost:8000/api/query" \
  -H "Content-Type: application/json" \
  -d '{"question": "产品价格是多少？"}'
```

### 带来源查询
```bash
curl -X POST "http://localhost:8000/api/query/sources" \
  -H "Content-Type: application/json" \
  -d '{"question": "智能手表防水吗？"}'
```

## 技术栈

- **LangChain**: 业务编排和RAG实现
- **ChromaDB**: 向量数据库
- **FastAPI**: RESTful API
- **OpenAI**: LLM和Embedding模型

## 注意事项

1. 需要设置 `OPENAI_API_KEY` 环境变量
2. 首次运行会自动创建向量数据库（约30秒）
3. 生产环境需要配置CORS和安全策略
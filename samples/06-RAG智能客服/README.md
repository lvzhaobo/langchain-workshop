# LangChain RAG 智能客服系统

## 🎯 项目简介

这是一个基于 LangChain RAG（检索增强生成）技术的智能客服系统，支持移动端H5访问。

### 核心功能
- ✅ 基于知识库的智能问答
- ✅ 向量检索（ChromaDB）
- ✅ RESTful API接口
- ✅ 移动端友好的H5界面

### 技术栈
- **LangChain**: RAG 编排
- **ChromaDB**: 向量数据库
- **FastAPI**: 后端API
- **OpenAI**: LLM + Embedding

## 📁 项目结构

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
├── frontend/                 # 前端应用
│   └── index.html            # 移动端H5界面
│
├── start.sh                  # 启动脚本
└── README.md                 # 本文件
```

## 🚀 快速启动

### 方法一：使用启动脚本

```bash
# 1. 设置 OpenAI API Key
export OPENAI_API_KEY="your-api-key-here"

# 2. 运行启动脚本
chmod +x start.sh
./start.sh
```

### 方法二：手动启动

```bash
# 1. 进入后端目录
cd backend

# 2. 安装依赖
pip install -r requirements.txt

# 3. 设置环境变量
export OPENAI_API_KEY="your-api-key-here"

# 4. 启动服务
python main.py
```

## 📱 访问地址

启动成功后，访问以下地址：

- **前端界面**: http://localhost:8000/frontend/index.html
- **API文档**: http://localhost:8000/docs
- **健康检查**: http://localhost:8000/api/health

## 🔌 API接口

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

## 💡 使用示例

### 前端界面
打开浏览器访问 http://localhost:8000/frontend/index.html

可以直接点击快捷问题，或在输入框中输入您的问题。

### 测试问题示例
- "产品价格是多少？"
- "智能手表防水吗？"
- "如何连接手机？"
- "可以退换货吗？"
- "续航时间多久？"
- "支持哪些运动模式？"

## ⚙️ 配置说明

### 知识库配置
知识库文件位于 `backend/data/product_faq.txt`，您可以：
- 添加更多产品信息
- 更新价格和功能说明
- 增加常见问题解答

修改后，首次运行会自动重建向量数据库。

### 模型配置
默认使用 `gpt-3.5-turbo`，可在 `rag_chain.py` 中修改：
```python
self.llm = ChatOpenAI(
    model_name="gpt-3.5-turbo",  # 可改为 gpt-4
    temperature=0.7
)
```

## 🔧 开发指南

### 添加新知识文档

1. 编辑 `backend/data/product_faq.txt`
2. 删除旧的向量数据库：`rm -r backend/chroma_db`
3. 重启服务，会自动重建向量库

### 扩展知识库格式

目前支持纯文本格式，可以扩展支持：
- PDF文档（使用 PyPDFLoader）
- Markdown文件（使用 UnstructuredMarkdownLoader）
- Word文档（使用 Docx2txtLoader）

### 自定义Prompt模板

在 `rag_chain.py` 中修改 `self.prompt` 模板。

## 🐛 常见问题

### Q: 启动时报错 "无法连接OpenAI"
A: 检查是否正确设置了 `OPENAI_API_KEY` 环境变量

### Q: 前端界面无法访问
A: 确保后端服务正常运行，访问 http://localhost:8000/api/health 检查

### Q: 回答不准确
A: 
1. 检查知识库内容是否完整
2. 尝试调整检索数量 `search_kwargs={"k": 3}`
3. 优化Prompt模板

## 📚 学习资源

- [LangChain 官方文档](https://python.langchain.com/)
- [RAG 最佳实践](https://python.langchain.com/docs/use_cases/question_answering/)
- [FastAPI 文档](https://fastapi.tiangolo.com/)

## 🎓 Workshop材料

本项目配套以下学习材料：
- `langchain-core-concepts.md` - LangChain核心概念
- `rag-customer-service-workshop.md` - 实战Workshop指南
- `multi-framework-integration.md` - 多框架集成方案

## 📝 更新日志

### v1.0.0 (2026-05-17)
- ✅ 初始版本发布
- ✅ RAG基础功能
- ✅ 移动端H5界面
- ✅ 基础API接口
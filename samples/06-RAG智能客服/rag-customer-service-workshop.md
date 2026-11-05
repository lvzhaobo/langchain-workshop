# 实战Workshop：移动端智能客服RAG系统

## 项目概述

构建一个基于RAG（检索增强生成）的智能客服系统，支持移动端H5访问，能够回答企业产品相关问题。

### 技术栈
- **后端**：Python + LangChain + FastAPI
- **向量数据库**：ChromaDB（轻量级，适合Workshop）
- **前端**：Vue 3 + Vite（移动端H5）
- **模型**：OpenAI GPT-3.5-turbo 或 本地模型

---

## 第一部分：后端开发（60分钟）

### 1. 环境准备（10分钟）

#### 1.1 创建项目结构
```bash
mkdir rag-customer-service
cd rag-customer-service
mkdir backend frontend
cd backend
```

#### 1.2 安装依赖
```bash
# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装依赖
pip install langchain langchain-openai langchain-community
pip install chromadb
pip install fastapi uvicorn
pip install python-multipart
```

#### 1.3 创建 requirements.txt
```txt
langchain==0.1.0
langchain-openai==0.0.2
langchain-community==0.0.10
chromadb==0.4.22
fastapi==0.109.0
uvicorn==0.27.0
python-multipart==0.0.6
```

---

### 2. 构建知识库（15分钟）

#### 2.1 创建示例知识文档
创建 `data/product_faq.txt`：

```text
【产品介绍】
我们的智能手表支持心率监测、睡眠分析、运动记录等功能，续航时间长达7天。

【价格信息】
智能手表标准版：999元
智能手表专业版：1299元
智能手表运动版：1499元

【保修政策】
所有产品享受1年免费保修服务，自购买之日起计算。

【退换货】
7天无理由退货，15天换货，需保持产品完好不影响二次销售。

【配送范围】
全国包邮，港澳台地区暂不支持配送。

【使用问题】
心率监测功能需要在设置中开启，建议佩戴在手腕骨上方2-3cm处。

【常见问题】
Q: 如何连接手机？
A: 下载我们的APP，打开蓝牙，按照提示完成配对即可。

Q: 防水吗？
A: 支持IP68级防水，游泳时可佩戴，但不建议热水浴或桑拿时使用。

Q: 如何充电？
A: 使用配套的磁吸充电底座，充电约2小时可充满。
```

#### 2.2 文档加载与切分
创建 `backend/knowledge_base.py`：

```python
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
        print(f"文档已切分为 {len(chunks)} 个块")
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
        print(f"向量数据库已创建，保存在 {self.persist_directory}")
        return vectorstore
    
    def load_vectorstore(self):
        """加载已有向量数据库"""
        if not os.path.exists(self.persist_directory):
            print("向量数据库不存在，正在创建...")
            return self.create_vectorstore()
        
        vectorstore = Chroma(
            persist_directory=self.persist_directory,
            embedding_function=self.embeddings
        )
        print("向量数据库已加载")
        return vectorstore

# 测试
if __name__ == "__main__":
    kb = KnowledgeBase("data/product_faq.txt")
    vectorstore = kb.create_vectorstore()
    
    # 测试检索
    results = vectorstore.similarity_search("产品价格是多少", k=2)
    for i, doc in enumerate(results):
        print(f"\n结果 {i+1}:\n{doc.page_content}")
```

**练习1**：运行上述代码，测试知识库的检索功能。

---

### 3. 构建RAG Chain（20分钟）

#### 3.1 创建RAG Pipeline
创建 `backend/rag_chain.py`：

```python
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain.schema.runnable import RunnablePassthrough, RunnableParallel
from langchain.schema.output_parser import StrOutputParser
from knowledge_base import KnowledgeBase

class RAGChain:
    def __init__(self, data_path: str):
        """初始化RAG Chain"""
        # 加载知识库
        self.kb = KnowledgeBase(data_path)
        self.vectorstore = self.kb.load_vectorstore()
        self.retriever = self.vectorstore.as_retriever(
            search_kwargs={"k": 3}  # 检索top 3相关文档
        )
        
        # 初始化LLM
        self.llm = ChatOpenAI(
            model_name="gpt-3.5-turbo",
            temperature=0.7
        )
        
        # 创建prompt模板
        self.prompt = PromptTemplate.from_template(
            """你是一个专业的智能客服助手。请根据以下知识库内容回答用户问题。

知识库内容：
{context}

用户问题：{question}

回答要求：
1. 优先使用知识库中的信息
2. 如果知识库中没有相关信息，请诚实说明
3. 回答要简洁友好
4. 如果涉及价格，请列出具体价格信息

回答："""
        )
        
        # 构建Chain
        self.chain = self._build_chain()
    
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
            answer = self.chain.invoke(question)
            return answer
        except Exception as e:
            return f"抱歉，处理您的问题时出现错误：{str(e)}"

# 测试
if __name__ == "__main__":
    rag = RAGChain("data/product_faq.txt")
    
    # 测试问题
    questions = [
        "你们的产品有什么功能？",
        "智能手表多少钱？",
        "怎么连接手机？",
        "可以退换货吗？"
    ]
    
    for q in questions:
        print(f"\n问题：{q}")
        print(f"回答：{rag.query(q)}")
        print("-" * 50)
```

**练习2**：添加一个功能，在回答中标注引用了知识库中的哪些部分。

<details>
<summary>💡 参考答案</summary>

```python
def query_with_sources(self, question: str):
    """查询并返回来源"""
    # 先检索
    docs = self.retriever.get_relevant_documents(question)
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
```
</details>

---

### 4. 创建API接口（15分钟）

#### 4.1 创建FastAPI应用
创建 `backend/main.py`：

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from rag_chain import RAGChain
import uvicorn

# 创建FastAPI应用
app = FastAPI(title="智能客服API", version="1.0.0")

# 配置CORS（允许移动端访问）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应限制来源
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 初始化RAG Chain
rag_chain = RAGChain("data/product_faq.txt")

# 请求模型
class QueryRequest(BaseModel):
    question: str

# 响应模型
class QueryResponse(BaseModel):
    answer: str
    success: bool
    error: str = None

@app.get("/")
async def root():
    """健康检查"""
    return {"message": "智能客服API运行中"}

@app.post("/api/query", response_model=QueryResponse)
async def query(request: QueryRequest):
    """
    查询接口
    
    - **question**: 用户问题
    """
    try:
        answer = rag_chain.query(request.question)
        return QueryResponse(
            answer=answer,
            success=True
        )
    except Exception as e:
        return QueryResponse(
            answer="",
            success=False,
            error=str(e)
        )

@app.get("/api/history")
async def get_history():
    """获取历史记录（简化版）"""
    # 实际项目中应该从数据库获取
    return {"history": []}

if __name__ == "__main__":
    print("正在启动智能客服API...")
    print("访问地址: http://localhost:8000")
    print("API文档: http://localhost:8000/docs")
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

#### 4.2 测试API
```bash
# 启动服务
python main.py

# 新开终端测试
curl -X POST "http://localhost:8000/api/query" \
  -H "Content-Type: application/json" \
  -d '{"question": "产品价格是多少？"}'
```

**练习3**：添加一个接口，用于动态添加新的知识文档到向量库。

---

## 第二部分：前端开发（40分钟）

### 1. 创建Vue项目（5分钟）

```bash
cd ../frontend
npm create vite@latest . -- --template vue
npm install axios
```

### 2. 构建移动端界面（25分钟）

#### 2.1 主页面
编辑 `frontend/src/App.vue`：

```vue
<template>
  <div class="app">
    <header class="header">
      <h1>智能客服</h1>
    </header>
    
    <main class="chat-container">
      <div class="messages" ref="messagesContainer">
        <div
          v-for="(msg, index) in messages"
          :key="index"
          :class="['message', msg.type]"
        >
          <div class="avatar">{{ msg.type === 'user' ? '我' : 'AI' }}</div>
          <div class="content">{{ msg.content }}</div>
        </div>
        
        <div v-if="loading" class="message bot">
          <div class="avatar">AI</div>
          <div class="content typing">
            <span></span>
            <span></span>
            <span></span>
          </div>
        </div>
      </div>
    </main>
    
    <footer class="input-area">
      <input
        v-model="userInput"
        @keyup.enter="sendMessage"
        placeholder="请输入您的问题..."
        :disabled="loading"
      />
      <button @click="sendMessage" :disabled="loading || !userInput.trim()">
        发送
      </button>
    </footer>
    
    <!-- 快捷问题 -->
    <div class="quick-questions" v-if="messages.length === 0">
      <p class="tip">您可以问我：</p>
      <div class="question-list">
        <button
          v-for="q in quickQuestions"
          :key="q"
          @click="askQuickQuestion(q)"
          class="quick-btn"
        >
          {{ q }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, nextTick } from 'vue'
import axios from 'axios'

// API地址
const API_URL = 'http://localhost:8000'

// 状态
const messages = ref([])
const userInput = ref('')
const loading = ref(false)
const messagesContainer = ref(null)

// 快捷问题
const quickQuestions = ref([
  '产品价格是多少？',
  '如何连接手机？',
  '支持退换货吗？',
  '手表防水吗？'
])

// 发送消息
const sendMessage = async () => {
  const question = userInput.value.trim()
  if (!question || loading.value) return
  
  // 添加用户消息
  messages.value.push({
    type: 'user',
    content: question
  })
  
  userInput.value = ''
  loading.value = true
  
  try {
    // 调用API
    const response = await axios.post(`${API_URL}/api/query`, {
      question: question
    })
    
    // 添加AI回复
    messages.value.push({
      type: 'bot',
      content: response.data.answer
    })
  } catch (error) {
    messages.value.push({
      type: 'bot',
      content: '抱歉，服务暂时不可用，请稍后重试。'
    })
  } finally {
    loading.value = false
    scrollToBottom()
  }
}

// 快捷问题
const askQuickQuestion = (question) => {
  userInput.value = question
  sendMessage()
}

// 滚动到底部
const scrollToBottom = async () => {
  await nextTick()
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  }
}
</script>

<style scoped>
.app {
  max-width: 100%;
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: #f5f5f5;
}

.header {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  padding: 20px;
  text-align: center;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
}

.header h1 {
  margin: 0;
  font-size: 20px;
}

.chat-container {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  padding-bottom: 80px;
}

.messages {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.message {
  display: flex;
  gap: 12px;
  animation: fadeIn 0.3s ease;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}

.message.user {
  flex-direction: row-reverse;
}

.avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  flex-shrink: 0;
}

.message.user .avatar {
  background: #667eea;
  color: white;
}

.message.bot .avatar {
  background: #e0e0e0;
  color: #666;
}

.content {
  max-width: 70%;
  padding: 12px 16px;
  border-radius: 18px;
  line-height: 1.5;
  font-size: 14px;
}

.message.user .content {
  background: #667eea;
  color: white;
  border-bottom-right-radius: 4px;
}

.message.bot .content {
  background: white;
  color: #333;
  border-bottom-left-radius: 4px;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.1);
}

/* 打字动画 */
.typing {
  display: flex;
  gap: 4px;
  padding: 16px;
}

.typing span {
  width: 8px;
  height: 8px;
  background: #999;
  border-radius: 50%;
  animation: bounce 1.4s infinite ease-in-out;
}

.typing span:nth-child(1) { animation-delay: -0.32s; }
.typing span:nth-child(2) { animation-delay: -0.16s; }

@keyframes bounce {
  0%, 80%, 100% { transform: scale(0); }
  40% { transform: scale(1); }
}

/* 输入区域 */
.input-area {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  display: flex;
  gap: 12px;
  padding: 16px 20px;
  background: white;
  box-shadow: 0 -2px 10px rgba(0, 0, 0, 0.1);
}

.input-area input {
  flex: 1;
  padding: 12px 16px;
  border: 1px solid #ddd;
  border-radius: 24px;
  font-size: 14px;
  outline: none;
}

.input-area input:focus {
  border-color: #667eea;
}

.input-area button {
  padding: 12px 24px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border: none;
  border-radius: 24px;
  font-size: 14px;
  cursor: pointer;
}

.input-area button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* 快捷问题 */
.quick-questions {
  padding: 20px;
  text-align: center;
}

.tip {
  color: #999;
  margin-bottom: 12px;
}

.question-list {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  justify-content: center;
}

.quick-btn {
  padding: 8px 16px;
  background: white;
  border: 1px solid #ddd;
  border-radius: 16px;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
}

.quick-btn:hover {
  border-color: #667eea;
  color: #667eea;
}
</style>
```

#### 2.2 移动端适配
编辑 `frontend/index.html`：

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
  <meta name="theme-color" content="#667eea">
  <title>智能客服</title>
</head>
<body>
  <div id="app"></div>
  <script type="module" src="/src/main.js"></script>
</body>
</html>
```

### 3. 运行项目（10分钟）

```bash
# 安装依赖
npm install

# 启动开发服务器
npm run dev

# 访问 http://localhost:5173
# 在手机上访问：http://你的IP:5173
```

**练习4**：添加一个功能，支持语音输入（使用浏览器的Web Speech API）。

---

## 第三部分：优化与部署（20分钟）

### 1. 性能优化

#### 1.1 后端优化
```python
# 添加缓存
from functools import lru_cache

@lru_cache(maxsize=100)
def cached_query(question: str):
    """缓存常见问题的回答"""
    return rag_chain.query(question)
```

#### 1.2 前端优化
```javascript
// 添加请求防抖
import { debounce } from 'lodash-es'

const sendMessage = debounce(async () => {
  // ... 原有逻辑
}, 300)
```

### 2. 生产部署

#### 2.1 后端部署（使用Docker）
创建 `backend/Dockerfile`：

```dockerfile
FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

#### 2.2 前端部署
```bash
# 构建
npm run build

# 生成的dist目录可以部署到任何静态服务器
# 如 Nginx、Vercel、Netlify等
```

---

## 项目结构

```
rag-customer-service/
├── backend/
│   ├── data/
│   │   └── product_faq.txt      # 知识文档
│   ├── chroma_db/               # 向量数据库（自动生成）
│   ├── knowledge_base.py        # 知识库管理
│   ├── rag_chain.py             # RAG Chain
│   ├── main.py                  # FastAPI应用
│   ├── requirements.txt
│   └── Dockerfile
└── frontend/
    ├── src/
    │   ├── App.vue              # 主组件
    │   └── main.js
    ├── index.html
    └── package.json
```

---

## 学习要点总结

1. **RAG 核心流程**：文档加载 → 向量化 → 检索 → 生成回答
2. **Chain 编排**：使用 LCEL 构建 Pipeline
3. **移动端适配**：响应式设计、触摸优化
4. **前后端分离**：FastAPI + Vue 架构

---

## 常见问题

**Q1: 如何提高检索准确率？**
- 优化文档切分策略
- 调整检索数量 (k值)
- 使用重排序模型

**Q2: 如何支持更多文档格式？**
```python
from langchain_community.document_loaders import (
    PDFLoader, 
    Docx2txtLoader,
    UnstructuredMarkdownLoader
)
```

**Q3: 如何添加对话历史？**
```python
from langchain.memory import ConversationBufferMemory

memory = ConversationBufferMemory(
    memory_key="chat_history",
    return_messages=True
)
```

---

## 延伸练习

1. 添加用户认证功能
2. 实现对话历史持久化
3. 添加多轮对话支持
4. 实现知识库管理界面（上传、删除文档）
5. 添加回答评分功能
# 多框架协同方案：TensorFlow/PyTorch + LangChain + Vue

## 一、架构设计理念

### 为什么需要多框架协同？

在实际的大模型应用中，单一的框架往往无法满足所有需求：

```
┌─────────────────────────────────────────────────────┐
│                   应用需求层次                        │
├─────────────────────────────────────────────────────┤
│                                                     │
│  展示层    ←→  Vue/React - 用户交互                 │
│    ↓                                               │
│  编排层    ←→  LangChain - 业务逻辑编排              │
│    ↓                                               │
│  推理层    ←→  TensorFlow/PyTorch - 模型推理         │
│                                                     │
└─────────────────────────────────────────────────────┘
```

### 各框架的职责分工

| 框架 | 核心职责 | 优势 |
|------|---------|------|
| **TensorFlow/PyTorch** | 模型训练、推理、优化 | 深度学习原生支持、GPU加速 |
| **LangChain** | 链式编排、Agent调度、工具集成 | 业务逻辑清晰、开发效率高 |
| **Vue** | 用户界面、交互体验 | 移动端友好、组件化开发 |

---

## 二、架构设计详解

### 2.1 整体架构图

```
┌──────────────────────────────────────────────────────────┐
│                      用户界面层                           │
│                    (Vue 3 + Vite)                        │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐              │
│  │ 对话界面 │  │ 结果展示 │  │ 文件上传 │              │
│  └──────────┘  └──────────┘  └──────────┘              │
└───────────────────────┬──────────────────────────────────┘
                        │ HTTP/WebSocket
                        ↓
┌──────────────────────────────────────────────────────────┐
│                      API网关层                            │
│                    (FastAPI)                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐              │
│  │ 认证授权 │  │ 限流熔断 │  │ 日志监控 │              │
│  └──────────┘  └──────────┘  └──────────┘              │
└───────────────────────┬──────────────────────────────────┘
                        │
                        ↓
┌──────────────────────────────────────────────────────────┐
│                    业务编排层                             │
│                     (LangChain)                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐              │
│  │   Chain  │  │  Agent   │  │   Tool   │              │
│  │  编排器  │  │  调度器  │  │  工具箱  │              │
│  └──────────┘  └──────────┘  └──────────┘              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐              │
│  │  Memory  │  │ Retriever│  │  Prompt  │              │
│  │  记忆层  │  │  检索器  │  │  提示词  │              │
│  └──────────┘  └──────────┘  └──────────┘              │
└───────────────────────┬──────────────────────────────────┘
                        │
                        ↓
┌──────────────────────────────────────────────────────────┐
│                    模型推理层                             │
│              (TensorFlow / PyTorch)                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐              │
│  │ 文本模型 │  │ 图像模型 │  │ 向量模型 │              │
│  │ (LLM)    │  │ (CV)     │  │(Embedding)│             │
│  └──────────┘  └──────────┘  └──────────┘              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐              │
│  │ GPU加速  │  │ 模型优化 │  │ 批处理   │              │
│  └──────────┘  └──────────┘  └──────────┘              │
└───────────────────────┬──────────────────────────────────┘
                        │
                        ↓
┌──────────────────────────────────────────────────────────┐
│                    数据存储层                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐              │
│  │ 向量数据库│  │ 关系数据库│  │ 缓存层  │              │
│  │(ChromaDB)│  │(PostgreSQL)│ │ (Redis) │              │
│  └──────────┘  └──────────┘  └──────────┘              │
└──────────────────────────────────────────────────────────┘
```

### 2.2 数据流转过程

```
用户输入
  ↓
Vue组件 → 收集用户输入
  ↓
HTTP请求 → 发送到FastAPI后端
  ↓
LangChain Chain → 解析意图、选择工具
  ↓
Tool调用 → 可能调用：
  ├─ 向量检索 (Embedding模型 - PyTorch)
  ├─ 图像分析 (Vision模型 - TensorFlow)
  └─ 文本生成 (LLM - 可选PyTorch本地部署)
  ↓
结果聚合 → LangChain组合答案
  ↓
响应返回 → FastAPI格式化输出
  ↓
Vue渲染 → 展示给用户
```

---

## 三、核心集成方案

### 3.1 TensorFlow/PyTorch 模型服务化

#### 方案一：直接集成（适合小型应用）

```python
# backend/model_service.py
import torch
from transformers import AutoModel, AutoTokenizer
from langchain.tools import BaseTool
from typing import Optional, Type
from pydantic import BaseModel

class LocalEmbeddingTool(BaseTool):
    """本地Embedding模型工具"""
    name = "local_embedding"
    description = "使用本地模型生成文本向量"
    
    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        super().__init__()
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModel.from_pretrained(model_name)
        
        # 使用GPU（如果可用）
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model.to(self.device)
        self.model.eval()
    
    def _run(self, text: str) -> list:
        """生成向量"""
        with torch.no_grad():
            inputs = self.tokenizer(
                text, 
                return_tensors="pt", 
                padding=True, 
                truncation=True
            ).to(self.device)
            
            outputs = self.model(**inputs)
            # 使用平均池化
            embeddings = outputs.last_hidden_state.mean(dim=1)
            
            return embeddings.cpu().numpy().tolist()[0]
    
    async def _arun(self, text: str):
        """异步执行"""
        return self._run(text)

# 集成到LangChain
from langchain.agents import initialize_agent, Tool
from langchain_openai import OpenAI

# 创建工具
embedding_tool = LocalEmbeddingTool()

# 创建Agent
tools = [
    Tool(
        name="向量生成",
        func=embedding_tool.run,
        description="将文本转换为向量表示"
    )
]

llm = OpenAI(temperature=0)
agent = initialize_agent(tools, llm, agent="zero-shot-react-description")
```

#### 方案二：模型服务化（推荐生产环境）

```python
# backend/model_server.py
from fastapi import FastAPI
from pydantic import BaseModel
import torch
from transformers import AutoModel, AutoTokenizer
import uvicorn

app = FastAPI(title="模型推理服务")

class ModelService:
    def __init__(self):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.models = {}
        
    def load_model(self, model_name: str, model_type: str):
        """加载模型"""
        if model_type == "embedding":
            self.models[model_name] = {
                "tokenizer": AutoTokenizer.from_pretrained(model_name),
                "model": AutoModel.from_pretrained(model_name).to(self.device)
            }
        # 可以加载其他类型的模型
    
    def get_embedding(self, model_name: str, text: str):
        """获取向量"""
        model_dict = self.models[model_name]
        tokenizer = model_dict["tokenizer"]
        model = model_dict["model"]
        
        with torch.no_grad():
            inputs = tokenizer(text, return_tensors="pt", padding=True).to(self.device)
            outputs = model(**inputs)
            embedding = outputs.last_hidden_state.mean(dim=1)
            return embedding.cpu().numpy().tolist()[0]

# 全局模型服务
model_service = ModelService()

@app.on_event("startup")
async def startup():
    """启动时加载模型"""
    model_service.load_model(
        "sentence-transformers/all-MiniLM-L6-v2",
        "embedding"
    )

class EmbeddingRequest(BaseModel):
    text: str
    model: str = "sentence-transformers/all-MiniLM-L6-v2"

@app.post("/embedding")
async def get_embedding(request: EmbeddingRequest):
    """获取文本向量"""
    embedding = model_service.get_embedding(request.model, request.text)
    return {"embedding": embedding}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
```

然后在LangChain中调用：

```python
# backend/tools/remote_model_tool.py
import requests
from langchain.tools import BaseTool

class RemoteEmbeddingTool(BaseTool):
    name = "remote_embedding"
    description = "调用远程模型服务生成向量"
    
    def __init__(self, server_url: str):
        super().__init__()
        self.server_url = server_url
    
    def _run(self, text: str) -> list:
        response = requests.post(
            f"{self.server_url}/embedding",
            json={"text": text}
        )
        return response.json()["embedding"]

# 使用
tool = RemoteEmbeddingTool("http://localhost:8001")
```

### 3.2 TensorFlow 模型集成示例

```python
# backend/tensorflow_integration.py
import tensorflow as tf
from langchain.tools import BaseTool
import numpy as np

class ImageClassifierTool(BaseTool):
    """图像分类工具（TensorFlow）"""
    name = "image_classifier"
    description = "对图像进行分类"
    
    def __init__(self, model_path: str):
        super().__init__()
        self.model = tf.keras.models.load_model(model_path)
        self.class_names = ["产品A", "产品B", "产品C"]
    
    def _run(self, image_path: str) -> dict:
        """分类图像"""
        # 加载和预处理图像
        img = tf.keras.preprocessing.image.load_img(
            image_path, 
            target_size=(224, 224)
        )
        img_array = tf.keras.preprocessing.image.img_to_array(img)
        img_array = tf.expand_dims(img_array, 0)
        img_array /= 255.0
        
        # 预测
        predictions = self.model.predict(img_array)
        score = tf.nn.softmax(predictions[0])
        
        return {
            "class": self.class_names[np.argmax(score)],
            "confidence": float(np.max(score))
        }

# 在Agent中使用
from langchain.agents import initialize_agent, Tool
from langchain_openai import OpenAI

tools = [
    Tool(
        name="图像分类",
        func=ImageClassifierTool("models/product_classifier.h5").run,
        description="识别产品图片类别"
    )
]

llm = OpenAI(temperature=0)
agent = initialize_agent(tools, llm, verbose=True)

# 使用
result = agent.run("这张图片是什么产品？路径：/path/to/image.jpg")
```

### 3.3 LangChain 多模型编排

```python
# backend/multi_model_chain.py
from langchain.schema.runnable import RunnableParallel, RunnablePassthrough
from langchain.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from langchain.schema.output_parser import StrOutputParser

class MultiModelChain:
    """多模型协同Chain"""
    
    def __init__(self):
        # 文本模型
        self.text_llm = ChatOpenAI(model="gpt-3.5-turbo")
        
        # 向量模型服务（PyTorch）
        self.embedding_service = "http://localhost:8001"
        
        # 图像模型服务（TensorFlow）
        self.image_service = "http://localhost:8002"
    
    def build_chain(self):
        """构建多模型协同Chain"""
        
        # 文本分析Chain
        text_chain = (
            PromptTemplate.from_template("分析以下文本：{text}")
            | self.text_llm
            | StrOutputParser()
        )
        
        # 并行处理
        parallel_chain = RunnableParallel(
            text_analysis=text_chain,
            # 可以添加其他模型的Chain
            # image_analysis=image_chain,
            # audio_analysis=audio_chain
        )
        
        # 最终聚合
        final_chain = (
            {
                "results": parallel_chain,
                "query": RunnablePassthrough()
            }
            | PromptTemplate.from_template(
                "基于以下分析结果回答用户问题：\n"
                "文本分析：{text_analysis}\n"
                "用户问题：{query}"
            )
            | self.text_llm
            | StrOutputParser()
        )
        
        return final_chain
    
    async def process(self, query: str, text: str = None, image: str = None):
        """处理多模态输入"""
        # 根据输入类型调用不同模型
        results = {}
        
        if text:
            # 文本处理
            results["text"] = await self.process_text(text)
        
        if image:
            # 图像处理
            results["image"] = await self.process_image(image)
        
        # 聚合结果
        return await self.aggregate_results(query, results)
```

---

## 四、前端Vue集成方案

### 4.1 项目结构

```
frontend/
├── src/
│   ├── api/              # API调用
│   │   ├── chat.js       # 对话API
│   │   ├── upload.js     # 文件上传
│   │   └── model.js      # 模型服务API
│   ├── components/       # 组件
│   │   ├── ChatBox.vue   # 对话框
│   │   ├── ImageUpload.vue # 图片上传
│   │   └── ResultDisplay.vue # 结果展示
│   ├── composables/      # 组合式函数
│   │   ├── useChat.js    # 对话逻辑
│   │   └── useModel.js   # 模型调用
│   └── App.vue
```

### 4.2 核心组件实现

#### API层 (`src/api/model.js`)

```javascript
import axios from 'axios'

const MODEL_SERVICE = 'http://localhost:8001'
const CHAIN_SERVICE = 'http://localhost:8000'

export const modelAPI = {
  // 获取文本向量
  async getEmbedding(text) {
    const response = await axios.post(`${MODEL_SERVICE}/embedding`, { text })
    return response.data.embedding
  },
  
  // 图像分类
  async classifyImage(imageFile) {
    const formData = new FormData()
    formData.append('image', imageFile)
    
    const response = await axios.post(`${MODEL_SERVICE}/classify`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
    return response.data
  },
  
  // 多模态分析
  async multiModalAnalysis(data) {
    const response = await axios.post(`${CHAIN_SERVICE}/analyze`, data)
    return response.data
  }
}
```

#### 组合式函数 (`src/composables/useModel.js`)

```javascript
import { ref } from 'vue'
import { modelAPI } from '@/api/model'

export function useModel() {
  const loading = ref(false)
  const error = ref(null)
  
  // 文本向量生成
  const getEmbedding = async (text) => {
    loading.value = true
    error.value = null
    
    try {
      const embedding = await modelAPI.getEmbedding(text)
      return embedding
    } catch (e) {
      error.value = e.message
      throw e
    } finally {
      loading.value = false
    }
  }
  
  // 图像分类
  const classifyImage = async (imageFile) => {
    loading.value = true
    error.value = null
    
    try {
      const result = await modelAPI.classifyImage(imageFile)
      return result
    } catch (e) {
      error.value = e.message
      throw e
    } finally {
      loading.value = false
    }
  }
  
  return {
    loading,
    error,
    getEmbedding,
    classifyImage
  }
}
```

#### 多模态组件 (`src/components/MultiModalInput.vue`)

```vue
<template>
  <div class="multimodal-input">
    <!-- 文本输入 -->
    <div class="input-section">
      <textarea
        v-model="textInput"
        placeholder="输入文本内容..."
        rows="3"
      ></textarea>
    </div>
    
    <!-- 图片上传 -->
    <div class="upload-section">
      <input
        type="file"
        ref="fileInput"
        @change="handleImageUpload"
        accept="image/*"
        style="display: none"
      />
      <button @click="$refs.fileInput.click()" class="upload-btn">
        📷 上传图片
      </button>
      
      <div v-if="imagePreview" class="image-preview">
        <img :src="imagePreview" alt="预览" />
        <button @click="removeImage" class="remove-btn">×</button>
      </div>
    </div>
    
    <!-- 提交按钮 -->
    <button 
      @click="submit" 
      :disabled="!canSubmit || loading"
      class="submit-btn"
    >
      {{ loading ? '分析中...' : '开始分析' }}
    </button>
    
    <!-- 错误提示 -->
    <div v-if="error" class="error-message">
      {{ error }}
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useModel } from '@/composables/useModel'

const emit = defineEmits(['result'])

const { loading, error, classifyImage, getEmbedding } = useModel()

const textInput = ref('')
const imageFile = ref(null)
const imagePreview = ref('')

const canSubmit = computed(() => {
  return textInput.value.trim() || imageFile.value
})

const handleImageUpload = (event) => {
  const file = event.target.files[0]
  if (file) {
    imageFile.value = file
    imagePreview.value = URL.createObjectURL(file)
  }
}

const removeImage = () => {
  imageFile.value = null
  imagePreview.value = ''
}

const submit = async () => {
  const results = {
    text: textInput.value,
    image: null,
    embedding: null
  }
  
  try {
    // 处理文本
    if (textInput.value) {
      results.embedding = await getEmbedding(textInput.value)
    }
    
    // 处理图片
    if (imageFile.value) {
      results.image = await classifyImage(imageFile.value)
    }
    
    emit('result', results)
  } catch (e) {
    console.error('分析失败:', e)
  }
}
</script>

<style scoped>
.multimodal-input {
  padding: 20px;
  background: white;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.input-section textarea {
  width: 100%;
  padding: 12px;
  border: 1px solid #ddd;
  border-radius: 8px;
  font-size: 14px;
  resize: vertical;
}

.upload-section {
  margin: 16px 0;
}

.upload-btn {
  padding: 10px 20px;
  background: #f5f5f5;
  border: 1px dashed #999;
  border-radius: 8px;
  cursor: pointer;
}

.image-preview {
  position: relative;
  margin-top: 12px;
}

.image-preview img {
  max-width: 200px;
  border-radius: 8px;
}

.remove-btn {
  position: absolute;
  top: -8px;
  right: -8px;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: #ff4444;
  color: white;
  border: none;
  cursor: pointer;
}

.submit-btn {
  width: 100%;
  padding: 12px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border: none;
  border-radius: 8px;
  font-size: 16px;
  cursor: pointer;
}

.submit-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.error-message {
  margin-top: 12px;
  padding: 12px;
  background: #fee;
  color: #c00;
  border-radius: 8px;
}
</style>
```

### 4.3 移动端性能优化

```javascript
// src/utils/performance.js

// 图片压缩
export async function compressImage(file, maxWidth = 800) {
  return new Promise((resolve) => {
    const reader = new FileReader()
    reader.onload = (e) => {
      const img = new Image()
      img.onload = () => {
        const canvas = document.createElement('canvas')
        let width = img.width
        let height = img.height
        
        if (width > maxWidth) {
          height = (height * maxWidth) / width
          width = maxWidth
        }
        
        canvas.width = width
        canvas.height = height
        
        const ctx = canvas.getContext('2d')
        ctx.drawImage(img, 0, 0, width, height)
        
        canvas.toBlob(resolve, 'image/jpeg', 0.8)
      }
      img.src = e.target.result
    }
    reader.readAsDataURL(file)
  })
}

// 请求防抖
export function debounce(fn, delay) {
  let timer = null
  return function (...args) {
    clearTimeout(timer)
    timer = setTimeout(() => fn.apply(this, args), delay)
  }
}

// 请求节流
export function throttle(fn, delay) {
  let lastTime = 0
  return function (...args) {
    const now = Date.now()
    if (now - lastTime >= delay) {
      fn.apply(this, args)
      lastTime = now
    }
  }
}

// 使用示例
import { compressImage } from '@/utils/performance'

const handleImageUpload = async (event) => {
  const file = event.target.files[0]
  if (file) {
    // 移动端先压缩
    const compressedFile = await compressImage(file)
    imageFile.value = compressedFile
    imagePreview.value = URL.createObjectURL(compressedFile)
  }
}
```

---

## 五、完整集成示例

### 5.1 后端整合 (`backend/main.py`)

```python
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from langchain.schema.runnable import RunnablePassthrough
from multi_model_chain import MultiModelChain

app = FastAPI(title="多模态智能服务")

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 初始化多模型Chain
chain = MultiModelChain()

class TextRequest(BaseModel):
    text: str

class MultiModalRequest(BaseModel):
    text: str = None
    image_url: str = None
    query: str

@app.post("/api/analyze")
async def analyze(request: MultiModalRequest):
    """多模态分析"""
    result = await chain.process(
        query=request.query,
        text=request.text,
        image=request.image_url
    )
    return {"result": result}

@app.post("/api/embedding")
async def get_embedding(request: TextRequest):
    """文本向量化"""
    embedding = await chain.get_embedding(request.text)
    return {"embedding": embedding}

@app.post("/api/classify-image")
async def classify_image(file: UploadFile = File(...)):
    """图像分类"""
    # 保存临时文件
    temp_path = f"/tmp/{file.filename}"
    with open(temp_path, "wb") as f:
        f.write(await file.read())
    
    # 分类
    result = await chain.classify_image(temp_path)
    return result
```

### 5.2 Docker部署配置

#### 后端Dockerfile

```dockerfile
# backend/Dockerfile
FROM python:3.10-slim

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 安装Python依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制代码
COPY . .

# 暴露端口
EXPOSE 8000 8001

# 启动服务
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

#### docker-compose.yml

```yaml
version: '3.8'

services:
  # 后端服务
  backend:
    build: ./backend
    ports:
      - "8000:8000"
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
    depends_on:
      - redis
      - chromadb
  
  # 模型服务
  model-server:
    build: ./model_server
    ports:
      - "8001:8001"
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
  
  # 向量数据库
  chromadb:
    image: chromadb/chroma:latest
    ports:
      - "8002:8000"
    volumes:
      - chroma_data:/chroma/data
  
  # 缓存
  redis:
    image: redis:alpine
    ports:
      - "6379:6379"
  
  # 前端
  frontend:
    build: ./frontend
    ports:
      - "80:80"
    depends_on:
      - backend

volumes:
  chroma_data:
```

---

## 六、最佳实践与注意事项

### 6.1 性能优化建议

#### 模型层面
1. **批量处理**：将多个请求合并批量处理
2. **模型量化**：使用量化模型减少内存占用
3. **缓存策略**：对常见问题使用缓存

```python
# 批量处理示例
from langchain.schema.runnable import RunnableParallel

batch_chain = RunnableParallel(
    texts=text_chain.batch,  # 批量处理文本
    images=image_chain.batch  # 批量处理图像
)
```

#### 前端层面
1. **懒加载**：按需加载模型服务
2. **请求压缩**：压缩上传的图片和数据
3. **缓存策略**：使用LocalStorage缓存结果

### 6.2 安全注意事项

```python
# 输入验证
from pydantic import BaseModel, validator

class SafeRequest(BaseModel):
    text: str
    
    @validator('text')
    def validate_text(cls, v):
        # 防止注入攻击
        if len(v) > 10000:
            raise ValueError('文本过长')
        return v

# API限流
from fastapi_limiter import FastAPILimiter
from fastapi_limiter.depends import RateLimiter

@app.post("/api/query", dependencies=[Depends(RateLimiter(times=10, seconds=60))])
async def query(request: SafeRequest):
    # 限制每分钟10次
    pass
```

### 6.3 监控与日志

```python
import logging
from prometheus_client import Counter, Histogram

# 性能指标
request_count = Counter('request_count', 'Total requests')
request_latency = Histogram('request_latency_seconds', 'Request latency')

@app.middleware("http")
async def add_metrics(request, call_next):
    request_count.inc()
    with request_latency.time():
        response = await call_next(request)
    return response
```

---

## 七、项目结构总览

```
multi-modal-app/
├── backend/
│   ├── model_server/        # 模型服务
│   │   ├── server.py
│   │   └── Dockerfile
│   ├── chains/              # LangChain编排
│   │   ├── multi_model_chain.py
│   │   └── tools/
│   ├── api/                 # API接口
│   │   ├── routes/
│   │   └── main.py
│   ├── requirements.txt
│   └── Dockerfile
│
├── frontend/
│   ├── src/
│   │   ├── api/
│   │   ├── components/
│   │   ├── composables/
│   │   └── App.vue
│   ├── package.json
│   └── Dockerfile
│
├── docker-compose.yml
└── README.md
```

---

## 八、常见问题与解决方案

### Q1: 模型加载慢怎么办？
**A**: 使用模型预热、懒加载、或者模型服务独立部署

### Q2: GPU资源不足？
**A**: 使用CPU推理优化版模型，或使用云服务API

### Q3: 前端调用跨域？
**A**: 配置FastAPI的CORS中间件

### Q4: 移动端性能差？
**A**: 
- 图片压缩上传
- 使用流式响应
- 减少不必要的重渲染

---

## 九、延伸学习

1. **模型优化**：ONNX Runtime、TensorRT
2. **向量数据库**：Pinecone、Weaviate、Milvus
3. **监控告警**：Prometheus + Grafana
4. **自动化部署**：GitHub Actions、GitLab CI
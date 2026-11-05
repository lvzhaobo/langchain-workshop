# Lab 7.2 — 向量检索 + RAG 知识问答

> 把 12 篇电力技术文档变成可检索的知识库，让 AI 能回答它原本不知道的专业问题。

---

## 🎯 实验目标

1. 理解 Embedding 的核心原理：把文本变成向量，语义相近的文本向量距离也近
2. 用 ChromaDB 构建本地向量索引，实现语义检索
3. 搭建最简单的 RAG 管道：检索 → 拼到 Prompt → LLM 生成答案
4. 对比"有 RAG"和"无 RAG"的回答质量差异

---

## 📋 前置条件

| 序号 | 条件 | 说明 |
|------|------|------|
| 1 | Python 3.9+ | 运行脚本 |
| 2 | 百炼 API Key | Embedding 和 LLM 都需要 |
| 3 | 安装依赖 | `pip install langchain langchain-openai langchain-community chromadb` |
| 4 | 完成 Lab 7.1 | 了解基本的 LLM 调用方式 |

---

## 📦 实验数据

### 数据文件

| 文件路径 | 用途 | 说明 |
|----------|------|------|
| `demo/knowledge_base.json` | 知识库 | 12 篇电力技术文档，含故障诊断、巡检规程、技术规范、试验标准等 |
| `demo/rag_skeleton.py` | 骨架代码 | RAG 管道结构已写好，关键方法留空 |

### 知识库文档概览

| 编号 | 标题 | 类别 |
|------|------|------|
| doc_001 | 变压器油温异常诊断规程 | 故障诊断 |
| doc_002 | 断路器拒分故障处理流程 | 故障处理 |
| doc_003 | 输电线路巡检周期与内容 | 巡检规程 |
| doc_004 | 配电柜过流保护整定原则 | 技术规范 |
| doc_005 | GIS设备SF6气体管理要求 | 运行维护 |
| doc_006 | 电力电缆绝缘试验标准 | 试验标准 |
| doc_007 | 开关柜局部放电检测与评估 | 状态检测 |
| doc_008 | 继电保护装置定检项目清单 | 检修规程 |
| doc_009 | 电力设备接地装置技术要求 | 技术规范 |
| doc_010 | 变压器绕组变形检测方法 | 状态检测 |
| doc_011 | 直流系统蓄电池维护标准 | 运行维护 |
| doc_012 | 架空线路防雷保护措施 | 技术规范 |

### 背景信息

#### RAG 是什么

RAG（Retrieval-Augmented Generation，检索增强生成）解决了一个根本问题：**LLM 不知道训练数据以外的知识**。

```
没有 RAG：
  用户 → LLM → 回答（基于训练数据，可能编造）

有 RAG：
  用户 → 检索相关文档 → 把文档拼到 Prompt → LLM → 回答（基于真实文档）
```

#### 向量检索 vs 关键词检索

```
关键词检索（Ctrl+F）：
  查"变压器油温" → 只匹配包含这三个字的文档
  查"主变油温" → 找不到（因为写的是"变压器油温"）

向量检索（语义）：
  查"变压器油温" → 把查询转为向量 → 找余弦距离最近的文档
  查"主变油温" → 向量和"变压器油温"很接近 → 也能找到 ✅
```

Embedding 模型把文本映射到高维向量空间，语义相近的文本向量距离也近。

#### 百炼的 Embedding 端点

百炼 `text-embedding-v1` 模型通过兼容接口提供，可以直接用 `OpenAIEmbeddings` 调用：

```python
from langchain_openai import OpenAIEmbeddings

embeddings = OpenAIEmbeddings(
    model="text-embedding-v1",
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    api_key="你的 Key",
)
```

---

## 🔬 实验步骤

### Task 1：加载知识库并理解数据结构

**目标**：熟悉 12 篇文档的内容和结构，为后续分块和检索做准备。

**步骤**：

1. 用 Python 交互环境快速浏览知识库：

```bash
cd demo
python3 -c "
import json
with open('knowledge_base.json') as f:
    docs = json.load(f)
for d in docs:
    print(f\"[{d['category']}] {d['title']} ({len(d['content'])}字)\")
"
```

2. 选 3 篇不同类别的文档，读一遍内容。至少涵盖：
   - 一篇故障诊断类（doc_001 或 doc_002）
   - 一篇技术规范类（doc_004 或 doc_009）
   - 一篇运行维护类（doc_005 或 doc_011）

3. 思考：如果用户问"SF6 气体漏了怎么办"，哪些文档相关？如果是关键词检索能匹配哪些？向量检索能匹配哪些？

**预期结果**：了解知识库的结构，能判断"什么问题应该检索到哪篇文档"。

---

### Task 2：文档分块 + Embedding + 构建 ChromaDB 索引

**目标**：完成 `build_vector_index` 函数，把知识库变成可检索的向量数据库。

**步骤**：

1. 在 `rag_skeleton.py` 中找到 `build_vector_index` 函数
2. 完成实现：

```python
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document

def build_vector_index():
    # 1. 加载知识库
    kb = load_knowledge_base()
    
    # 2. 每篇文档包装为 LangChain Document
    documents = []
    for doc in kb:
        documents.append(Document(
            page_content=doc["content"],
            metadata={
                "title": doc["title"],
                "category": doc["category"],
                "doc_id": doc["id"],
            }
        ))
    
    # 3. 创建 Embedding 模型
    embeddings = OpenAIEmbeddings(
        model="text-embedding-v1",
        base_url=DASHSCOPE_BASE_URL,
        api_key=DASHSCOPE_API_KEY,
    )
    
    # 4. 构建 ChromaDB 向量索引
    vector_store = Chroma.from_documents(
        documents=documents,
        embedding=embeddings,
        persist_directory=str(DATA_DIR / "chroma_db"),  # 持久化到磁盘
    )
    
    return vector_store
```

3. **关键设计点**：
   - `persist_directory` 让向量索引保存在磁盘上，不需要每次重建
   - 每篇文档作为一个整块（12 篇约 5000 字），后续可以根据需要切分更细
   - Embedding 模型的选择决定了检索质量——`text-embedding-v1` 是百炼的中文优化模型

4. 测试：

```python
vector_store = build_vector_index()
print(f"索引构建完成，共 {vector_store._collection.count()} 条向量")
```

**预期结果**：`chroma_db/` 目录下有持久化的向量索引文件，`_collection.count()` 返回 12。

---

### Task 3：语义检索 — 用自然语言查文档

**目标**：完成 `similarity_search` 函数，验证向量检索的效果。

**步骤**：

1. 完成 `similarity_search` 函数：

```python
def similarity_search(vector_store, query: str, k: int = 3):
    results = vector_store.similarity_search(query, k=k)
    return results
```

2. 用不同查询测试检索效果：

```python
# 查询 1：精确关键词
results = similarity_search(vector_store, "变压器油温过高怎么处理？")
# 应该匹配 doc_001

# 查询 2：口语化表达
results = similarity_search(vector_store, "电缆要做哪些测试才能投运？")
# 应该匹配 doc_006（电力电缆绝缘试验标准）

# 查询 3：不太相关的查询
results = similarity_search(vector_store, "今天午饭吃什么？")
# 所有文档相似度都很低——观察 scores
```

3. 查看检索结果的标题和相似度：

```python
results = vector_store.similarity_search_with_relevance_scores(
    "变压器绕组有没有变形怎么查？", k=3
)
for doc, score in results:
    print(f"[{score:.4f}] {doc.metadata['title']}")
```

**预期结果**：
- 语义检索能准确匹配相关文档，即使查询用词和文档不完全一致
- 无关查询的相似度分数明显偏低

---

### Task 4：搭建 RAG 链 — 检索 + 生成

**目标**：完成 `rag_answer` 函数，实现"检索相关文档 → 拼到 Prompt → LLM 生成"的完整管道。

**步骤**：

1. 完成 `rag_answer` 函数：

```python
def rag_answer(vector_store, question: str) -> str:
    # 1. 检索
    docs = similarity_search(vector_store, question, k=3)
    
    # 2. 拼上下文
    context_parts = []
    for doc in docs:
        context_parts.append(
            f"【{doc.metadata['title']}】\n{doc.page_content}"
        )
    context = "\n\n".join(context_parts)
    
    # 3. 构造 Prompt
    prompt = f"""你是一个电力设备运维专家。请根据以下技术资料回答问题。
如果资料中找不到相关信息，请明确说"资料中未提供相关信息"，不要编造。

技术资料：
{context}

问题：{question}

请基于以上资料回答："""
    
    # 4. 调用 LLM
    llm = ChatOpenAI(
        model=MODEL,
        base_url=DASHSCOPE_BASE_URL,
        api_key=DASHSCOPE_API_KEY,
        temperature=0,
    )
    response = llm.invoke(prompt)
    
    # 5. 返回答案和来源
    sources = [d.metadata['title'] for d in docs]
    return {
        "answer": response.content,
        "sources": sources,
    }
```

2. 测试几个问题：

```
"SF6气体泄漏的标准和处理方法是什么？"
"变压器油温超过多少度需要停机？"
"断路器拒分应该怎么排查？"
```

3. 检查每个回答：
   - 答案是否能在对应的来源文档中找到依据？
   - LLM 有没有编造文档中没有的内容？

**预期结果**：RAG 回答有据可查，引用的内容在来源文档中能找到。

---

### Task 5：对比实验 — 有 RAG vs 无 RAG

**目标**：完成 `compare_rag_vs_no_rag` 函数，量化 RAG 的价值。

**步骤**：

1. 完成对比函数：

```python
def compare_rag_vs_no_rag(vector_store):
    llm = ChatOpenAI(
        model=MODEL,
        base_url=DASHSCOPE_BASE_URL,
        api_key=DASHSCOPE_API_KEY,
        temperature=0,
    )
    
    questions = [
        "变压器油温超过85度应该怎么处理？",
        "10kV开关柜局部放电的检测标准是什么？",
        "架空线路防雷有哪些措施？",
    ]
    
    for q in questions:
        print(f"\n{'─'*50}")
        print(f"❓ {q}")
        
        # 无 RAG
        response = llm.invoke(q)
        print(f"\n📝 无 RAG（LLM 直接回答）：")
        print(f"   {response.content[:250]}")
        
        # 有 RAG
        result = rag_answer(vector_store, q)
        print(f"\n📚 有 RAG（检索后回答）：")
        print(f"   答案：{result['answer'][:250]}")
        print(f"   来源：{', '.join(result['sources'])}")
```

2. 对每个问题，判断：
   - 无 RAG 的回答是否准确？有没有编造数据？
   - 有 RAG 的回答引用了哪些来源？引用是否恰当？
   - 哪个回答更可信？

3. （选做）增加一个"超出知识库范围"的问题：
   ```
   "风力发电机的叶片维护周期是多少？"
   ```
   知识库中没有风电相关内容——正确行为应该是："资料中未提供相关信息"，而不是编造。

**预期结果**：有 RAG 的回答有明确来源，专业问题的准确度明显高于无 RAG。超出知识库范围的问题，RAG 不会编造。

---

### Task 6（选做）：用百炼 DashVector 替换 ChromaDB

**目标**：体验云端向量数据库，理解本地 vs 云端的差异。

**步骤**：

1. 在百炼控制台开通 DashVector 服务（如果有权限）
2. 安装 SDK：`pip install dashvector`
3. 将 `build_vector_index` 中的 `Chroma` 替换为 DashVector 客户端
4. 对比两种方案：
   - 初始化复杂度
   - 检索速度
   - 是否支持多用户共享

**提示**：如果百炼 DashVector 不可用，可以尝试用 FAISS（`pip install faiss-cpu`）作为本地方案对比：

```python
from langchain_community.vectorstores import FAISS

vector_store = FAISS.from_documents(documents, embeddings)
vector_store.save_local(str(DATA_DIR / "faiss_index"))
```

---

## 📊 结果产出

| 产出 | 格式 | 位置 | 说明 |
|------|------|------|------|
| 完整 RAG 代码 | `.py` | `demo/rag_skeleton.py` | `build_vector_index`、`similarity_search`、`rag_answer` 均已实现 |
| ChromaDB 索引 | 目录 | `demo/chroma_db/` | 持久化的向量索引 |
| 检索效果记录 | 文本 | 终端输出 | 3 个查询的 Top-3 检索结果和分数 |
| RAG vs 直接回答对比 | 文本 | 终端输出 | 3 个专业问题的对比结果 |

---

## 📸 打卡内容

| 序号 | 打卡项 | 具体要求 | 检查 |
|------|--------|----------|------|
| 1 | **向量索引构建截图** | `_collection.count()` 返回 12 | ☐ |
| 2 | **语义检索效果截图** | 3 个查询的检索结果，展示标题和相似度 | ☐ |
| 3 | **RAG 回答截图** | 一个专业问题的完整 RAG 回答 + 来源列表 | ☐ |
| 4 | **RAG vs 无 RAG 对比截图** | 同一问题，两种方式的回答差异 | ☐ |

---

## ⚠️ 常见问题

| 问题 | 原因 | 解决方法 |
|------|------|----------|
| `chromadb` 安装失败 | 缺少 C++ 编译环境（Windows） | `pip install chromadb` 通常不需要编译；如失败用 `pip install faiss-cpu` 替代 |
| Embedding 调用 401 | API Key 错误 | 检查 `DASHSCOPE_API_KEY`，确认百炼控制台 Key 有效 |
| Embedding 调用报"model not found" | 模型名不对 | 百炼兼容接口用 `text-embedding-v1`；如果是 DashScope SDK，用 `text-embedding-v2` |
| 检索结果不相关 | Embedding 模型对中文语义理解不够 | 尝试用不同的查询表述；或者把文档切成更小的块 |
| LLM 在 RAG 中依然编造 | Prompt 没有强调"不要编造" | 在 Prompt 中加 `如果资料中找不到，请明确说明，不要编造` |
| ChromaDB 重复索引 | 每次运行都创建新索引 | 先检查 `chroma_db/` 是否存在，存在则用 `Chroma(persist_directory=..., embedding_function=...)` 加载而非重建 |

---

**🎉 恭喜完成实验！**

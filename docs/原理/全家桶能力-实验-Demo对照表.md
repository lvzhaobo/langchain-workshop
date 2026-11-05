# LangChain 全家桶能力 · 实验 · 5G Demo 对照表

> 验证时间：2026-07-25 · 全部接口 curl 实测通过
> ✅ 真实可运行 · ⚠️ 代码有但前端未展示 · ❌ 未覆盖

| LangChain 全家桶技术能力 | 实验 | 5G Demo 平台 | 实测 |
|------------------------|----------------------------------|--------------------------|
| ✅ **ChatModel 多模型调用** | sample-5 LLM节点 · sample-6 Agent循环 · labs-new 1.4 | 后端 DeepSeek ChatOpenAI · 前端 Agent 中心对话 |
| ✅ **Messages 消息类型** | sample-5/6 Human/AI/System/ToolMessage · labs-new 1.4 | 后端 MessagesState · 前端 SSE 消息流 |
| ✅ **@tool 工具定义** | sample-6 @tool装饰器 · labs-new 1.4 | 后端 query_device/query_alarms/list_devices |
| ✅ **bind_tools 工具绑定** | sample-6 .bind_tools(TOOLS) | 后端 ChatOpenAI.bind_tools(TOOLS) |
| ✅ **ToolNode 工具执行** | sample-6 ToolNode(TOOLS) | 后端 ToolNode 自动执行 |
| ⚠️ **Structured Output** | sample-4/4b TypedDict+Pydantic · labs-new 1.5 | 后端 HITLState 等 TypedDict 定义 |
| ✅ **Prompt Template** | sample-15 ChatPromptTemplate · labs-new 1.4 | 后端 SystemMessage + Prompt 模板 |
| ✅ **LCEL 管道语法 `\|`** | sample-14 RAG链 · labs-new 2.5 | 后端 /rag/search 接口内 LCEL 链 |
| ✅ **ReAct Agent 循环** | sample-6 LLM↔Tool · labs-new 1.4 | 后端 /agent/single · 前端 Agent 中心→LangChain Tab |
| ✅ **Document Loader** | sample-14 TextLoader · labs-new 2.1 | 后端 knowledge.txt 加载 |
| ✅ **Text Splitter** | sample-14 RecursiveCharacterTextSplitter · labs-new 2.1 | 后端 chunk_size=200 切割 |
| ⚠️ **Embeddings 向量化** | sample-14 OpenAIEmbeddings · labs-new 2.1 | 后端 DashScope Embeddings（需 Key） |
| ⚠️ **FAISS 向量索引** | sample-14 FAISS.from_documents · labs-new 2.1 | 后端 FAISS 索引（需 Key） |
| ✅ **Retriever 检索器** | sample-14 as_retriever(k=2) · labs-new 2.5 | 后端 关键词匹配检索 · 前端 知识库页搜索+结果 |
| ✅ **RAG 完整链路** | sample-14 loader→split→embed→FAISS→retrieve→LLM · labs-new 2.5 | 前端 知识库页检索输入+结果展示 |
| ⚠️ **Memory Buffer/Window/Summary** | sample-13 三层记忆 · labs-new 2.7 | 后端 MessagesState + MEMORY.md · ⚠️ 前端未展示 |
| ✅ **Checkpoint 持久化** | sample-7 MemorySaver/SqliteSaver · labs-new 3.4 | 后端 MemorySaver + /sessions 接口 |
| ✅ **thread_id 会话隔离** | sample-7 thread_id 隔离 | 后端 所有 Agent 接口带 thread_id 参数 |
| ✅ **StateGraph 图构建** | sample-1~12 StateGraph 三要素 · labs-new 3.2 | 后端 所有 Agent 均 StateGraph 构建 |
| ✅ **add_edge 固定边** | sample-1 线性串联 | 后端 Supervisor/HITL 图内 add_edge |
| ✅ **add_conditional_edges** | sample-2 条件分支 · labs-new 3.1 | 后端 Supervisor 路由 · 前端 审批分叉展示 |
| ✅ **Supervisor 多 Agent** | sample-12 Supervisor+Worker循环 · labs-new 3.2 | 后端 /agent/supervisor · 前端 一键全流程按钮 |
| ✅ **HITL 人工审批** | sample-8 interrupt+Command(resume) · labs-new 3.4 | 后端 /agent/hitl/start+decide · 前端 弹窗审批交互 |
| ✅ **Stream 流式输出** | sample-9 三种stream_mode · labs-new 3.7 | 后端 SSE stream_mode="messages" · 前端 逐token打字机 |
| ⚠️ **Command 动态路由** | sample-10 Command(goto, update) | ⚠️ 后端代码有 · 前端未展示 |
| ⚠️ **Subgraph 子图嵌套** | sample-11 add_node(compiled_graph) · labs-new 3.3 | ⚠️ 后端代码可复用 · 前端未展示 |
| ❌ **Send API 并行派发** | sample-3 Send+fan-out · labs-new 3.3 | ❌ 未接入 |
| ✅ **LangSmith Trace** | sample-15 环境变量配置 · labs-new 3.6 | 后端 已开启 tracing · 前端 LangSmith 网页查看 |
| ✅ **LangServe 部署** | demo-2/observ-lab serve_langserve.py · labs-new 4.4 | 后端 Flask 替代 · 前端 HTTP 调用 |
| ⚠️ **Skills 模板打包** | sample-16 Skills目录 · labs-new 4.6 | ⚠️ 独立 sample-16 目录 |
| ⚠️ **Coze/Dify 低代码** | labs-new 1.2a/1.2b | 前端 Agent 中心→Coze/Dify Tab（实验指引） |
| ✅ **设备数据对接** | labs-new 1.1/1.3 平台API | 后端 /api/devices 转发 · 前端 Dashboard 设备列表 |
| ❌ **安全护栏** | labs-new 3.5 | ❌ 未接入 |
| ❌ **SDD/测试/部署** | labs-new 4.1~4.5 | ❌ 非平台功能 |

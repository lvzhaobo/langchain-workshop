"""LangChain RAG Agent — 5G 基站排障智能体（含知识库检索）

相比 1.4 agent_langchain.py，新增 search_kb 工具，连接 FAISS 知识库。
"""
import os
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))  # 自动读取课程根目录 .env

import requests
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.tools import tool
from langchain.agents import create_agent

BASE_URL = "http://localhost:8025"


# ── 工具 1：查设备详情 ──
@tool
def query_device(device_id: str) -> str:
    """查询指定 5G 基站设备的运行状态、型号、厂商、站点等详细信息。
    当用户提到具体设备 ID（如 DEV-0001）时，使用此工具获取该设备的数据。"""
    resp = requests.get(f"{BASE_URL}/devices/{device_id}", timeout=5)
    data = resp.json()
    if not data.get("found"):
        return f"设备 {device_id} 不存在"
    d = data["device"]
    alarms = d.get("alarms", [])
    alarm_info = "\n".join([
        f"  [{a['severity']}] {a['type']}: {a['description']}"
        for a in alarms
    ]) if alarms else "无告警"
    return (
        f"设备 {device_id}：{d['vendor']} {d['model']}，{d['type']}，"
        f"站点 {d['site']}，状态 {d['status']}，IP {d['ip']}。"
        f"告警（{len(alarms)}条）：\n{alarm_info}"
    )


# ── 工具 2：查设备列表 ──
@tool
def list_devices(status: str = "", vendor: str = "") -> str:
    """获取 5G 基站设备列表，可按状态（running/alarm/maintenance）和厂商筛选。"""
    params = {}
    if status:
        params["status"] = status
    if vendor:
        params["vendor"] = vendor
    resp = requests.get(f"{BASE_URL}/devices", params=params, timeout=5)
    data = resp.json()
    devices = data.get("devices", [])
    if not devices:
        return "没有匹配的设备"
    lines = [f"共 {data['total']} 台设备，显示前 {len(devices)} 台："]
    for d in devices:
        alarms = len(d.get("alarms", []))
        lines.append(
            f"  {d['device_id']} | {d['vendor']} {d['model']} | "
            f"{d['status']} | 告警{alarms}条"
        )
    return "\n".join(lines)


# ── 工具 3：查设备告警 ──
@tool
def get_alarms(device_id: str) -> str:
    """查询指定 5G 基站设备的告警详情。"""
    resp = requests.get(f"{BASE_URL}/devices/{device_id}/alarms", timeout=5)
    data = resp.json()
    alarms = data.get("alarms", [])
    if not alarms:
        return f"设备 {device_id} 当前无告警"
    lines = [f"设备 {device_id} 共 {len(alarms)} 条告警："]
    for a in alarms:
        lines.append(f"  [{a['severity']}] {a['type']}: {a['description']}")
    return "\n".join(lines)


# ── 工具 4：搜知识库 ── 2.5 新增！
@tool
def search_kb(query: str) -> str:
    """在 5G 基站排障知识库中搜索相关内容。当用户询问故障原因、排查方法、
    处理流程时，优先使用此工具。返回 Top 3 最相关的排障文档片段。"""
    embeddings = OpenAIEmbeddings(
        model="text-embedding-v3",
        api_key=os.getenv("DASHSCOPE_API_KEY"),
        base_url=os.getenv("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
        check_embedding_ctx_length=False,
        chunk_size=10,
    )
    vectorstore = FAISS.load_local(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "faiss_index"),
        embeddings,
        allow_dangerous_deserialization=True,
    )
    docs = vectorstore.similarity_search_with_relevance_scores(query, k=3)

    if not docs or docs[0][1] < 0.5:
        return "知识库中未找到高度相关内容，建议换个角度描述问题。"

    result_parts = []
    for doc, score in docs:
        source = doc.metadata.get("source", "未知来源")
        result_parts.append(
            f"[来源: {source}] [相似度: {score:.2f}]\n{doc.page_content}"
        )
    return "\n\n---\n".join(result_parts)


# ── 创建 Agent ──
def create_rag_agent():
    llm = ChatOpenAI(
        model=os.getenv("AGENT_MODEL", "deepseek-chat"),
        temperature=0,
        api_key=os.getenv("AGENT_API_KEY", "REPLACE_ME_NO_KEY"),
        base_url=os.getenv("AGENT_API_BASE", "https://api.deepseek.com/v1"),
    )

    tools = [query_device, list_devices, get_alarms, search_kb]

    system_prompt = """你是 5G 基站智能排障助手。你可以使用以下工具：

- query_device：查询指定设备详情
- list_devices：获取设备列表
- get_alarms：查询设备告警
- search_kb：检索排障知识库（故障原因、排查步骤、处理流程）

工作流程：
1. 先调 query_device / get_alarms 获取设备状态
2. 再调 search_kb 检索相关排障知识
3. 综合设备数据和知识库内容，给出诊断建议

回答要求：
- 引用知识库中的具体步骤和命令
- 标注引用的文档来源
- 知识库中没有的内容，如实说明
- 不确定时说明"建议进一步检查" """

    return create_agent(
        model=llm,
        tools=tools,
        system_prompt=system_prompt,
    )


# ── 快速测试 ──
if __name__ == "__main__":
    agent = create_rag_agent()
    result = agent.invoke({
        "messages": [
            {"role": "user", "content": "DEV-0001 有告警，帮我分析下并参考知识库给出排查建议"}
        ]
    })
    # create_agent 返回最后一条消息的 content 作为最终回答
    final_message = result["messages"][-1]
    print(final_message.content)

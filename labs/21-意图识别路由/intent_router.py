"""意图识别 + 路由 Agent —— 一句话自动分发到正确的处理通道

运行：python intent_router.py
依赖：pip install langchain langchain-openai langchain-community faiss-cpu python-dotenv requests
前置：1.1 平台服务（localhost:8000）、2.1 的 faiss_index、1.1 的 devices.json
"""
import os
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))  # 自动读取课程根目录 .env

import json
import re
import sqlite3
import time
from pathlib import Path
from typing import Literal, Any

import requests
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain.agents import tool, create_tool_calling_agent, AgentExecutor
from langchain.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableBranch
from langchain_core.output_parsers import StrOutputParser, PydanticOutputParser
from pydantic import BaseModel, Field, field_validator

# ═══ 配置 ═══
BASE_URL = "http://localhost:8000"
API_KEY = os.getenv("AGENT_API_KEY", "REPLACE_ME_NO_KEY")
API_BASE = os.getenv("AGENT_API_BASE", "https://api.deepseek.com/v1")
MODEL = os.getenv("AGENT_MODEL", "deepseek-chat")

llm = ChatOpenAI(model=MODEL, temperature=0, api_key=API_KEY, base_url=API_BASE)


# ══════════════════════════════════════════════════════════════
# 第一部分：意图识别
# ══════════════════════════════════════════════════════════════

class IntentResult(BaseModel):
    """意图分类结果"""
    intent: Literal["diagnose", "query_data", "troubleshoot", "chat"] = Field(
        description="用户意图分类。diagnose=查设备状态/分析告警；query_data=统计/分组/趋势查询；troubleshoot=排查故障/搜索知识库；chat=闲聊/通用问答/其他"
    )
    device_id: str = Field(default="", description="如果用户提到了具体设备ID则提取，格式DEV-XXXX")
    reason: str = Field(description="一句话简述分类依据")

    @field_validator("device_id")
    @classmethod
    def _only_real_device_id(cls, v: str) -> str:
        """LLM 提取的槽位不能直接信，得自己校一道格式

        字段描述里写了"格式 DEV-XXXX"，但实测输入"AAU5613 SCTP 链路
        中断怎么排查"时，它会把设备型号 AAU5613 当成设备 ID 填进来。
        型号不是 ID，拿它去调 /devices/AAU5613 只会 404。结构化输出只保证
        JSON 能解析、枚举合法，不保证自由文本字段真的符合你在描述里
        提的格式要求 —— 那只是一句提示，不是约束。
        """
        v = v.strip().upper()
        return v if re.fullmatch(r"DEV-\d{4}", v) else ""


intent_parser = PydanticOutputParser(pydantic_object=IntentResult)

intent_prompt = ChatPromptTemplate.from_template("""你是 5G 基站运维平台的意图识别模块。分析用户输入，归类为四种意图之一。

意图定义：
- diagnose：查询设备状态、查看告警详情、分析设备运行情况。"DEV-0001 状态怎么样""有哪些告警"
- query_data：统计数据、分组对比、趋势分析、Top N。"告警设备有几台""华为和爱立信各多少""本月P0告警趋势"
- troubleshoot：排查故障原因、搜索处理方法、找排障步骤。"AAU5613 SCTP链路中断怎么修""这个告警怎么处理"
- chat：其他——闲聊、自我介绍、不在前三种范围内的问题。"你好""你能做什么""今天天气"

{format_instructions}

用户输入：{input}""")

intent_chain = intent_prompt.partial(format_instructions=intent_parser.get_format_instructions()) | llm | intent_parser


def classify_intent(user_input: str) -> IntentResult:
    """识别用户意图，返回分类结果"""
    return intent_chain.invoke({"input": user_input})


# ══════════════════════════════════════════════════════════════
# 第二部分：四个处理通道对应的工具集
# ══════════════════════════════════════════════════════════════

# ── 取数的降级策略：HTTP 优先，本地文件兜底 ──
#
# 为什么要这层：工具函数如果只写 except 里 return f"查询失败：{e}"，
# 平台没起的时候 Agent 不会报错也不会停 —— 它拿着"查询失败"这句话，
# 照样能编出一份格式完整、看着挺专业的分析报告。静默产出胡编结果
# 比直接崩溃更危险，因为你根本看不出它在编。
#
# 所以降级要分三档：真实数据 → 本地快照（明确标注）→ 明确失败。
# 第三档必须让 LLM 知道"这次真没数据"，而不是给它一句可以糊过去的话。

DEVICES_FILE = Path(__file__).parent / "data" / "devices.json"
if not DEVICES_FILE.exists():
    DEVICES_FILE = Path(__file__).parent.parent / "04-平台搭建" / "data" / "devices.json"
_degraded = False   # 是否已降级到本地快照，供输出时提示


def _load_local_devices() -> list[dict[str, Any]]:
    """读 1.1 造好的 devices.json —— 平台 API 也是读这份，数据完全一致"""
    global _degraded
    try:
        devices = json.loads(DEVICES_FILE.read_text(encoding="utf-8"))
        _degraded = True
        return devices
    except Exception:
        return []


def _fmt_alarms(alarms: list[dict[str, Any]], indent: str = "  ") -> str:
    if not alarms:
        return "无告警"
    return "\n".join(f"{indent}[{a['severity']}] {a['type']}: {a['description']}" for a in alarms)


def _degraded_note() -> str:
    return "\n（数据来源：本地快照，平台 API 未启动）" if _degraded else ""


# ── 工具 1-3：设备查询工具（Day 1 的产物）──
@tool
def query_device(device_id: str) -> str:
    """查询 5G 基站设备详情。"""
    d = None
    try:
        resp = requests.get(f"{BASE_URL}/devices/{device_id}", timeout=5)
        data = resp.json()
        if not data.get("found"):
            return f"设备 {device_id} 不存在"
        d = data["device"]
    except Exception:
        d = next((x for x in _load_local_devices() if x["device_id"] == device_id), None)
        if d is None:
            return f"取数失败：平台 API 不可达，本地快照中也没有 {device_id}。请勿基于推测作答，直接说明数据不可用。"

    alarms = d.get("alarms", [])
    return (
        f"设备 {device_id}：{d['vendor']} {d['model']}，{d['type']}，"
        f"站点 {d['site']}，状态 {d['status']}，IP {d['ip']}。"
        f"告警（{len(alarms)}条）：\n{_fmt_alarms(alarms)}" + _degraded_note()
    )


@tool
def list_devices(status: str = "", vendor: str = "") -> str:
    """获取设备列表，可按状态（running/alarm/maintenance）和厂商筛选。"""
    devices, total = None, 0
    try:
        params = {}
        if status:
            params["status"] = status
        if vendor:
            params["vendor"] = vendor
        resp = requests.get(f"{BASE_URL}/devices", params=params, timeout=5)
        data = resp.json()
        devices = data.get("devices", [])
        total = data.get("total", len(devices))
    except Exception:
        devices = _load_local_devices()
        if not devices:
            return "取数失败：平台 API 不可达，本地快照也读不到。请勿基于推测作答，直接说明数据不可用。"
        # 平台的筛选逻辑在本地重放一遍，保证降级前后语义一致
        if status:
            devices = [d for d in devices if d["status"] == status]
        if vendor:
            devices = [d for d in devices if vendor in d["vendor"]]
        total = len(devices)
        devices = devices[:20]

    if not devices:
        return "没有匹配的设备"
    lines = [f"共 {total} 台设备"]
    for d in devices:
        lines.append(f"  {d['device_id']} | {d['vendor']} {d['model']} | {d['status']} | 告警{len(d.get('alarms', []))}条")
    return "\n".join(lines) + _degraded_note()


@tool
def get_alarms(device_id: str) -> str:
    """查询指定设备的告警列表。"""
    alarms = None
    try:
        resp = requests.get(f"{BASE_URL}/devices/{device_id}/alarms", timeout=5)
        alarms = resp.json().get("alarms", [])
    except Exception:
        d = next((x for x in _load_local_devices() if x["device_id"] == device_id), None)
        if d is None:
            return f"取数失败：平台 API 不可达，本地快照中也没有 {device_id}。请勿基于推测作答，直接说明数据不可用。"
        alarms = d.get("alarms", [])

    if not alarms:
        return f"设备 {device_id} 无告警" + _degraded_note()
    lines = [f"设备 {device_id} 共 {len(alarms)} 条告警："]
    for a in alarms:
        lines.append(f"  [{a['severity']}] {a['type']}: {a['description']}")
    return "\n".join(lines) + _degraded_note()


# ── 工具 4：知识库检索（Day 2 产物）──
@tool
def search_kb(query: str) -> str:
    """在 5G 基站排障知识库中搜索。当用户询问故障原因、排查方法时使用。"""
    try:
        embeddings = OpenAIEmbeddings(
            model="text-embedding-v3",
            api_key=os.getenv("DASHSCOPE_API_KEY"),
            base_url=os.getenv("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
            check_embedding_ctx_length=False,
            chunk_size=10,
        )
        kb_path = Path(__file__).parent / "faiss_index"
        if not kb_path.exists():
            kb_path = Path(__file__).parent.parent / "12-FAISS向量库/faiss_index"
        vectorstore = FAISS.load_local(
            str(kb_path), embeddings, allow_dangerous_deserialization=True,
        )
        docs = vectorstore.similarity_search_with_relevance_scores(query, k=3)
        if not docs or docs[0][1] < 0.5:
            return "知识库中未找到高度相关内容。"
        parts = []
        for doc, score in docs:
            source = doc.metadata.get("source", "未知来源")
            parts.append(f"[来源: {source}] [相似度: {score:.2f}]\n{doc.page_content[:300]}")
        return "\n\n---\n".join(parts)
    except Exception as e:
        return f"知识库检索失败：{e}"


# ── 工具 5：SQL 智能问数（Day 2 产物）──
# SQLite 内存库延迟初始化
_sql_db: sqlite3.Connection = None


def _get_sql_db() -> sqlite3.Connection:
    global _sql_db
    if _sql_db is not None:
        return _sql_db
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE devices (device_id TEXT PRIMARY KEY, model TEXT, vendor TEXT,
            site TEXT, type TEXT, status TEXT, ip TEXT, online_date TEXT);
        CREATE TABLE alarms (alarm_id TEXT PRIMARY KEY, device_id TEXT, type TEXT,
            severity TEXT, time TEXT, description TEXT);
    """)
    devices_file = Path(__file__).parent / "data" / "devices.json"
    if not devices_file.exists():
        devices_file = Path(__file__).parent.parent / "04-平台搭建/data/devices.json"
    with open(devices_file, encoding="utf-8") as f:
        devices = json.load(f)
    for d in devices:
        conn.execute(
            "INSERT INTO devices VALUES (?,?,?,?,?,?,?,?)",
            (d["device_id"], d["model"], d["vendor"], d["site"],
             d["type"], d["status"], d["ip"], d["online_date"])
        )
        for a in d.get("alarms", []):
            try:
                conn.execute(
                    "INSERT INTO alarms VALUES (?,?,?,?,?,?)",
                    (a["alarm_id"], d["device_id"], a["type"],
                     a["severity"], a["time"], a["description"])
                )
            except sqlite3.IntegrityError:
                pass
    conn.commit()
    _sql_db = conn
    return conn


@tool
def query_devices_sql(question: str) -> str:
    """用自然语言查询设备数据库。统计/分组/筛选类问题使用。"""
    schema = """
表 devices: device_id, model, vendor, site, type, status, ip, online_date
表 alarms: alarm_id, device_id, type, severity, time, description
status: running/alarm/maintenance | severity: P0/P1/P2/P3 | vendor: 华为/中兴/爱立信/诺基亚
"""
    sql_llm = ChatOpenAI(model=MODEL, temperature=0, api_key=API_KEY, base_url=API_BASE)
    resp = sql_llm.invoke(
        f"""根据表结构和用户问题生成一条 SQLite SELECT 语句。只输出 SQL，一行。\n\n{schema}\n\n用户问题：{question}\n\nSELECT"""
    )
    sql = "SELECT " + resp.content.strip().removeprefix("SELECT ").removesuffix(";")
    for prefix in ["```sql", "```"]:
        if prefix in sql:
            sql = sql.split(prefix)[1].split("```")[0].strip()

    if not sql.strip().upper().startswith("SELECT"):
        return f"仅支持 SELECT 查询"

    try:
        conn = _get_sql_db()
        cursor = conn.execute(sql)
        cols = [d[0] for d in cursor.description]
        rows = cursor.fetchall()
        if not rows:
            return f"无匹配数据。SQL: {sql}"
        lines = [f"SQL: {sql}", f"结果（{len(rows)} 行）："]
        for row in rows[:20]:
            lines.append("  " + " | ".join(f"{c}={row[c]}" for c in cols))
        return "\n".join(lines)
    except Exception as e:
        return f"SQL 执行失败：{e}\n生成的 SQL：{sql}"


# ══════════════════════════════════════════════════════════════
# 第三部分：构建四个处理 Agent
# ══════════════════════════════════════════════════════════════

# 四个通道共用的输出约束：模型默认爱在 markdown 里撑 emoji，课堂投屏时很吵
_OUTPUT_STYLE = "\n\n输出要求：不要使用 emoji 和装饰符号，用纯文本陈述。"


def _make_agent(tools: list, system_prompt: str) -> AgentExecutor:
    """建一个 tool-calling Agent

    为什么不用 create_react_agent：ReAct 靠文本提示词驱动，它要求
    agent_scratchpad 是一个字符串（Thought/Action/Observation 拼接），
    必须配字符串模板 PromptTemplate。而这里用的是 ChatPromptTemplate
    的 placeholder，它要求值是 message 列表 —— 两者撑不到一起，会报
    "agent_scratchpad should be a list of base messages, got str"。
    tool-calling agent 直接走模型原生的 function calling，不靠提示词
    解析，更可靠，也不需要在 prompt 里手写 {tools} / {tool_names}。
    """
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt + _OUTPUT_STYLE),
        ("human", "{input}"),
        ("placeholder", "{agent_scratchpad}"),
    ])
    agent = create_tool_calling_agent(llm, tools, prompt)
    return AgentExecutor(agent=agent, tools=tools, verbose=False, max_iterations=8, handle_parsing_errors=True)


# 诊断 Agent：查设备状态 + 告警
diagnose_agent = _make_agent([query_device, list_devices, get_alarms], """你是 5G 基站设备诊断助手。职责：查询设备状态、分析告警、判断严重程度。

步骤：
1. 先查设备详情（query_device）——拿到状态和告警列表
2. 如果有告警，查告警详情（get_alarms）
3. 综合判断：运行是否正常？告警是否需要立即处理？
4. 输出诊断结论（不要泛泛而谈，引用具体数据）""")

# 问数 Agent：统计、分组、趋势
query_data_agent = _make_agent([query_devices_sql], """你是 5G 基站数据分析助手。职责：统计设备数量、告警分布、厂商/站点对比、趋势分析。

用 query_devices_sql 工具把用户问题翻译为 SQL 查询数据库。
回答时结合数据给出结论，不要只输出原始表格。

提示：
- 需要分组统计时用 GROUP BY
- 需要排名时用 ORDER BY + LIMIT
- 涉及两个表时用 JOIN""")

# 排障 Agent：搜知识库 + 查设备
troubleshoot_agent = _make_agent([query_device, search_kb], """你是 5G 基站排障专家。职责：根据设备告警和知识库给出排查方案。

步骤：
1. 如果用户提到了具体设备，先 query_device 了解设备状态和告警
2. 用 search_kb 在排障知识库中搜索相关处理方法
3. 综合两者：设备实际情况 + 知识库建议 → 给出具体排查步骤

回答要求：
- 引用知识库文档来源
- 排查步骤具体到命令级别
- 标注每步预计耗时""")

# 通用对话通道：零工具，所以不用 Agent
# Agent 的价值在于"选工具 + 看结果 + 再决定"的循环。没工具就没循环，
# 套一层 AgentExecutor 只是白多一轮空转；而且给 create_tool_calling_agent
# 传空 tools 列表，bind_tools([]) 在部分 OpenAI 兼容网关上会直接报错。
# 一条 prompt | llm | StrOutputParser 的普通链就够了。
chat_prompt = ChatPromptTemplate.from_messages([
    ("system", """你是 5G 基站运维平台助手。你可以：

- 回答关于 5G 基站运维的通用问题
- 帮助用户了解平台功能
- 引导用户使用正确的表述来触发诊断、问数、排障功能

用户可能的问法示例：
- "帮我分析 DEV-0001 的告警"（诊断）
- "上个月有多少 P0 告警"（问数）
- "AAU5613 退服怎么排查"（排障）

回答简洁友好，不超过 100 字。""" + _OUTPUT_STYLE),
    ("human", "{input}"),
])
chat_chain = chat_prompt | llm | StrOutputParser()


# ══════════════════════════════════════════════════════════════
# 第四部分：RunnableBranch 路由
# ══════════════════════════════════════════════════════════════

def _build_input(intent: IntentResult, user_input: str) -> dict:
    """构造传递给各通道的输入"""
    inp = {"input": user_input}
    # 如果意图识别提取到了设备 ID 但用户没明确说，自动注入
    if intent.device_id and intent.device_id not in user_input:
        inp["input"] = f"用户问：{user_input}\n（涉及设备 {intent.device_id}）"
    return inp


def _format_reply(intent: str, agent_output: str) -> dict:
    """统一返回格式"""
    label_map = {
        "diagnose": "[诊断分析]",
        "query_data": "[数据查询]",
        "troubleshoot": "[排障建议]",
        "chat": "[助手回复]",
    }
    return {
        "intent": intent,
        "label": label_map.get(intent, "[回复]"),
        "reply": agent_output,
    }


# 路由链只建一次：RunnableBranch 本身无状态，每次请求重建是白花开销
router_chain = RunnableBranch(
    (lambda x: x["intent"] == "diagnose",
     (lambda x: diagnose_agent.invoke(x)["output"])),
    (lambda x: x["intent"] == "query_data",
     (lambda x: query_data_agent.invoke(x)["output"])),
    (lambda x: x["intent"] == "troubleshoot",
     (lambda x: troubleshoot_agent.invoke(x)["output"])),
    (lambda x: x["intent"] == "chat",
     (lambda x: chat_chain.invoke(x))),
    (lambda x: chat_chain.invoke(x)),  # 兜底：LLM 返回了四类之外的值时不致崩
)


def build_router():
    """保留给外部调用方的入口（如 3.8 的分发层）"""
    return router_chain


def route(user_input: str, verbose: bool = True) -> dict:
    """完整路由：意图识别 → 分发 → 执行 → 返回结果"""
    start = time.time()

    # 1) 意图识别
    intent = classify_intent(user_input)
    if verbose:
        print(f"意图: {intent.intent} | 设备: {intent.device_id or '无'} | 原因: {intent.reason}")

    # 2) 构造输入
    agent_input = _build_input(intent, user_input)

    # 3) 路由执行
    agent_input["intent"] = intent.intent
    output = router_chain.invoke(agent_input)

    elapsed = time.time() - start
    result = _format_reply(intent.intent, output)
    result["elapsed"] = round(elapsed, 2)

    return result


# ══════════════════════════════════════════════════════════════
# 第五部分：演示
# ══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 60)
    print("实验 3.1：意图识别 + 路由 Agent")
    print("=" * 60)

    # 四类意图各两条
    # 注意 query_data 的第一条："帮我看下华为有多少告警设备"。它带着"看下设备"
    # 的外壳，但要的是数量，属于统计 —— 原来这条被标成 diagnose，跑出来准确率
    # 永远是 7/8，学员会以为模型判错了，其实是标注错了。评测集的标注错误比模型
    # 错误更难发现，因为它伪装成模型的锅。
    TEST_CASES = [
        # (预期意图, 用户输入)
        ("diagnose", "DEV-0001 状态怎么样？有什么告警？"),
        ("diagnose", "DEV-0007 现在运行正常吗"),
        ("query_data", "帮我看下华为有多少告警设备"),
        ("query_data", "告警设备按厂商分组统计，每个厂商各多少台？"),
        ("troubleshoot", "AAU5613 SCTP 链路中断怎么排查？"),
        ("troubleshoot", "这个 P0 退服告警该怎么处理？查下知识库"),
        ("chat", "你好，你能帮我做什么？"),
        ("chat", "今天天气不错"),
    ]

    correct = 0
    total = 0
    for expected_intent, text in TEST_CASES:
        total += 1
        print(f"\n{'-'*40}")
        print(f"用户: {text}")
        print(f"预期意图: {expected_intent}")

        try:
            result = route(text, verbose=True)
            actual = result["intent"]
            status = "一致" if actual == expected_intent else f"不一致（预期 {expected_intent}）"
            print(f"结果: {status}")
            print(f"通道: {result['label']}")
            print(f"耗时: {result['elapsed']}s")
            print(f"回答: {result['reply'][:150]}...")
            if actual == expected_intent:
                correct += 1
        except Exception as e:
            print(f"错误: {type(e).__name__}: {e}")

    print(f"\n{'='*60}")
    print(f"意图识别准确率: {correct}/{total} ({correct/total*100:.0f}%)")
    print(f"{'='*60}")

    # 展示架构
    print(f"""
意图路由架构：

  用户输入 ──→ 意图识别（LLM 分类）──→ RunnableBranch
                                         │
                  ┌──────────────────────┼──────────────────────┐
                  ▼                      ▼                      ▼
            diagnose              query_data             troubleshoot
          查设备+告警              SQL统计              搜知识库+排障
                  │                      │                      │
                  └──────────────────────┴──────────────────────┘
                                         │
                                         ▼
                                   统一返回格式
""")

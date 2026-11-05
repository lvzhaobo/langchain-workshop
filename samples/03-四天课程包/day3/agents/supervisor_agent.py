"""Day3 Supervisor Agent — 中央调度 + 三个 Worker（检测/诊断/处置）

多智能体场景（真数据版）：
    detection  — 读 day1 真实对象数据（指标+事件），LLM 分析并定风险等级
    diagnosis  — 搜 day2 知识库（阈值/排障手册），LLM 结合检测结果定根因
    disposal   — LLM 按风险等级生成工单与处置步骤（P0 提示需人工审批 → 引出 HITL）
Worker 全部真调 LLM；Supervisor 看消息里的标记决定派谁 / FINISH。
"""
import os
from typing import Any, Literal
from dotenv import load_dotenv
load_dotenv()

from langgraph.graph import StateGraph, START, END, MessagesState
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from .tools import extract_object_id, format_object, get_object, search_knowledge

LLM = ChatOpenAI(
    model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
)

SUPERVISOR_PROMPT = """你是 Supervisor，调度三个 Worker 按顺序排查故障：
1. detection — 分析告警、判断风险等级（先做）
2. diagnosis — 根因分析（detection 完成后做）
3. disposal — 创建工单、执行处置（diagnosis 完成后做）
4. FINISH — 三个 Worker 都已执行过 → 结束

看 AI 消息里的 [检测结果]/[诊断结果]/[处置结果] 判断已执行哪些：
- 没 [检测结果] → 派 detection
- 有 [检测结果] 没 [诊断结果] → 派 diagnosis
- 有 [诊断结果] 没 [处置结果] → 派 disposal
- 三个都有 → FINISH

只输出一个词：detection / diagnosis / disposal / FINISH"""


def supervisor_node(state: MessagesState) -> dict[str, Any]:
    msgs = [SystemMessage(content=SUPERVISOR_PROMPT)] + state["messages"]
    response = LLM.invoke(msgs)
    return {"messages": [response]}


def _user_question(state: MessagesState) -> str:
    for m in state["messages"]:
        if isinstance(m, HumanMessage):
            return str(m.content)
    return ""


def _find_section(state: MessagesState, marker: str) -> str:
    """从对话历史里找某个 Worker 的产出（诊断要用检测结果，处置要用诊断结果）"""
    for m in state["messages"]:
        if isinstance(m, AIMessage) and marker in str(m.content or ""):
            return str(m.content)
    return ""


def detection_worker(state: MessagesState) -> dict[str, Any]:
    """检测：真读对象数据（HTTP 8081 优先 / 文件兜底），LLM 分析指标与事件"""
    q = _user_question(state)
    obj = get_object(extract_object_id(q) or "OBJ-0006")   # 未指明对象时用演示故障站
    if not obj:
        return {"messages": [AIMessage(content="[检测结果] 对象不存在，无法检测。风险等级 无")]}
    facts = format_object(obj)
    resp = LLM.invoke([HumanMessage(content=f"""你是 5G 基站检测工程师。以下是设备真实数据：

{facts}

判断阈值：收光低于 -28dBm 异常；温度高于 55°C 过热；驻波比高于 3.0 异常。
输出（不超过 120 字）：
[检测结果] 对象 {obj['id']}，异常指标与事件概括，风险等级 P0/P1/P2（有 P0 事件即 P0）""")])
    return {"messages": [resp]}   # 直接返回 LLM 消息，避免 stream_mode=messages 重复推送


def diagnosis_worker(state: MessagesState) -> dict[str, Any]:
    """诊断：真搜 day2 知识库，LLM 结合检测结果给根因（带来源）"""
    detect = _find_section(state, "[检测结果]")
    hits = search_knowledge(detect or _user_question(state))
    kb = "\n\n".join(f"《{h['src']}》{h['text']}" for h in hits) or "（知识库无相关内容）"
    resp = LLM.invoke([HumanMessage(content=f"""你是 5G 基站诊断专家。结合检测结果和知识库定位根因。

检测结果：
{detect}

知识库：
{kb}

输出（不超过 120 字）：
[诊断结果] 根因一句话（引用知识库来源文件名），置信度 高/中/低""")])
    return {"messages": [resp]}


def disposal_worker(state: MessagesState) -> dict[str, Any]:
    """处置：LLM 按风险等级生成工单与处置步骤"""
    detect = _find_section(state, "[检测结果]")
    diagnose = _find_section(state, "[诊断结果]")
    resp = LLM.invoke([HumanMessage(content=f"""你是 5G 基站运维处置专家。生成工单和处置方案。

检测结果：{detect}
诊断结果：{diagnose}

输出（不超过 150 字）：
[处置结果] 工单 WO-XXXXXXXX-XXX（自拟编号），处置步骤 2-3 条；若风险等级为 P0，末尾注明"高危操作需人工审批"。""")])
    return {"messages": [resp]}


def route_supervisor(state: MessagesState) -> Literal["detection", "diagnosis", "disposal", "__end__"]:
    last = str(state["messages"][-1].content).strip().lower()
    if "detection" in last: return "detection"
    elif "diagnosis" in last: return "diagnosis"
    elif "disposal" in last: return "disposal"
    return "__end__"


def build_supervisor(checkpointer=None):
    builder = StateGraph(MessagesState)
    for name, fn in [("supervisor", supervisor_node), ("detection", detection_worker),
                     ("diagnosis", diagnosis_worker), ("disposal", disposal_worker)]:
        builder.add_node(name, fn)
    builder.add_edge(START, "supervisor")
    builder.add_conditional_edges("supervisor", route_supervisor,
        {"detection": "detection", "diagnosis": "diagnosis", "disposal": "disposal", "__end__": END})
    for w in ["detection", "diagnosis", "disposal"]:
        builder.add_edge(w, "supervisor")
    return builder.compile(checkpointer=checkpointer)

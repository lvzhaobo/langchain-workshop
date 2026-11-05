"""LangGraph 多 Agent 流水线 — 三种协作模式对比

模式 1：串行流水线（detector → diagnoser → decider → executor）
模式 2：Supervisor 调度（中央 Agent 决定下一步调用谁）
模式 3：条件分支（根据诊断结果动态选择处置路径）

运行：python supervisor_pipeline.py [serial|supervisor|conditional|all]
依赖：pip install langgraph langchain langchain-openai requests
"""
import os
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))  # 自动读取课程根目录 .env

import json
import sys
import time
from pathlib import Path
from typing import TypedDict, Literal, Annotated, Any
import operator

import requests
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.graph import StateGraph, END

# ═══ 配置 ═══
BASE_URL = "http://localhost:8000"
API_KEY = os.getenv("AGENT_API_KEY", "REPLACE_ME_NO_KEY")
API_BASE = os.getenv("AGENT_API_BASE", "https://api.deepseek.com/v1")
MODEL = os.getenv("AGENT_MODEL", "deepseek-chat")

llm = ChatOpenAI(model=MODEL, temperature=0, api_key=API_KEY, base_url=API_BASE)


# ══════════════════════════════════════════════════════════════
# State 定义 — 四种模式共用
# ══════════════════════════════════════════════════════════════
class AgentState(TypedDict):
    # 输入
    user_input: str
    device_id: str

    # 各节点产出
    detect_result: str      # 检测：设备状态 + 告警列表
    diagnose_result: str    # 诊断：知识库搜索结果
    decide_result: str      # 决策：风险等级 + 处置策略
    execute_result: str     # 处置：最终建议/工单

    # 流程控制
    next_step: str           # "diagnose" / "decide" / "execute" / "finish"
    risk_level: str          # "high" / "medium" / "low"

    # 消息日志
    messages: Annotated[list, operator.add]


# ══════════════════════════════════════════════════════════════
# 工具函数 — 子 Agent 共用
# ══════════════════════════════════════════════════════════════

# 取数降级：HTTP 优先 → 本地快照兜底 → 明确失败。
# 多 Agent 流水线里这层特别重要：检测节点拿不到数据也不会报错，它会把
# "无法获取设备列表"当成分析材料往下传，诊断、决策、处置四个节点会基于
# 空数据逐层放大幻觉，最后产出一份格式完整、内容全编的处置方案。
DEVICES_FILE = Path(__file__).parent / "data" / "devices.json"
if not DEVICES_FILE.exists():
    DEVICES_FILE = Path(__file__).parent.parent / "04-平台搭建" / "data" / "devices.json"
_degraded = False


def _local_api(endpoint: str) -> dict[str, Any]:
    """平台不可达时，用 1.1 的 devices.json 在本地重放同构响应

    平台 API 读的就是这份文件，所以降级前后数据完全一致，
    不存在"两套演示结果对不上"的问题。
    """
    global _degraded
    try:
        devices = json.loads(DEVICES_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"error": "平台 API 不可达，本地快照也读不到"}
    _degraded = True

    path, _, query = endpoint.partition("?")
    params = dict(p.split("=", 1) for p in query.split("&") if "=" in p)

    if path.startswith("/devices/"):
        did = path[len("/devices/"):].split("/")[0]
        hit = next((d for d in devices if d["device_id"] == did), None)
        if path.endswith("/alarms"):
            alarms = hit.get("alarms", []) if hit else []
            return {"device_id": did, "alarms": alarms, "alarm_count": len(alarms)}
        return {"found": hit is not None, "device": hit} if hit else {"found": False}

    # /devices 列表：把平台的筛选逻辑重放一遍
    if "status" in params:
        devices = [d for d in devices if d["status"] == params["status"]]
    if "vendor" in params:
        devices = [d for d in devices if params["vendor"] in d["vendor"]]
    total = len(devices)
    return {"devices": devices[:int(params.get("limit", 20))], "total": total}


def _degraded_note() -> str:
    return "\n（数据来源：本地快照，平台 API 未启动）" if _degraded else ""


def _call_device_api(endpoint: str) -> dict[str, Any]:
    try:
        resp = requests.get(f"{BASE_URL}{endpoint}", timeout=5)
        return resp.json()
    except Exception:
        return _local_api(endpoint)


def fetch_device_info(device_id: str) -> str:
    """获取设备详情"""
    data = _call_device_api(f"/devices/{device_id}")
    if data.get("error"):
        return f"取数失败：{data['error']}。请勿基于推测作答，直接说明数据不可用。"
    if not data.get("found"):
        return f"设备 {device_id} 不存在"
    d = data["device"]
    alarms = d.get("alarms", [])
    alarm_text = "\n".join([
        f"  [{a['severity']}] {a['type']}: {a['description']}"
        for a in alarms
    ]) if alarms else "无告警"
    return (
        f"设备 {device_id}：{d['vendor']} {d['model']}，{d['type']}，"
        f"站点 {d['site']}，状态 {d['status']}，IP {d['ip']}。"
        f"告警（{len(alarms)}条）：\n{alarm_text}" + _degraded_note()
    )


def search_knowledge_base(query: str) -> str:
    """搜索排障知识库"""
    kb_path = Path(__file__).parent / "faiss_index"
    if not kb_path.exists():
        kb_path = Path(__file__).parent.parent / "12-FAISS向量库/faiss_index"
    if not kb_path.exists():
        return "[模拟] 知识库未就绪，请先完成实验 2.1"
    try:
        embeddings = OpenAIEmbeddings(
            model="text-embedding-v3",
            api_key=os.getenv("DASHSCOPE_API_KEY"),
            base_url=os.getenv("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
            check_embedding_ctx_length=False,
            chunk_size=10,
        )
        vectorstore = FAISS.load_local(str(kb_path), embeddings, allow_dangerous_deserialization=True)
        docs = vectorstore.similarity_search_with_relevance_scores(query, k=3)
        if not docs or docs[0][1] < 0.5:
            return "知识库未找到高度相关内容。"
        parts = []
        for doc, score in docs:
            source = doc.metadata.get("source", "未知")
            parts.append(f"[{source}] (相似度:{score:.2f})\n{doc.page_content[:300]}")
        return "\n\n---\n".join(parts)
    except Exception as e:
        return f"知识库检索失败：{e}"


# ══════════════════════════════════════════════════════════════
# LLM 调用封装 — 避免重复代码
# ══════════════════════════════════════════════════════════════
def _ask(prompt: str) -> str:
    """向 LLM 提问并返回文本"""
    resp = llm.invoke([HumanMessage(content=prompt)])
    return resp.content


# ══════════════════════════════════════════════════════════════
# 四个子 Agent 节点 — 三种模式复用相同的节点实现
# ══════════════════════════════════════════════════════════════

def detector_node(state: AgentState) -> AgentState:
    """检测节点：查设备状态 + 告警"""
    device_id = state.get("device_id", "")
    user_input = state.get("user_input", "")

    # 从用户输入中提取可能的设备 ID
    if not device_id:
        for word in user_input.split():
            if word.upper().startswith("DEV-"):
                device_id = word.upper()
                break

    if device_id:
        device_info = fetch_device_info(device_id)
    else:
        device_info = "用户未指定设备ID，以下是通用的告警设备概览：\n"
        data = _call_device_api("/devices?status=alarm&limit=5")
        if data.get("error"):
            device_info += "无法获取设备列表，请勿基于推测作答"
        else:
            for d in data.get("devices", []):
                alarms = len(d.get("alarms", []))
                device_info += f"  {d['device_id']} | {d['vendor']} {d['model']} | {d['site']} | 告警{alarms}条\n"
            device_info += _degraded_note()

    analysis = _ask(f"""你是 5G 基站检测工程师。分析以下设备信息并输出：

设备信息：
{device_info}

输出格式：
【设备状态】：一句话总结
【告警汇总】：列出所有告警的级别和类型
【初步判断】：这是硬件故障/配置错误/传输问题/其他？理由是什么
【需要进一步诊断的问题】：列出 1-3 个需要深入排查的方向""")

    return {
        **state,
        "detect_result": analysis,
        "device_id": device_id,
        "messages": [AIMessage(content=f"[检测Agent] {analysis[:200]}...")],
    }


def diagnoser_node(state: AgentState) -> AgentState:
    """诊断节点：搜索知识库 + 定位根因"""
    detect = state.get("detect_result", "")
    user_input = state.get("user_input", "")

    # 从检测结果中提取关键词用于知识库搜索
    kb_result = search_knowledge_base(user_input)
    if "[模拟]" in kb_result:
        kb_result = "（知识库未就绪，基于通用排障知识分析）\n1. 检查物理链路：光模块光功率、光纤连接\n2. 检查配置：SCTP端点/路由/VLAN配置\n3. 检查负载：带宽利用率、CPU温度"

    diagnosis = _ask(f"""你是 5G 基站诊断专家。基于检测结果和知识库，定位根因。

检测结果：
{detect[:800]}

知识库搜索结果：
{kb_result[:1000]}

输出格式：
【最可能的根因】：一句话 + 置信度（高/中/低）
【判断依据】：引用检测结果或知识库中的具体信息
【其他可能原因】：列出 1-2 个备选根因
【建议的处置方向】：不需要详细步骤，只说方向""")

    return {
        **state,
        "diagnose_result": diagnosis,
        "messages": [AIMessage(content=f"[诊断Agent] {diagnosis[:200]}...")],
    }


def decider_node(state: AgentState) -> AgentState:
    """决策节点：评估风险等级，决定处置策略"""
    detect = state.get("detect_result", "")
    diagnose = state.get("diagnose_result", "")

    decision = _ask(f"""你是 5G 基站运维决策专家。根据检测和诊断结果，做两件事：
1. 评估风险等级（high/medium/low）
2. 决定处置策略

检测结果：{detect[:500]}
诊断结果：{diagnose[:500]}

输出格式：
【风险等级】：high / medium / low
【等级依据】：一句话
【处置策略】：具体说明怎么处理
【是否需要人工审批】：是/否""")

    # 从决策中提取风险等级
    risk = "medium"
    if "high" in decision.lower().split("风险等级")[1][:30] if "风险等级" in decision.lower() else "":
        risk = "high"
    elif "low" in decision.lower():
        risk = "low"

    # 直接匹配关键词
    if "【风险等级】：high" in decision or "【风险等级】： high" in decision:
        risk = "high"
    elif "【风险等级】：low" in decision or "【风险等级】： low" in decision:
        risk = "low"

    return {
        **state,
        "decide_result": decision,
        "risk_level": risk,
        "next_step": "execute",
        "messages": [AIMessage(content=f"[决策Agent] 风险等级: {risk}")],
    }


def executor_node(state: AgentState) -> AgentState:
    """处置节点：生成最终排查步骤/建议"""
    detect = state.get("detect_result", "")
    diagnose = state.get("diagnose_result", "")
    decide = state.get("decide_result", "")
    risk = state.get("risk_level", "medium")

    urgency = "紧急！需立即处理" if risk == "high" else ("需在 30 分钟内处理" if risk == "medium" else "例行处理")

    execution = _ask(f"""你是 5G 基站排障执行专家。综合所有前置分析，给出可直接操作的处置方案。

告警等级：{urgency}

检测结果：{detect[:400]}
诊断结果：{diagnose[:400]}
决策结果：{decide[:400]}

输出格式：
【处置方案】（{urgency}）
【步骤1】（预计耗时）具体操作命令
【步骤2】（预计耗时）具体操作命令
【步骤3】（预计耗时）验证方法
【回滚方案】如果以上步骤无效，怎么做""")

    return {
        **state,
        "execute_result": execution,
        "next_step": "finish",
        "messages": [AIMessage(content=f"[处置Agent] 方案已生成")],
    }


# ══════════════════════════════════════════════════════════════
# 模式一：串行流水线 — 固定顺序，无条件分支
# ══════════════════════════════════════════════════════════════

def build_serial_pipeline():
    """detector → diagnoser → decider → executor，固定顺序"""
    graph = StateGraph(AgentState)
    graph.add_node("detector", detector_node)
    graph.add_node("diagnoser", diagnoser_node)
    graph.add_node("decider", decider_node)
    graph.add_node("executor", executor_node)

    # 固定串行
    graph.set_entry_point("detector")
    graph.add_edge("detector", "diagnoser")
    graph.add_edge("diagnoser", "decider")
    graph.add_edge("decider", "executor")
    graph.add_edge("executor", END)

    return graph.compile()


# ══════════════════════════════════════════════════════════════
# 模式二：Supervisor 调度 — 中央 Agent 决定下一步
# ══════════════════════════════════════════════════════════════

def supervisor_router(state: AgentState) -> Literal["detector", "diagnoser", "decider", "executor", "__end__"]:
    """Supervisor 决定下一步调用谁"""
    step = state.get("next_step", "")

    # 初始状态 → 先检测
    if not state.get("detect_result"):
        return "detector"

    # 检测完成 → 诊断
    if not state.get("diagnose_result"):
        return "diagnoser"

    # 诊断完成 → 决策
    if not state.get("decide_result"):
        return "decider"

    # 决策完成 → 处置
    if not state.get("execute_result"):
        return "executor"

    return "__end__"


def build_supervisor_pipeline():
    """Supervisor 模式：中央路由函数决定每一步的走向"""
    graph = StateGraph(AgentState)
    graph.add_node("detector", detector_node)
    graph.add_node("diagnoser", diagnoser_node)
    graph.add_node("decider", decider_node)
    graph.add_node("executor", executor_node)

    graph.set_entry_point("detector")

    # 每个节点完成后回到 supervisor，由 supervisor 决定下一个
    graph.add_conditional_edges("detector", supervisor_router, {
        "diagnoser": "diagnoser",
        "__end__": END,
    })
    graph.add_conditional_edges("diagnoser", supervisor_router, {
        "decider": "decider",
        "__end__": END,
    })
    graph.add_conditional_edges("decider", supervisor_router, {
        "executor": "executor",
        "__end__": END,
    })
    graph.add_edge("executor", END)

    return graph.compile()


# ══════════════════════════════════════════════════════════════
# 模式三：条件分支 — 根据诊断结果动态选择处置路径
# ══════════════════════════════════════════════════════════════

def executor_high_risk(state: AgentState) -> AgentState:
    """高风险执行器——调用标准的 executor 但追加紧急提示"""
    result = executor_node(state)
    result["execute_result"] = "[高风险] 处置方案（建议人工审批后执行）：\n\n" + result["execute_result"]
    return result


def executor_low_risk(state: AgentState) -> AgentState:
    """低风险执行器——简化版处理"""
    return {
        **state,
        "execute_result": f"设备 {state.get('device_id', '未知')} 风险等级低，建议例行巡检即可。\n主要关注点：{state.get('diagnose_result', '')[:200]}",
        "next_step": "finish",
        "messages": [AIMessage(content="[低风险处置] 例行巡检")],
    }


def risk_router(state: AgentState) -> Literal["executor_high", "executor_normal", "executor_low"]:
    """根据风险等级动态路由到不同执行器"""
    risk = state.get("risk_level", "medium")
    if risk == "high":
        return "executor_high"
    elif risk == "low":
        return "executor_low"
    return "executor_normal"


def build_conditional_pipeline():
    """条件分支模式：decider 之后根据风险等级走不同的 executor"""
    graph = StateGraph(AgentState)
    graph.add_node("detector", detector_node)
    graph.add_node("diagnoser", diagnoser_node)
    graph.add_node("decider", decider_node)
    graph.add_node("executor_normal", executor_node)
    graph.add_node("executor_high", executor_high_risk)
    graph.add_node("executor_low", executor_low_risk)

    graph.set_entry_point("detector")
    graph.add_edge("detector", "diagnoser")
    graph.add_edge("diagnoser", "decider")

    # 关键：decider 之后不是固定边，而是条件路由
    graph.add_conditional_edges("decider", risk_router, {
        "executor_high": "executor_high",
        "executor_normal": "executor_normal",
        "executor_low": "executor_low",
    })

    graph.add_edge("executor_high", END)
    graph.add_edge("executor_normal", END)
    graph.add_edge("executor_low", END)

    return graph.compile()


# ══════════════════════════════════════════════════════════════
# 统一入口 + 演示
# ══════════════════════════════════════════════════════════════

def run_pipeline(mode: str, user_input: str, device_id: str = "") -> dict:
    """运行指定模式的流水线"""
    modes = {
        "serial": build_serial_pipeline,
        "supervisor": build_supervisor_pipeline,
        "conditional": build_conditional_pipeline,
    }
    if mode not in modes:
        raise ValueError(f"未知模式: {mode}。可选: serial / supervisor / conditional")

    app = modes[mode]()
    initial_state = {
        "user_input": user_input,
        "device_id": device_id,
        "detect_result": "",
        "diagnose_result": "",
        "decide_result": "",
        "execute_result": "",
        "next_step": "",
        "risk_level": "medium",
        "messages": [],
    }

    start = time.time()
    result = app.invoke(initial_state)
    elapsed = time.time() - start

    return {
        "mode": mode,
        "elapsed": round(elapsed, 2),
        "detect": result.get("detect_result", ""),
        "diagnose": result.get("diagnose_result", ""),
        "decide": result.get("decide_result", ""),
        "execute": result.get("execute_result", ""),
        "risk_level": result.get("risk_level", "medium"),
        "steps": len(result.get("messages", [])),
    }


if __name__ == "__main__":
    MODE = sys.argv[1] if len(sys.argv) > 1 else "all"
    TASK = "DEV-0001 SCTP 链路中断导致退服，帮我排查并给出处置方案"
    DEVICE = "DEV-0001"

    print("=" * 60)
    print("实验 3.2：LangGraph 多 Agent 流水线 — 三种协作模式")
    print("=" * 60)
    print(f"\n任务：{TASK}")

    if MODE == "all":
        to_run = ["serial", "supervisor", "conditional"]
    else:
        to_run = [MODE]

    all_results = {}
    for mode in to_run:
        print(f"\n{'#'*50}")
        print(f"# 模式：{mode}")
        print(f"{'#'*50}")

        result = run_pipeline(mode, TASK, DEVICE)
        all_results[mode] = result

        print(f"\n耗时: {result['elapsed']}s")
        print(f"节点执行步数: {result['steps']}")
        print(f"风险等级: {result['risk_level']}")

        print(f"\n{'─'*40}")
        print("【检测结果】")
        print(result["detect"][:250])

        print(f"\n{'─'*40}")
        print("【诊断结果】")
        print(result["diagnose"][:250])

        print(f"\n{'─'*40}")
        print("【决策结果】")
        print(result["decide"][:200])

        print(f"\n{'─'*40}")
        print("【最终处置】")
        print(result["execute"][:300])

    # ── 三种模式对比总结 ──
    if len(all_results) >= 2:
        print(f"\n\n{'='*60}")
        print("三种协作模式对比")
        print(f"{'='*60}")
        print(f"{'模式':<16} {'耗时':>8} {'风险':>6} {'节点步数':>8} {'特点'}")
        print(f"{'-'*60}")
        for mode, r in all_results.items():
            feature = {
                "serial": "固定顺序，无条件，最简单",
                "supervisor": "中央路由，每步可跳转，最灵活",
                "conditional": "根据风险分流，不同情况不同处理",
            }.get(mode, "")
            print(f"{mode:<16} {r['elapsed']:>7.1f}s {r['risk_level']:>6} {r['steps']:>8}  {feature}")

        print(f"\n选型建议：")
        print(f"  流程固定 → serial（KISS 原则）")
        print(f"  需要动态调度 → supervisor（如 3.1 的意图路由升级版）")
        print(f"  根据结果分流 → conditional（如 1.7 RunnableBranch 的 StateGraph 版）")

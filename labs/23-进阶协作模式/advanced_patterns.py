"""LangGraph 进阶协作模式 — Map-Reduce / Iterative Loop / Peer Mesh

三种模式复用同一套 Agent 节点（detector/diagnoser/decider/executor），
只改 Graph 的边连接方式。体现 LangGraph 核心优势：Agent 不变，编排变。

运行：python advanced_patterns.py [mapreduce|loop|mesh|all]
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
from langgraph.constants import Send

# ═══ 配置 ═══
BASE_URL = "http://localhost:8000"
API_KEY = os.getenv("AGENT_API_KEY", "REPLACE_ME_NO_KEY")
API_BASE = os.getenv("AGENT_API_BASE", "https://api.deepseek.com/v1")
MODEL = os.getenv("AGENT_MODEL", "deepseek-chat")

llm = ChatOpenAI(model=MODEL, temperature=0, api_key=API_KEY, base_url=API_BASE)


# ══════════════════════════════════════════════════════════════
# State 定义 — 在 3.2 基础 State 上加字段
# ══════════════════════════════════════════════════════════════
class AgentState(TypedDict, total=False):
    user_input: str
    device_id: str

    # 各节点产出
    detect_result: str
    diagnose_result: str
    decide_result: str
    execute_result: str

    # Map-Reduce 用
    sub_tasks: list                     # Splitter 拆出的子任务列表
    parallel_results: Annotated[list, operator.add]  # 各 Worker 的并行结果汇总

    # Iterative Loop 用
    loop_count: int                     # 当前循环次数
    confidence_score: float             # 诊断置信度
    history_log: Annotated[list, operator.add]  # 历史诊断记录（用于循环对比）

    # 流程控制
    next_step: str
    risk_level: str
    messages: Annotated[list, operator.add]


# ══════════════════════════════════════════════════════════════
# 共享工具函数（复用 3.2 的实现，精简版）
# ══════════════════════════════════════════════════════════════
# 取数降级：HTTP 优先 → 本地快照兜底 → 明确失败（同 3.2）
DEVICES_FILE = Path(__file__).parent / "data" / "devices.json"
if not DEVICES_FILE.exists():
    DEVICES_FILE = Path(__file__).parent.parent / "04-平台搭建" / "data" / "devices.json"
_degraded = False


def _local_api(endpoint: str) -> dict[str, Any]:
    """平台不可达时用 1.1 的 devices.json 重放同构响应"""
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

    if "status" in params:
        devices = [d for d in devices if d["status"] == params["status"]]
    if "vendor" in params:
        devices = [d for d in devices if params["vendor"] in d["vendor"]]
    return {"devices": devices[:int(params.get("limit", 20))], "total": len(devices)}


def _degraded_note() -> str:
    return "\n（数据来源：本地快照，平台 API 未启动）" if _degraded else ""


def _call_api(endpoint: str) -> dict[str, Any]:
    try:
        return requests.get(f"{BASE_URL}{endpoint}", timeout=5).json()
    except Exception:
        return _local_api(endpoint)


def fetch_device_info(device_id: str) -> str:
    data = _call_api(f"/devices/{device_id}")
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
    return (f"设备 {device_id}：{d['vendor']} {d['model']}，站点 {d['site']}，"
            f"状态 {d['status']}。告警({len(alarms)}条)：\n{alarm_text}" + _degraded_note())


def search_knowledge_base(query: str) -> str:
    kb_path = Path(__file__).parent / "faiss_index"
    if not kb_path.exists():
        kb_path = Path(__file__).parent.parent / "12-FAISS向量库/faiss_index"
    if not kb_path.exists():
        return "[模拟] 知识库未就绪。基于通用排障知识：1.检查物理链路 2.检查配置 3.检查负载"
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
            return "未找到高度相关内容。建议：扩大搜索关键词或联系二线专家。"
        parts = []
        for doc, score in docs:
            parts.append(f"[{doc.metadata.get('source','?')}] (置信:{score:.2f})\n{doc.page_content[:300]}")
        return "\n---\n".join(parts)
    except Exception as e:
        return f"知识库检索失败：{e}"


def _ask(prompt: str) -> str:
    resp = llm.invoke([HumanMessage(content=prompt)])
    return resp.content


def fetch_historical_alarms(device_id: str) -> str:
    """查询设备历史告警记录（从平台 API）"""
    data = _call_api(f"/devices/{device_id}/alarms")
    if data.get("error"):
        return f"取数失败：{data['error']}。请勿基于推测作答。"
    alarms = data.get("alarms", [])
    if not alarms:
        return "该设备当前无告警记录"
    lines = [f"{device_id} 历史告警（{len(alarms)}条）："]
    for a in alarms:
        lines.append(f"  [{a['severity']}] {a['type']}: {a['description']} ({a.get('time','')})")
    return "\n".join(lines) + _degraded_note()


# ══════════════════════════════════════════════════════════════
# 共享 Agent 节点 — 三种模式复用
# ══════════════════════════════════════════════════════════════

def detector_node(state: AgentState) -> AgentState:
    user_input = state.get("user_input", "")
    device_id = state.get("device_id", "")
    if not device_id:
        for word in user_input.split():
            if word.upper().startswith("DEV-"):
                device_id = word.upper()
                break

    device_info = fetch_device_info(device_id) if device_id else "未指定设备"
    analysis = _ask(f"""你是 5G 基站检测工程师。分析设备信息。

设备数据：{device_info}

输出：【设备状态】一句话 / 【告警汇总】级别+类型 / 【初步判断】故障类型+理由""")
    return {**state, "detect_result": analysis, "device_id": device_id,
            "messages": [AIMessage(content=f"[检测] {analysis[:150]}...")]}


def diagnoser_node(state: AgentState) -> AgentState:
    detect = state.get("detect_result", "")
    user_input = state.get("user_input", "")
    kb_result = search_knowledge_base(user_input)

    diagnosis = _ask(f"""你是 5G 诊断专家。定位根因。

检测结果：{detect[:600]}
知识库：{kb_result[:800]}

输出：
【最可能根因】+ 置信度(0-1)
【判断依据】
【备选原因】""")
    return {**state, "diagnose_result": diagnosis,
            "messages": [AIMessage(content=f"[诊断] {diagnosis[:150]}...")]}


def decider_node(state: AgentState) -> AgentState:
    detect = state.get("detect_result", "")
    diagnose = state.get("diagnose_result", "")
    decision = _ask(f"""你是运维决策专家。评估风险+决定策略。

检测：{detect[:400]}
诊断：{diagnose[:400]}

输出：【风险等级】high/medium/low / 【等级依据】 / 【处置策略】 / 【是否需人工审批】""")

    risk = "medium"
    for level in ["high", "medium", "low"]:
        if f"【风险等级】{level}" in decision or f"【风险等级】 {level}" in decision:
            risk = level
            break
    return {**state, "decide_result": decision, "risk_level": risk,
            "next_step": "execute",
            "messages": [AIMessage(content=f"[决策] 风险={risk}")]}


def executor_node(state: AgentState) -> AgentState:
    detect = state.get("detect_result", "")
    diagnose = state.get("diagnose_result", "")
    decide = state.get("decide_result", "")
    risk = state.get("risk_level", "medium")
    urgency = "立即处理" if risk == "high" else ("30分钟内" if risk == "medium" else "例行")

    execution = _ask(f"""你是排障执行专家。输出可直接操作的处置方案（{urgency}）。

检测：{detect[:300]}
诊断：{diagnose[:300]}
决策：{decide[:300]}

输出：【处置方案】/ 【步骤1】命令+预计耗时 / 【步骤2】... / 【回滚方案】""")
    return {**state, "execute_result": execution,
            "messages": [AIMessage(content=f"[处置] 方案已生成")]}


# ══════════════════════════════════════════════════════════════
# 模式一：Map-Reduce（并行扇出 → 汇总）
# ══════════════════════════════════════════════════════════════

def splitter_node(state: AgentState) -> AgentState:
    """Splitter：把用户问题拆成多个独立子任务，每个子任务可以并行执行"""
    user_input = state.get("user_input", "")
    device_id = state.get("device_id", "")

    # 模拟拆任务——生产环境用 LLM 动态拆分
    tasks = [
        {"id": "check-device", "label": "查设备状态", "query": f"查询设备 {device_id} 的运行状态和告警信息"},
        {"id": "search-kb", "label": "搜知识库", "query": user_input},
        {"id": "check-history", "label": "查历史告警", "query": f"查询设备 {device_id} 的历史告警记录"},
    ]
    return {**state, "sub_tasks": tasks, "messages": [AIMessage(content=f"[Splitter] 拆为 {len(tasks)} 个子任务")]}


def map_worker(state: AgentState) -> AgentState:
    """Map Worker：执行单个子任务"""
    task = state.get("current_task", {})
    task_id = task.get("id", "unknown")
    query = task.get("query", "")

    result = ""
    if task_id == "check-device":
        result = fetch_device_info(state.get("device_id", ""))
    elif task_id == "search-kb":
        result = search_knowledge_base(query)
    elif task_id == "check-history":
        result = fetch_historical_alarms(state.get("device_id", ""))

    summary = _ask(f"""你是排障分析员。总结以下信息的关键发现（不超过 100 字）。

任务：{task.get('label', '')}
{query}

执行结果：
{result[:500]}

关键发现：""")

    return {"parallel_results": [{
        "task_id": task_id,
        "label": task.get("label", ""),
        "result": result[:300],
        "summary": summary,
    }]}


def reducer_node(state: AgentState) -> AgentState:
    """Reducer：汇总所有并行 Worker 的结果，生成综合分析"""
    parallel_results = state.get("parallel_results", [])
    parts = []
    for r in parallel_results:
        parts.append(f"## {r['label']}\n{r['summary']}\n详情: {r['result'][:200]}")

    combined = "\n\n".join(parts)
    synthesis = _ask(f"""你是 5G 排障综合分析专家。以下是从三个维度并行收集的信息，综合输出诊断方案。

{combined}

输出：
【综合判断】根因是什么？
【关键证据】各维度的证据链
【处置优先级】先做什么、后做什么""")

    return {**state, "execute_result": synthesis,
            "messages": [AIMessage(content=f"[Reducer] 三路结果已汇总")]}


def continue_to_workers(state: AgentState) -> list:
    """返回 Send 列表——LangGraph 自动并行执行所有 Worker"""
    tasks = state.get("sub_tasks", [])
    return [Send("map_worker", {**state, "current_task": t}) for t in tasks]


def build_mapreduce_pipeline():
    graph = StateGraph(AgentState)
    graph.add_node("splitter", splitter_node)
    graph.add_node("map_worker", map_worker)
    graph.add_node("reducer", reducer_node)

    graph.set_entry_point("splitter")
    graph.add_conditional_edges("splitter", continue_to_workers, ["map_worker"])
    graph.add_edge("map_worker", "reducer")
    graph.add_edge("reducer", END)

    return graph.compile()


# ══════════════════════════════════════════════════════════════
# 模式二：Iterative Loop（置信度不达标 → 回退 → 重新检测）
# ══════════════════════════════════════════════════════════════

MAX_LOOPS = 3
CONFIDENCE_THRESHOLD = 0.7


def confidence_checker(state: AgentState) -> AgentState:
    """从诊断结果中提取置信度分数"""
    diagnose = state.get("diagnose_result", "")
    loop = state.get("loop_count", 0)

    # LLM 提取置信度
    score_text = _ask(f"""从以下诊断结论中提取置信度分数（0-1之间的小数）。只输出数字。

{diagnose}
置信度：""")
    try:
        score = float(score_text.strip())
        score = max(0.0, min(1.0, score))
    except ValueError:
        score = 0.5

    return {
        **state,
        "confidence_score": score,
        "loop_count": loop + 1,
        "history_log": [f"第{loop+1}轮诊断：置信度{score:.2f} | {diagnose[:100]}"],
    }


def loop_router(state: AgentState) -> Literal["detector", "decider", "__end__"]:
    """判断是继续循环还是往下走"""
    score = state.get("confidence_score", 0)
    loops = state.get("loop_count", 0)

    if score >= CONFIDENCE_THRESHOLD:
        return "decider"
    if loops >= MAX_LOOPS:
        # 达到最大循环次数，强制继续
        return "decider"
    # 置信度不够，回退到 detector 重新检测
    return "detector"


def build_loop_pipeline():
    graph = StateGraph(AgentState)
    graph.add_node("detector", detector_node)
    graph.add_node("diagnoser", diagnoser_node)
    graph.add_node("checker", confidence_checker)
    graph.add_node("decider", decider_node)
    graph.add_node("executor", executor_node)

    graph.set_entry_point("detector")
    graph.add_edge("detector", "diagnoser")
    graph.add_edge("diagnoser", "checker")

    # 关键：checker 之后不是固定边，而是回退路由
    graph.add_conditional_edges("checker", loop_router, {
        "decider": "decider",
        "detector": "detector",  # ← 回退！
        "__end__": END,
    })

    graph.add_edge("decider", "executor")
    graph.add_edge("executor", END)

    return graph.compile()


# ══════════════════════════════════════════════════════════════
# 模式三：Peer Mesh（去中心化，Agent 互相调用）
# ══════════════════════════════════════════════════════════════

def peer_router(state: AgentState) -> Literal["detector", "diagnoser", "decider", "executor", "__end__"]:
    """Peer Mesh 路由：没有中央 Supervisor，每个 Agent 完成后自己决定下一个

    简化版实现：用 run_manager（LLM）模拟 Agent 之间的相互调用决策
    """
    msgs = state.get("messages", [])
    step_count = len([m for m in msgs if "[" in getattr(m, "content", "")])

    # 按顺序推进，但允许回退
    if not state.get("detect_result"):
        return "detector"

    if not state.get("diagnose_result"):
        return "diagnoser"

    # Peer 特色——诊断完成后，Agent 可以"要求其他 Agent 帮忙"
    # 这里模拟：诊断结果不够详细时，请求 detector 补充数据
    diagnose = state.get("diagnose_result", "")
    if step_count <= 3 and ("不确定" in diagnose or "需要更多信息" in diagnose):
        return "detector"  # Peer 请求：detector 你能再查一下吗？

    if not state.get("decide_result"):
        return "decider"
    if not state.get("execute_result"):
        return "executor"

    return "__end__"


def build_mesh_pipeline():
    """Peer Mesh：Agent 之间可以互相调用，不经过中央调度器"""
    graph = StateGraph(AgentState)
    graph.add_node("detector", detector_node)
    graph.add_node("diagnoser", diagnoser_node)
    graph.add_node("decider", decider_node)
    graph.add_node("executor", executor_node)

    graph.set_entry_point("detector")

    # 每个节点完成后 → 自己决定下一个（通过 peer_router 模拟）
    graph.add_conditional_edges("detector", peer_router, {
        "diagnoser": "diagnoser",
        "decider": "decider",
        "executor": "executor",
        "__end__": END,
    })
    graph.add_conditional_edges("diagnoser", peer_router, {
        "detector": "detector",  # ← 可以回退
        "decider": "decider",
        "executor": "executor",
        "__end__": END,
    })
    graph.add_conditional_edges("decider", peer_router, {
        "diagnoser": "diagnoser",  # ← 可以让 diagnoser 重做
        "executor": "executor",
        "__end__": END,
    })
    graph.add_conditional_edges("executor", peer_router, {
        "detector": "detector",  # ← 处置后可以重新检测验证
        "__end__": END,
    })

    return graph.compile()


# ══════════════════════════════════════════════════════════════
# 统一入口
# ══════════════════════════════════════════════════════════════

BUILDERS = {
    "mapreduce": ("Map-Reduce 并行扇出", build_mapreduce_pipeline),
    "loop": ("Iterative Loop 循环精炼", build_loop_pipeline),
    "mesh": ("Peer Mesh 去中心化", build_mesh_pipeline),
}


def run_pattern(mode: str, user_input: str, device_id: str = "") -> dict:
    label, builder = BUILDERS[mode]
    app = builder()
    initial = {
        "user_input": user_input,
        "device_id": device_id or "DEV-0001",
        "detect_result": "",
        "diagnose_result": "",
        "decide_result": "",
        "execute_result": "",
        "sub_tasks": [],
        "parallel_results": [],
        "loop_count": 0,
        "confidence_score": 0.0,
        "history_log": [],
        "next_step": "",
        "risk_level": "medium",
        "messages": [],
    }

    start = time.time()
    result = app.invoke(initial)
    elapsed = time.time() - start

    return {
        "mode": mode,
        "label": label,
        "elapsed": round(elapsed, 2),
        "execute": result.get("execute_result", ""),
        "loops": result.get("loop_count", 0),
        "confidence": result.get("confidence_score", 0),
        "parallel_tasks": len(result.get("parallel_results", [])),
        "messages_count": len(result.get("messages", [])),
    }


if __name__ == "__main__":
    MODE = sys.argv[1] if len(sys.argv) > 1 else "all"
    TASK = "DEV-0001 SCTP 链路中断导致退服，请帮我分析原因并给出处置方案"
    DEVICE = "DEV-0001"

    print("=" * 64)
    print("实验 3.3：LangGraph 进阶协作模式")
    print("=" * 64)
    print(f"\n任务：{TASK}")

    to_run = list(BUILDERS.keys()) if MODE == "all" else [MODE]
    results = {}

    for mode in to_run:
        label, _ = BUILDERS[mode]
        print(f"\n{'#'*50}")
        print(f"# {label}")
        print(f"{'#'*50}")

        result = run_pattern(mode, TASK, DEVICE)
        results[mode] = result

        print(f"耗时: {result['elapsed']}s")
        if mode == "mapreduce":
            print(f"并行任务数: {result['parallel_tasks']}")
            print(f"消息数: {result['messages_count']}")
        elif mode == "loop":
            print(f"循环次数: {result['loops']}")
            print(f"最终置信度: {result['confidence']:.2f}")
        elif mode == "mesh":
            print(f"消息数: {result['messages_count']}（Agent 间交互次数）")

        print(f"\n最终处置方案（前 300 字）:")
        print(result["execute"][:300])

    # ── 对比总结 ──
    if len(results) >= 2:
        print(f"\n\n{'='*64}")
        print("三种进阶协作模式对比")
        print(f"{'='*64}")
        print(f"{'模式':<22} {'耗时':>7} {'关键指标':>25} {'适用场景'}")
        print(f"{'-'*64}")
        for mode, r in results.items():
            if mode == "mapreduce":
                key = f"并行{r['parallel_tasks']}路"
                scene = "可拆分为独立子任务"
            elif mode == "loop":
                key = f"循环{r['loops']}次,置信度{r['confidence']:.2f}"
                scene = "首次诊断置信度低"
            else:
                key = f"交互{r['messages_count']}次"
                scene = "非固定流程、需动态协作"

            print(f"{r['label']:<22} {r['elapsed']:>6.1f}s {key:>25}  {scene}")

        print(f"""
协作模式选型决策树：

  任务可以拆成独立子任务？ ──是──→ Map-Reduce（并行扇出，汇总）
       │
       否
       │
       ▼
  流程可能回退/重做？ ──是──→ Iterative Loop（循环精炼）
       │
       否
       │
       ▼
  流程不固定、需要灵活跳转？ ──是──→ Peer Mesh（去中心化）
       │
       否
       │
       ▼
  回到 3.2 的 Serial/Supervisor/Conditional
""")

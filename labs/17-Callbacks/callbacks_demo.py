"""Callbacks 演示 — Agent 指标监控

运行：python callbacks_demo.py
依赖：pip install langchain langchain-openai langchain-community faiss-cpu requests
"""
import os
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))  # 自动读取课程根目录 .env

import time
from typing import Any, Dict, List
from langchain_core.callbacks import BaseCallbackHandler
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.tools import tool
from langchain.agents import create_agent


# ═══ 自定义 Callback Handler ═══
class MetricsCallback(BaseCallbackHandler):
    """记录每次 Agent 调用的 Token、延迟、工具调用次数"""

    def __init__(self):
        self.reset()

    def reset(self):
        self.start_time = None
        self.total_llm_calls = 0
        self.total_tool_calls = 0
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.llm_latencies: List[float] = []
        self._current_llm_start = None
        self._tool_names: List[str] = []

    def on_chain_start(self, serialized, inputs, **kwargs):
        # langchain 1.x 的 create_agent 返回的是 LangGraph 图，没有 on_agent_start；
        # 用第一次 on_chain_start 作为整轮开始时间
        if self.start_time is None:
            self.start_time = time.time()

    def on_llm_start(self, serialized, prompts, **kwargs):
        self.total_llm_calls += 1
        # 先估算输入 token，如果 on_llm_end 拿到了真实值则覆盖
        self._pending_input_tokens = sum(len(p) for p in prompts)
        self._current_llm_start = time.time()

    def on_llm_end(self, response, **kwargs):
        if self._current_llm_start:
            self.llm_latencies.append(time.time() - self._current_llm_start)
            self._current_llm_start = None

        # 尝试从 response 中提取真实 token 用量
        # langchain 1.x：真实用量在 message.usage_metadata / response_metadata，
        # llm_output["token_usage"] 通常为空，所以三个地方都要看
        usage = {}
        try:
            gen = response.generations[0][0]
            msg = getattr(gen, "message", None)
            um = getattr(msg, "usage_metadata", None) or {}
            if um:
                usage = {"prompt_tokens": um.get("input_tokens", 0),
                         "completion_tokens": um.get("output_tokens", 0)}
            if not usage:
                rm = getattr(msg, "response_metadata", None) or {}
                usage = rm.get("token_usage", {}) or {}
        except Exception:
            pass
        if not usage:
            token_usage = getattr(response, "llm_output", {}) or {}
            usage = token_usage.get("token_usage", {}) or {}
        if usage:
            # 有真实值就用真实值（覆盖估算）
            self.total_input_tokens += usage.get("prompt_tokens", self._pending_input_tokens)
            self.total_output_tokens += usage.get("completion_tokens", 0)
        else:
            # 没有真实值，用估算兜底
            self.total_input_tokens += self._pending_input_tokens
            try:
                generations = getattr(response, "generations", [[]])
                if generations and generations[0]:
                    gen = generations[0][0]
                    text = getattr(gen, "text", "") or ""
                    self.total_output_tokens += len(text)
            except Exception:
                pass
        self._pending_input_tokens = 0

    def on_tool_start(self, serialized, input_str, **kwargs):
        self.total_tool_calls += 1
        name = serialized.get("name", "unknown")
        self._tool_names.append(name)

    def summary(self) -> Dict[str, Any]:
        total_time = time.time() - self.start_time if self.start_time else 0
        avg_latency = (
            sum(self.llm_latencies) / len(self.llm_latencies)
            if self.llm_latencies else 0
        )
        return {
            "标签": "",
            "总耗时（秒）": round(total_time, 2),
            "LLM 调用次数": self.total_llm_calls,
            "工具调用次数": self.total_tool_calls,
            "输入 Token": self.total_input_tokens,
            "输出 Token": self.total_output_tokens,
            "LLM 平均延迟（秒）": round(avg_latency, 2),
            "调用工具": " → ".join(self._tool_names) if self._tool_names else "无",
        }


# ═══ Agent 配置 ═══
API_KEY = os.getenv("AGENT_API_KEY", "REPLACE_ME_NO_KEY")
API_BASE = os.getenv("AGENT_API_BASE", "https://api.deepseek.com/v1")
MODEL = os.getenv("AGENT_MODEL", "deepseek-chat")

llm = ChatOpenAI(
    model=MODEL,
    temperature=0,
    api_key=API_KEY,
    base_url=API_BASE,
)


# ═══ 工具定义 ═══
def _local_device(device_id: str):
    """平台没起时的本地兜底：直接读同目录 data/devices.json"""
    import json
    from pathlib import Path
    f = Path(__file__).parent / "data" / "devices.json"
    if not f.exists():
        return None
    raw = json.loads(f.read_text(encoding="utf-8"))
    devices = raw.get("devices", raw) if isinstance(raw, dict) else raw
    for d in devices:
        if d.get("device_id") == device_id:
            return d
    return None


@tool
def query_device(device_id: str) -> str:
    """查询 5G 基站设备详情。当用户提到具体设备 ID 时使用。"""
    import requests
    try:
        resp = requests.get(
            f"http://localhost:8000/devices/{device_id}", timeout=5
        )
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
    except Exception as e:
        d = _local_device(device_id)
        if d:
            alarms = d.get("alarms", []) or []
            alarm_info = "\n".join(
                f"  [{a.get('severity')}] {a.get('type')}: {a.get('description')}"
                for a in alarms) if alarms else "无告警"
            return (f"[本地快照] 设备 {device_id}：{d.get('vendor')} {d.get('model')}，"
                    f"站点 {d.get('site')}，状态 {d.get('status')}。"
                    f"告警（{len(alarms)}条）：\n{alarm_info}")
        return f"查询设备失败：{str(e)}"


@tool
def list_devices(status: str = "") -> str:
    """列出设备清单，可按状态筛选（running / alarm / maintenance）。用户问"有哪些设备""几台告警"时使用。"""
    import json
    from pathlib import Path
    f = Path(__file__).parent / "data" / "devices.json"
    if not f.exists():
        return "本地没有设备快照，无法列出设备"
    raw = json.loads(f.read_text(encoding="utf-8"))
    devices = raw.get("devices", raw) if isinstance(raw, dict) else raw
    rows = [d for d in devices if not status or d.get("status") == status]
    if not rows:
        return f"没有状态为 {status} 的设备"
    lines = [f"{d.get('device_id')} | {d.get('vendor')} {d.get('model')} | {d.get('site')} | {d.get('status')}"
             for d in rows]
    return f"共 {len(rows)} 台（筛选：{status or '全部'}）\n" + "\n".join(lines)


@tool
def search_kb(query: str) -> str:
    """在 5G 基站排障知识库中搜索相关内容。当用户询问排障步骤、故障原因时使用。"""
    try:
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
            return "知识库中未找到高度相关内容。"

        parts = []
        for doc, score in docs:
            source = doc.metadata.get("source", "未知来源")
            parts.append(
                f"[来源: {source}] [相似度: {score:.2f}]\n{doc.page_content[:300]}"
            )
        return "\n\n---\n".join(parts)
    except Exception as e:
        return f"知识库检索失败：{str(e)}"


def create_agent_with_callbacks():
    """创建 Agent

    注意 langchain 1.x 的两点变化：
      1. create_agent 返回的就是可执行的图，不再需要 AgentExecutor 包一层
      2. callbacks 不再传给 AgentExecutor，而是在 invoke 时通过 config 传
    """
    tools = [query_device, list_devices, search_kb]
    return create_agent(
        llm,
        tools,
        system_prompt="""你是 5G 基站智能排障助手。可以用 query_device 查设备详情、search_kb 检索排障知识库。
工作流程：先查设备状态 → 再搜知识库 → 综合给出诊断建议。""",
    )



# ═══ 主程序 ═══
if __name__ == "__main__":
    cb = MetricsCallback()
    executor = create_agent_with_callbacks()

    TEST_QUERIES = [
        ("简单查设备", "DEV-0001 是什么型号？"),
        ("告警查询", "DEV-0001 有哪些告警？"),
        ("排障+知识库", "DEV-0001 的告警怎么处理？参考知识库给出排查步骤"),
        ("复杂诊断", "帮我分析设备状态异常的原因。先查设备、再搜知识库、再给建议"),
        ("多设备对比", "告警设备有几台？列出最严重的那台的详细信息"),
    ]

    results = []
    for label, query in TEST_QUERIES:
        print(f"\n{'='*60}")
        print(f"测试：{label}")
        print(f"Query: {query}")
        print(f"{'='*60}")

        cb.reset()
        try:
            # callbacks 在 1.x 里通过 config 传，而不是传给 AgentExecutor
            result = executor.invoke(
                {"messages": [("user", query)]},
                config={"callbacks": [cb]},
            )
            metrics = cb.summary()
            metrics["标签"] = label
            metrics["回答长度"] = len(result["messages"][-1].content)
            results.append(metrics)

            print(f"\n📊 指标：")
            print(f"   耗时: {metrics['总耗时（秒）']}s")
            print(f"   LLM 调用: {metrics['LLM 调用次数']}次")
            print(f"   工具调用: {metrics['工具调用次数']}次")
            print(f"   输入 Token: {metrics['输入 Token']}")
            print(f"   输出 Token: {metrics['输出 Token']}")
            print(f"   工具链: {metrics['调用工具']}")
            print(f"   回答预览: {result['messages'][-1].content[:100]}...")
        except Exception as e:
            print(f"❌ 执行失败：{e}")

    # ── 汇总对比表格 ──
    print(f"\n\n{'='*80}")
    print("五条查询成本对比")
    print(f"{'='*80}")
    print(f"{'标签':<16} {'耗时(s)':>8} {'LLM':>5} {'工具':>5} {'Token入':>8} {'Token出':>8} {'总Token':>8}")
    print(f"{'-'*80}")
    for r in results:
        total_tokens = r['输入 Token'] + r['输出 Token']
        print(
            f"{r['标签']:<16}"
            f"{r['总耗时（秒）']:>8.2f}"
            f"{r['LLM 调用次数']:>5}"
            f"{r['工具调用次数']:>5}"
            f"{r['输入 Token']:>8}"
            f"{r['输出 Token']:>8}"
            f"{total_tokens:>8}"
        )

    # ── 发现 ──
    print(f"\n📌 发现（按本次实测数据）：")
    if results:
        by_tool = sorted(results, key=lambda r: r["工具调用次数"])
        print(f"   - 工具调用越多，LLM 调用次数和 Token 一般越高："
              f"0 次工具 ≈ {by_tool[0]['LLM 调用次数']} 次 LLM，"
              f"{by_tool[-1]['工具调用次数']} 次工具 ≈ {by_tool[-1]['LLM 调用次数']} 次 LLM")
        print(f"   - 具体数值取决于模型实际决策，同一问题两次跑也可能不同")
        print(f"   - 这正是 Callback 的价值：不用猜，每次都能看到真实开销")
    if results:
        cheapest = min(results, key=lambda r: r['输入 Token'] + r['输出 Token'])
        priciest = max(results, key=lambda r: r['输入 Token'] + r['输出 Token'])
        print(f"   - 最便宜：{cheapest['标签']}（{cheapest['输入 Token'] + cheapest['输出 Token']} tokens）")
        print(f"   - 最贵：{priciest['标签']}（{priciest['输入 Token'] + priciest['输出 Token']} tokens）")
        print(f"   - 差价：{priciest['输入 Token'] + priciest['输出 Token'] - cheapest['输入 Token'] - cheapest['输出 Token']} tokens")

"""可观测 Trace — 多 Agent 流水线每一步的耗时、Token、工具调用

不依赖外部服务（LangFuse/LangSmith 需要注册），
使用 LangChain Callbacks + 本地 JSON 日志实现等效功能。

运行：python trace_demo.py
依赖：无（仅标准库）。装了 langchain 会额外启用 LangChainTracer 回调类
"""
import json
import time
from typing import Dict, List
from datetime import datetime

# ══════════════════════════════════════════════════════════════
# 本地 Trace 收集器 — 不依赖 LangFuse/LangSmith
# ══════════════════════════════════════════════════════════════

class LocalTracer:
    """本地 Trace 收集器：记录每次 Agent 调用的完整链路"""

    def __init__(self):
        self.traces: List[Dict] = []
        self._current_trace = None
        # span 必须用栈而不是单个变量：嵌套调用（agent 里套 tool）
        # 时，单变量会被子 span 覆盖，导致父 span 永久丢失
        self._span_stack: List[Dict] = []

    def start_trace(self, name: str, input_data: dict = None) -> str:
        tid = f"trace-{int(time.time()*1000)}"
        self._current_trace = {
            "trace_id": tid,
            "name": name,
            "start_time": datetime.now().isoformat(),
            "input": input_data or {},
            "spans": [],
            "total_tokens": 0,
        }
        self._span_stack = []
        return tid

    def start_span(self, name: str, span_type: str = "agent") -> str:
        if not self._current_trace:
            self.start_trace("unnamed")
        sid = f"{name}-{len(self._current_trace['spans']) + len(self._span_stack)}"
        parent = self._span_stack[-1] if self._span_stack else None
        self._span_stack.append({
            "span_id": sid,
            "name": name,
            "type": span_type,
            "parent_span_id": parent["span_id"] if parent else None,
            "depth": len(self._span_stack),
            "start": time.time(),
            "start_ts": datetime.now().isoformat(),
        })
        return sid

    def end_span(self, output: dict = None, tokens: int = 0):
        if not self._span_stack:
            return
        span = self._span_stack.pop()
        span["elapsed_ms"] = round((time.time() - span["start"]) * 1000)
        span["end_ts"] = datetime.now().isoformat()
        span["output"] = output or {}
        span["tokens"] = tokens
        del span["start"]
        self._current_trace["spans"].append(span)
        self._current_trace["total_tokens"] += tokens

    def end_trace(self) -> Dict:
        trace = self._current_trace
        trace["end_time"] = datetime.now().isoformat()
        # 只累加顶层 span 的耗时，子 span 已含在父区间内，否则重复计算
        total_ms = sum(s.get("elapsed_ms", 0) for s in trace["spans"]
                       if s.get("parent_span_id") is None)
        trace["total_elapsed_ms"] = total_ms
        self.traces.append(trace)
        self._current_trace = None
        self._span_stack = []
        return trace

    def report(self) -> str:
        """生成可读报告"""
        if not self.traces:
            return "暂无 Trace 数据"

        lines = ["=" * 60, "Agent 调用链路 Trace 报告", "=" * 60]
        for trace in self.traces[-5:]:  # 最近 5 条
            lines.append(f"\n{trace['name']} ({trace['trace_id']})")
            lines.append(f"   总耗时: {trace.get('total_elapsed_ms', 0)}ms")
            lines.append(f"   总 Token: {trace.get('total_tokens', 0)}")

            for span, is_last in _tree_order(trace.get("spans", [])):
                bar = _bar(span.get("elapsed_ms", 0), trace.get("total_elapsed_ms", 1))
                depth = span.get("depth", 0)
                indent = "   " * depth
                prefix = "└─" if is_last else "├─"
                label = f"{indent}{prefix} {span['name']}"
                lines.append(
                    f"   {label:<26}{span.get('elapsed_ms',0):>6}ms {bar} "
                    f"[{span.get('type','')}]"
                )

        lines.append(f"\n{'='*60}")
        return "\n".join(lines)

    def to_json(self, path: str = "traces.json"):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.traces[-20:], f, ensure_ascii=False, indent=2)
        return path


def _tree_order(spans: List[Dict]):
    """把按结束时间入列的 spans 重排为树形顺序：父在前，紧跟其子。

    end_span 是子 span 先结束，所以 spans 里 faiss_search 会排在
    diagnoser 前面——直接按列表顺序打印会把子 span 挂错父亲。
    返回 (span, is_last) 供树形符号使用。
    """
    by_parent: Dict = {}
    for s in spans:
        by_parent.setdefault(s.get("parent_span_id"), []).append(s)

    out = []

    def walk(parent_id):
        children = by_parent.get(parent_id, [])
        for i, s in enumerate(children):
            out.append((s, i == len(children) - 1))
            walk(s["span_id"])

    walk(None)
    return out


def _bar(value: int, total: int) -> str:
    if total == 0:
        return ""
    pct = value / total
    blocks = int(pct * 20)
    return "█" * blocks + "░" * (20 - blocks)


# ══════════════════════════════════════════════════════════════
# 模拟多 Agent 流水线（不调真实 LLM，演示 Trace 能力）
# ══════════════════════════════════════════════════════════════

def simulate_detector(tracer: LocalTracer, device_id: str):
    tracer.start_span("detector", "agent")
    time.sleep(0.3)  # 模拟 API 调用
    tracer.end_span(output={"device": device_id, "alarms_found": 2}, tokens=150)


def simulate_diagnoser(tracer: LocalTracer, device_id: str):
    tracer.start_span("diagnoser", "agent")
    tracer.start_span("faiss_search", "tool")
    time.sleep(0.15)
    tracer.end_span(output={"hits": 3}, tokens=80)
    time.sleep(0.2)
    tracer.end_span(output={"root_cause": "SCTP配置错误"}, tokens=200)


def simulate_decider(tracer: LocalTracer):
    tracer.start_span("decider", "agent")
    time.sleep(0.15)
    tracer.end_span(output={"risk": "high"}, tokens=100)


def simulate_executor(tracer: LocalTracer):
    tracer.start_span("executor", "agent")
    time.sleep(0.1)
    tracer.end_span(output={"plan": "重启链路"}, tokens=120)


def simulate_full_pipeline(tracer: LocalTracer, device_id: str):
    tracer.start_trace(f"排障流水线-{device_id}", {"device_id": device_id})

    simulate_detector(tracer, device_id)
    simulate_diagnoser(tracer, device_id)
    simulate_decider(tracer)
    simulate_executor(tracer)

    return tracer.end_trace()


# ══════════════════════════════════════════════════════════════
# LangChain Callback — 如果安装了 langchain 就用真实 trace
# ══════════════════════════════════════════════════════════════

try:
    from langchain.callbacks.base import BaseCallbackHandler

    class LangChainTracer(BaseCallbackHandler, LocalTracer):
        """融合 LangChain Callback + 本地 Trace 收集"""

        def on_llm_start(self, serialized, prompts, **kwargs):
            self.start_span("llm", "llm")

        def on_llm_end(self, response, **kwargs):
            # 尝试提取 Token 用量
            usage = getattr(response, "llm_output", {}) or {}
            tokens = usage.get("token_usage", {}).get("total_tokens",
                     sum(len(p) for p in getattr(response, "generations", [[]])[0]
                         if hasattr(response, "generations")))
            self.end_span(tokens=tokens)

        def on_tool_start(self, serialized, input_str, **kwargs):
            name = serialized.get("name", "tool")
            self.start_span(name, "tool")

        def on_tool_end(self, output, **kwargs):
            self.end_span()

        def on_agent_action(self, action, **kwargs):
            pass  # LangGraph 模式下不需要额外处理

except ImportError:
    LangChainTracer = None


# ══════════════════════════════════════════════════════════════
# 演示
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("实验 3.6：可观测 Trace — 多 Agent 流水线链路追踪")
    print("=" * 60)

    tracer = LocalTracer()

    # ── 正常流程 ──
    print("\n# 模拟一次完整的排障流水线 Trace\n")
    simulate_full_pipeline(tracer, "DEV-0001")

    # ── 对比：不同复杂度任务的 Trace ──
    print("  [模拟] 简单任务...")
    tracer.start_trace("简单查设备", {"device_id": "DEV-0002"})
    simulate_detector(tracer, "DEV-0002")
    tracer.end_trace()

    # ── 报告 ──
    print(tracer.report())

    # ── 持久化 ──
    path = tracer.to_json("traces.json")
    print(f"\nTrace 已保存到 {path}")

    print(f"""
总结：
  本地 Trace 收集器实现了 LangFuse/LangSmith 的核心功能：
  1. 每次 Agent 调用 → 一条 Trace
  2. 每个子步骤（Agent/LLM/Tool）→ 一个 Span
  3. 每条 Span 记录：耗时 + Token + 输入/输出
  4. 可视化：控制台 ASCII 柱状图 + JSON 持久化

  如果要用真实 LangFuse：
  pip install langfuse
  from langfuse.langchain import CallbackHandler
  callback = CallbackHandler(public_key="...", secret_key="...")
  agent.invoke({{"input": "..."}}, config={{"callbacks": [callback]}})
  → 自动上报到 LangFuse Dashboard，无需手写 Trace 代码
""")

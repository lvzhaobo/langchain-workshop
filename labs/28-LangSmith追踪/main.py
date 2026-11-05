"""Lab 28 · LangSmith 追踪 —— 看清每一次调用

跑法：
    ./run.sh 28

两种模式：

  有 LANGSMITH_API_KEY   → 真实上报到 smith.langchain.com，控制台能看到完整 run tree
  没有                    → 用本地记录器打出**同样结构**的 run tree，
                            让你先看清"LangSmith 到底会收到什么"，再去注册也来得及

为什么要专门一个 lab：Lab 25 讲的是"自己写 callback 打点"，
LangSmith 是"不用写，框架自动帮你打"。两者的取舍是这个 lab 的重点。
"""
import os
import time
from contextlib import contextmanager

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from _mock_llm import scripted, use_mock

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

API_BASE = os.getenv("AGENT_API_BASE", "https://api.deepseek.com/v1")
API_KEY = os.getenv("AGENT_API_KEY", "")
MODEL = os.getenv("AGENT_MODEL", "deepseek-chat")

# LangSmith 用 LANGCHAIN_* 或 LANGSMITH_* 都认，两套都查一遍
LS_KEY = os.getenv("LANGSMITH_API_KEY") or os.getenv("LANGCHAIN_API_KEY") or ""
LS_PROJECT = os.getenv("LANGSMITH_PROJECT") or os.getenv("LANGCHAIN_PROJECT") or "langchain-workshop"

_spans: list[dict] = []
_depth = {"n": 0}


@contextmanager
def span(name: str, kind: str, **attrs):
    """一个 span：要么被 LangSmith 采集，要么被本地记录器采集。

    真实 LangSmith 是靠 @traceable / RunTree 自动做的，
    这里手写一层是为了在没有 key 时也能看到结构。
    """
    depth = _depth["n"]
    _depth["n"] += 1
    rec = {"name": name, "kind": kind, "depth": depth, "attrs": attrs, "start": time.time()}
    try:
        yield rec
    finally:
        rec["ms"] = int((time.time() - rec["start"]) * 1000)
        _depth["n"] -= 1
        _spans.append(rec)


def build_llm():
    if use_mock():
        return scripted([
            ("【诊断】DEV-0001 为 P0 基站退服，根因 SCTP 链路中断。"
             "建议：核查传输链路、检查 SCTP 对端 IP、30 分钟未恢复升级。", None),
        ] * 10)
    return ChatOpenAI(model=MODEL, temperature=0, api_key=API_KEY, base_url=API_BASE)


def fetch_device(device_id: str) -> str:
    with span("fetch_device", "tool", device_id=device_id):
        time.sleep(0.05)  # 模拟 HTTP
        return f"设备 {device_id}：华为 AAU5613，望京SOHO，状态 alarm，告警 [P0] 基站退服"


def search_kb(query: str) -> str:
    with span("search_kb", "retriever", query=query):
        time.sleep(0.03)
        return "SCTP 链路中断的常见原因是传输侧闪断或对端 IP 变更"


def diagnose(device_id: str) -> str:
    with span("diagnose_chain", "chain", device_id=device_id):
        info = fetch_device(device_id)
        kb = search_kb("SCTP 链路中断")

        with span("llm_call", "llm", model=MODEL):
            msgs = [
                SystemMessage(content="你是 5G 运维专家，给出 80 字以内的诊断。"),
                HumanMessage(content=f"{info}\n参考：{kb}"),
            ]
            resp = build_llm().invoke(msgs)

        with span("parse_output", "parser"):
            text = resp.content

        return text


def print_tree() -> None:
    print(f"\n{'─' * 64}")
    print("  Run Tree（LangSmith 里看到的就是这个结构）")
    print(f"{'─' * 64}")
    print(f"  {'trace':<28} {'kind':<10} {'耗时':>7}  属性")
    for s in sorted(_spans, key=lambda x: x["start"]):
        indent = "  " * s["depth"]
        attrs = " ".join(f"{k}={v}" for k, v in s["attrs"].items())[:40]
        print(f"  {indent}{s['name']:<26} {s['kind']:<10} {s['ms']:>5}ms  {attrs}")
    total = max((s["start"] + s["ms"] / 1000 for s in _spans), default=0) - min(
        (s["start"] for s in _spans), default=0)
    print(f"{'─' * 64}")
    print(f"  总耗时 {total * 1000:.0f}ms  |  {len(_spans)} 个 span")


def main() -> None:
    tracing = bool(LS_KEY)

    print("=" * 64)
    print("  Lab 28 · LangSmith 追踪")
    print("=" * 64)
    print(f"\n① 当前模式：{'真实上报 LangSmith' if tracing else '本地记录器（没配 LANGSMITH_API_KEY）'}")

    if tracing:
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_API_KEY"] = LS_KEY
        os.environ["LANGCHAIN_PROJECT"] = LS_PROJECT
        print(f"   项目：{LS_PROJECT}")
        print(f"   控制台：https://smith.langchain.com/o/-/projects")
    else:
        print("   想接真实 LangSmith，只需三个环境变量：")
        print("     LANGSMITH_API_KEY=lsv2_pt_xxx")
        print("     LANGSMITH_PROJECT=langchain-workshop")
        print("     （然后重跑本实验，上面的 run tree 就会出现在网页里）")

    if use_mock():
        print("\n⚠️  没检测到 AGENT_API_KEY —— 模型用预设答复（零 Key 模式）")

    print(f"\n② 跑一次诊断，观察产生了哪些 span")
    answer = diagnose("DEV-0001")
    print(f"   诊断结果：{answer[:70]}…")

    print_tree()

    print(f"\n{'=' * 64}")
    print("  核心收获")
    print("  1. 一次诊断 = 1 个 chain span + 2 个工具 span + 1 个 llm span + 1 个 parser span")
    print("  2. LangSmith 的价值：不用写 callback，run tree / 耗时 / Token 自动就有")
    print("  3. 和 Lab 25 的取舍：")
    print("       自写 callback  → 想采集什么自己定，但要维护，且没有跨服务的上下文")
    print("       LangSmith      → 零代码接入，能串起多服务，但要联网且数据出本地")
    print("  4. 生产建议：先上 LangSmith 把问题找出来，再决定哪些指标值得自己埋点")
    print("=" * 64)

    if tracing:
        print("\n   ↑ 去 smith.langchain.com 看这次运行的完整 run tree")


if __name__ == "__main__":
    main()

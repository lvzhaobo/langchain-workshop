"""验收：跑出 5 个 span 的 run tree，结构包含 chain / tool / retriever / llm / parser。"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = "main.py"

REQUIRED = [
    "Run Tree（LangSmith 里看到的就是这个结构）",
    "diagnose_chain",
    "fetch_device",
    "search_kb",
    "llm_call",
    "parse_output",
    "个 span",
]


def _env():
    e = dict(os.environ)
    for k in ("AGENT_API_KEY", "DEEPSEEK_API_KEY", "DASHSCOPE_API_KEY"):
        e[k] = ""
    return e


def main() -> int:
    try:
        r = subprocess.run([sys.executable, os.path.join(HERE, SCRIPT)],
                           capture_output=True, text=True, timeout=300, env=_env())
    except subprocess.TimeoutExpired:
        print(f"❌ {SCRIPT} 超时")
        return 1

    out = r.stdout + r.stderr
    missing = [s for s in REQUIRED if s not in out]
    if missing:
        print(f"❌ {SCRIPT} 输出缺少：{missing}")
        print("---- 实际输出最后 20 行 ----")
        print("\n".join(out.splitlines()[-20:]))
        return 1

    print(f"✅ 通过（{len(REQUIRED)} 项断言全部命中）")
    return 0


if __name__ == "__main__":
    sys.exit(main())

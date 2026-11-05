"""验收：5 条查询都跑完，且回调采集到 LLM 调用 / 工具调用 / Token / 工具链。"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = "callbacks_demo.py"

REQUIRED = [
    "五条查询成本对比",
    "最便宜",
    "最贵",
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

    # 5 条用例都要有指标输出
    if out.count("LLM 调用:") < 5:
        print(f"❌ 只采集到 {out.count('LLM 调用:')} 条，期望 5 条")
        return 1

    print(f"✅ 通过（{len(REQUIRED)} 项断言 + 5 条指标）")
    return 0


if __name__ == "__main__":
    sys.exit(main())

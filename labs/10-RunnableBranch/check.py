"""验收：P0 / P1 / 默认三条通道各走各的 prompt"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = "runnable_branch.py"

# 必须出现的片段：跑通时这些结论一定在输出里
REQUIRED = ['P0 立即行动', 'P1 排查步骤', '例行检查建议']


def _env():
    """强制零 Key 模式。

    置成空串而不是删除：load_dotenv 不会覆盖已存在的变量，
    这样即使本机 .env 里有 Key，验收也走确定的预设回复。
    """
    e = dict(os.environ)
    for k in ("AGENT_API_KEY", "DEEPSEEK_API_KEY", "DASHSCOPE_API_KEY"):
        e[k] = ""
    return e


def main() -> int:
    try:
        r = subprocess.run(
            [sys.executable, os.path.join(HERE, SCRIPT)],
            capture_output=True, text=True, timeout=300, input=None, env=_env(),
        )
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

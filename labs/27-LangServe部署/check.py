"""验收：LangServe 把图挂成 API 后，invoke / batch / stream 三个端点都能用。"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = "main.py"

REQUIRED = [
    "① add_routes 自动生成的端点",
    "② 单条调用 POST /invoke",
    "状态码 200",
    "③ 批量调用 POST /batch",
    "返回 2 条结果",
    "④ 流式 POST /stream",
    "个 SSE 事件",
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

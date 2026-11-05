"""验收脚本：不通过就退出码 1。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main() -> int:
    from solution import build

    out = build().invoke({"messages": [("user", "hi")]})
    ok = len(out["messages"]) == 2
    print("✅ 通过" if ok else f"❌ 期望 2 条消息，实际 {len(out['messages'])}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

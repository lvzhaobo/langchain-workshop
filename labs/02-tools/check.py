"""验收：main.py（或 --solution）应完成一次工具调用并拿到设备状态。"""
import argparse
import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, f"{name}.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--solution", action="store_true")
    target = "solution" if ap.parse_args().solution else "main"
    try:
        mod = load(target)
        out = mod.build().invoke({"messages": [("user", "DEV-0001 现在什么状态？")]})
    except Exception as e:  # noqa: BLE001
        print(f"❌ {target}.py 运行失败：{type(e).__name__}: {e}")
        return 1
    msgs = out.get("messages", [])
    kinds = [type(m).__name__ for m in msgs]
    hit = any("在线" in str(getattr(m, "content", "")) for m in msgs)
    ok = hit and "ToolMessage" in kinds and len(msgs) >= 3
    print("✅ 通过" if ok else f"❌ 期望 3 条消息且含设备状态，实际 {kinds} / {[getattr(m,'content','') for m in msgs]}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

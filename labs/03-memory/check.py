"""验收：同一 thread 递增、不同 thread 隔离。"""
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
        if hasattr(mod, "run"):
            a1, a2, b1 = mod.run()
        else:
            app = mod.build()
            cfg = {"configurable": {"thread_id": "A"}}
            cfg_b = {"configurable": {"thread_id": "B"}}
            a1 = app.invoke({}, config=cfg)["turns"]
            a2 = app.invoke({}, config=cfg)["turns"]
            b1 = app.invoke({}, config=cfg_b)["turns"]
    except Exception as e:  # noqa: BLE001
        print(f"❌ {target}.py 运行失败：{type(e).__name__}: {e}")
        return 1
    ok = (a1, a2, b1) == (1, 2, 1)
    print("✅ 通过" if ok else f"❌ 期望 (1, 2, 1)，实际 {(a1, a2, b1)}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

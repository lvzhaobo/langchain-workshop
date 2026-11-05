"""验收：main.py（或 --solution）应让 think 循环恰好 3 次。"""
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
        out = mod.build().invoke({"n": 0, "trace": []})
    except Exception as e:  # noqa: BLE001
        print(f"❌ {target}.py 运行失败：{type(e).__name__}: {e}")
        return 1
    ok = out.get("n") == 3 and len(out.get("trace", [])) == 3
    print("✅ 通过" if ok else f"❌ 期望 n=3 且 trace 有 3 条，实际 {out}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

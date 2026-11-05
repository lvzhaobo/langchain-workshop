#!/usr/bin/env python3
"""
Step 1: 基础 Agent Loop — 3 节点直线拓扑

用法:
    python main.py --api-key ollama --base-url http://localhost:11434/v1 --model qwen2.5:0.5b -q "你好"
"""
import os
import sys
import argparse


def main():
    parser = argparse.ArgumentParser(description="Step 1: 基础 Agent Loop")
    parser.add_argument("--api-key", help="LLM API Key")
    parser.add_argument("--base-url", help="LLM API 地址")
    parser.add_argument("--model", help="模型名")
    parser.add_argument("--workspace", default="./workspace", help="工作目录")
    parser.add_argument("--query", "-q", help="单次查询")
    parser.add_argument("--interactive", "-i", action="store_true", help="交互模式")
    args = parser.parse_args()

    workspace = os.path.abspath(args.workspace)
    if not os.path.exists(workspace):
        os.makedirs(workspace, exist_ok=True)

    from agent import build_graph  # type: ignore[import-untyped]

    print("=" * 60)
    print("🚀 Step 1: 基础 Agent Loop（3 节点直线拓扑）")
    print("=" * 60)

    graph = build_graph(model_name=args.model, api_key=args.api_key, base_url=args.base_url)
    print(f"📂 工作目录: {workspace}")

    if args.query:
        run_query(graph, workspace, args.query)
    else:
        run_interactive(graph, workspace)


def run_query(graph, workspace: str, query: str):
    config = {"configurable": {"thread_id": "step1"}}
    state = {
        "user_input": query, "workspace_path": workspace,
        "intent": "", "enriched_context": "", "final_output": "",
    }
    print(f"\n📝 用户输入: {query}\n🔄 执行中…\n")
    result = graph.invoke(state, config)
    print("\n" + "=" * 60)
    print("📦 结果")
    print("=" * 60)
    print(result.get("final_output", "(无输出)"))


def run_interactive(graph, workspace: str):
    print("\n交互模式（输入 exit 退出）\n")
    while True:
        try:
            q = input("🧑 你: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if q.lower() in ("exit", "quit"):
            break
        if not q:
            continue
        config = {"configurable": {"thread_id": "step1"}}
        state = {
            "user_input": q, "workspace_path": workspace,
            "intent": "", "enriched_context": "", "final_output": "",
        }
        result = graph.invoke(state, config)
        print(f"\n🤖 Agent:\n{result.get('final_output', '')}\n")


if __name__ == "__main__":
    main()

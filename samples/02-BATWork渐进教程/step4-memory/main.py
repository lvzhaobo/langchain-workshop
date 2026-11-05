#!/usr/bin/env python3
"""
BAT Work Agent Loop — 可运行的 LangGraph 示例（Step 4: + Memory 记忆系统）

用法:
    # 使用 OpenAI
    export OPENAI_API_KEY=sk-xxx
    python main.py

    # 使用本地 Ollama 模型
    python main.py --api-key ollama --base-url http://localhost:11434/v1 --model qwen2.5:7b

    # 使用通义千问（DashScope）
    python main.py --api-key $DASHSCOPE_API_KEY --base-url https://dashscope.aliyuncs.com/compatible-mode/v1 --model qwen-plus

    # 使用 DeepSeek
    python main.py --api-key $DEEPSEEK_API_KEY --base-url https://api.deepseek.com/v1 --model deepseek-chat

    # 指定工作目录
    python main.py --workspace ./my-workspace

Step 4 新增功能：
  - ChromaDB 向量记忆 + SQLite 摘要存储
  - 每次对话自动保存，下次对话自动召回相关历史
  - 支持项目知识库持久化（save_project_context / get_project_context）
"""

import os
import sys
import argparse


def main():
    parser = argparse.ArgumentParser(
        description="BAT Work Agent Loop — 基于 LangGraph 的 AI Agent 演示",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 使用本地 Ollama
  python main.py --api-key ollama --base-url http://localhost:11434/v1 --model qwen2.5:7b

  # 直接对话
  python main.py --query "用 sales.csv 的数据生成一份月度经营分析报告"

  # 交互模式
  python main.py --interactive

  # 指定工作目录
  python main.py --workspace ./my-project --interactive
        """
    )

    parser.add_argument("--api-key", help="LLM API Key（也可用环境变量 OPENAI_API_KEY）")
    parser.add_argument("--base-url", help="LLM API 地址（也可用环境变量 OPENAI_BASE_URL）")
    parser.add_argument("--model", help="模型名（也可用环境变量 LLM_MODEL，默认 gpt-4o-mini）")
    parser.add_argument("--workspace", default="./workspace", help="工作目录路径（默认 ./workspace）")
    parser.add_argument("--query", "-q", help="单次查询（非交互模式）")
    parser.add_argument("--interactive", "-i", action="store_true", help="交互模式")
    parser.add_argument("--verbose", "-v", action="store_true", help="显示详细日志")

    args = parser.parse_args()

    # 计算工作目录的绝对路径
    workspace = os.path.abspath(args.workspace)

    # 导入 agent（延迟导入，让 argparse 的 --help 更快）
    from agent import build_graph
    from memory import AgentMemory  # Step 4 新增

    # ── Step 4 新增：初始化记忆系统 ──
    memory = AgentMemory(persist_dir=os.path.join(workspace, "..", "memory_data"))

    # 构建 Graph
    print("=" * 60)
    print("🚀 BAT Work Agent Loop (LangGraph Demo) — Step 4: +Memory 记忆系统")
    print("=" * 60)

    try:
        graph = build_graph(
            model_name=args.model,
            api_key=args.api_key,
            base_url=args.base_url,
            memory=memory,  # Step 4 新增
        )
    except RuntimeError as e:
        print(f"\n❌ 启动失败: {e}")
        sys.exit(1)

    print(f"📂 工作目录: {workspace}")
    if not os.path.exists(workspace):
        os.makedirs(workspace, exist_ok=True)
        print(f"   (已创建)")

    # 列出工作目录文件
    files = [f for f in os.listdir(workspace) if os.path.isfile(os.path.join(workspace, f)) and not f.startswith(".")]
    if files:
        print(f"📄 已有文件: {', '.join(files)}")

    print("\n" + "=" * 60)
    print("💡 试试这些指令:")
    print("   • 分析 sales.csv 中各产品的销售趋势")
    print("   • 列出当前目录的文件")
    print("   • 帮我生成一份数据分析报告")
    print("=" * 60)

    # 执行查询
    if args.query:
        run_query(graph, workspace, args.query, memory)
    elif args.interactive:
        run_interactive(graph, workspace, memory)
    else:
        # 默认：交互模式
        run_interactive(graph, workspace, memory)


def run_query(graph, workspace: str, query: str, memory=None):
    """执行单次查询"""
    import uuid
    session_id = str(uuid.uuid4())[:8]  # Step 4 新增
    
    print(f"\n📝 用户输入: {query}")
    print(f"🧠 会话 ID: {session_id}\n")

    config = {"configurable": {"thread_id": f"demo-{session_id}"}}

    initial_state = {
        "user_input": query,
        "workspace_path": workspace,
        "session_id": session_id,  # Step 4 新增
        "intent": "",
        "enriched_context": "",
        "plan": [],
        "current_step": 0,
        "tool_results": [],
        "validation_passed": False,
        "validation_feedback": "",
        "retry_count": 0,
        "final_output": "",
        "output_files": [],
    }

    print("🔄 Agent 正在执行...\n")

    result = graph.invoke(initial_state, config)

    # ── Step 4 新增：保存交互记录到 Memory ──
    if memory is not None:
        memory.save_interaction(
            session_id=session_id,
            intent=result.get("intent", ""),
            context=result.get("enriched_context", "")[:500],
            summary=result.get("final_output", "")[:500],
        )

    # 打印最终结果
    print("\n" + "=" * 60)
    print("📦 最终产物")
    print("=" * 60)
    if result.get("final_output"):
        print(result["final_output"])
    else:
        print("(无输出)")

    if result.get("output_files"):
        print(f"\n📁 产出文件: {', '.join(result['output_files'])}")


def run_interactive(graph, workspace: str, memory=None):
    """交互模式：持续接收用户输入"""
    import uuid
    session_id = 1

    print("\n进入交互模式（输入 'exit' 或 'quit' 退出，输入 'new' 开始新会话）")
    print("输入 'memory-stats' 查看记忆统计，输入 'project-set key=value' 设置项目知识\n")

    while True:
        try:
            query = input("🧑 你: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n👋 再见！")
            break

        if not query:
            continue

        if query.lower() in ("exit", "quit"):
            print("👋 再见！")
            break

        if query.lower() == "new":
            session_id += 1
            print(f"✨ 新会话已创建 (session-{session_id})\n")
            continue

        # ── Step 4 新增：查看记忆统计 ──
        if query.lower() == "memory-stats" and memory is not None:
            print(f"🧠 记忆统计: {memory.stats()}\n")
            continue

        # ── Step 4 新增：设置项目知识 ──
        if query.startswith("project-set ") and memory is not None:
            parts = query[len("project-set "):].split("=", 1)
            if len(parts) == 2:
                memory.save_project_context(parts[0].strip(), parts[1].strip())
                print(f"📚 项目知识已设置: {parts[0].strip()}\n")
            continue

        current_sid = str(uuid.uuid4())[:8]  # Step 4 新增：每次对话唯一 ID
        config = {"configurable": {"thread_id": f"session-{session_id}"}}

        initial_state = {
            "user_input": query,
            "workspace_path": workspace,
            "session_id": current_sid,  # Step 4 新增
            "intent": "",
            "enriched_context": "",
            "plan": [],
            "current_step": 0,
            "tool_results": [],
            "validation_passed": False,
            "validation_feedback": "",
            "retry_count": 0,
            "final_output": "",
            "output_files": [],
        }

        print()

        try:
            result = graph.invoke(initial_state, config)
        except Exception as e:
            print(f"❌ 执行失败: {e}\n")
            continue

        # ── Step 4 新增：保存交互记录 ──
        if memory is not None:
            memory.save_interaction(
                session_id=current_sid,
                intent=result.get("intent", ""),
                context=result.get("enriched_context", "")[:500],
                summary=result.get("final_output", "")[:500],
            )

        output = result.get("final_output", "")
        if output:
            print("\n" + "─" * 60)
            print("🤖 Agent:")
            print("─" * 60)
            # 截断过长输出
            if len(output) > 2000:
                print(output[:2000])
                print(f"\n... (共 {len(output)} 字符，完整内容见 output.md)")
            else:
                print(output)
            print("─" * 60)

        if result.get("output_files"):
            print(f"📁 产物文件: {', '.join(result['output_files'])}")

        print()


if __name__ == "__main__":
    main()

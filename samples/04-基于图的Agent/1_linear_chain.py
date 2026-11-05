"""
DAG 模式 1：线性链（Linear Chain）

图结构：
  [planner] ──add_edge──→ [writer] ──add_edge──→ [polisher] ──→ END

API 映射：
  builder.add_node("name", func)   → 注册节点
  builder.set_entry_point("name")  → 设置入口
  builder.add_edge("A", "B")       → 直接边（无条件流转）
  builder.compile()                → 编译为可执行 App
  app.invoke(initial_state)        → 执行全图

运行：
  export DASHSCOPE_API_KEY="sk-..."
  python 1_linear_chain.py
"""

import os, time
from typing import TypedDict
from datetime import datetime, timezone, timedelta
from langgraph.graph import StateGraph, END

CST = timezone(timedelta(hours=8))


# ====== State ======
class State(TypedDict):
    topic: str
    plan: str
    draft: str
    final: str


# ====== LLM ======
def _init_llm():
    key = os.getenv("DASHSCOPE_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not key:
        return None, "mock", None, None
    from langchain_openai import ChatOpenAI
    if os.getenv("DASHSCOPE_API_KEY"):
        return ChatOpenAI(model="qwen-plus", api_key=key, base_url="https://dashscope.aliyuncs.com/compatible-mode/v1", temperature=0.7), "bailian", "qwen-plus", "https://dashscope.aliyuncs.com/compatible-mode/v1"
    return ChatOpenAI(model="gpt-4o-mini", api_key=key, temperature=0.7), "openai", "gpt-4o-mini", "https://api.openai.com/v1"


llm, mode, model, base_url = _init_llm()


def _call(prompt: str) -> tuple[str, dict]:
    start = time.time()
    trace = {"timestamp": datetime.now(CST).strftime("%H:%M:%S"), "model": model or "mock", "mode": mode, "base_url": base_url or "N/A", "prompt_len": len(prompt)}
    if llm is None:
        time.sleep(0.2)
        trace["latency_ms"] = 200
        trace["is_mock"] = True
        return "", trace
    try:
        resp = llm.invoke(prompt)
        trace["latency_ms"] = round((time.time() - start) * 1000)
        trace["is_mock"] = False
        try:
            u = resp.response_metadata.get("token_usage", {})
            trace["tokens"] = f"in:{u.get('prompt_tokens','?')} out:{u.get('completion_tokens','?')} total:{u.get('total_tokens','?')}"
        except:
            trace["tokens"] = "N/A"
        return resp.content, trace
    except Exception as e:
        trace["error"] = str(e)
        raise


# ====== Nodes ======
def planner_node(s: State) -> dict:
    print(f"\n🔵 [planner] 开始...")
    content, trace = _call(f'请为主题「{s["topic"]}」生成一个 3 段式的写作大纲，每段一句话。直接输出，不要废话。')
    plan = content or f"1. 引言段：阐述「{s['topic']}」的背景\n2. 主体段：分析趋势\n3. 结论段：展望未来"
    print(f"   ✅ 完成 | {trace['timestamp']} | {trace.get('model')} | {trace.get('latency_ms')}ms | {trace.get('tokens','')}")
    return {"plan": plan, "_trace": trace}


def writer_node(s: State) -> dict:
    print(f"\n🟢 [writer] 开始...")
    content, trace = _call(f'根据以下大纲写一篇 300 字左右的短文：\n\n{s["plan"]}')
    draft = content or f"这是一篇关于「{s['topic']}」的模拟文章..."
    print(f"   ✅ 完成 | {trace['timestamp']} | {trace.get('model')} | {trace.get('latency_ms')}ms | {trace.get('tokens','')}")
    return {"draft": draft, "_trace": trace}


def polisher_node(s: State) -> dict:
    print(f"\n🟡 [polisher] 开始...")
    content, trace = _call(f'请润色以下文章，修正语法和用词，使其更加优美：\n\n{s["draft"]}')
    final = content or f"【润色版】\n{s['draft']}\n── 完成 ✅"
    print(f"   ✅ 完成 | {trace['timestamp']} | {trace.get('model')} | {trace.get('latency_ms')}ms | {trace.get('tokens','')}")
    return {"final": final, "_trace": trace}


# ====== Build Graph ======
builder = StateGraph(State)
builder.add_node("planner", planner_node)
builder.add_node("writer", writer_node)
builder.add_node("polisher", polisher_node)
builder.set_entry_point("planner")
builder.add_edge("planner", "writer")    # 边1：直接边
builder.add_edge("writer", "polisher")   # 边2：直接边
builder.add_edge("polisher", END)        # 边3：结束边
app = builder.compile()


# ====== Run ======
if __name__ == "__main__":
    print("=" * 50)
    print(f"📐 DAG 模式 1：线性链 [{mode.upper()}]")
    print("=" * 50)
    print("图拓扑: [planner] → [writer] → [polisher] → END")
    print("边类型: 全部 add_edge（直接边），无条件路由")
    print()

    topic = "AI Agent 的发展趋势"
    print(f"📝 输入: {topic}\n")

    # 用 stream 看每步
    for step in app.stream({"topic": topic}):
        node_id = list(step.keys())[0]
        output_key = {"planner": "plan", "writer": "draft", "polisher": "final"}.get(node_id)
        output = step[node_id].get(output_key, "")
        trace = step[node_id].get("_trace", {})
        print(f"   [{node_id}] → {output_key} ({len(output)}字)")

    print(f"\n✨ 最终稿:\n{output[:200]}...")

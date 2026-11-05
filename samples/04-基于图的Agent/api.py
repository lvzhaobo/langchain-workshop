"""
Flask API — 将 LangGraph 流水线封装为 HTTP 服务
启动方式：
    source .venv/bin/activate
    python api.py
    然后打开 http://localhost:5050
"""

import time
import json
from flask import Flask, request, jsonify, send_from_directory, Response, stream_with_context
from graph_app import build_graph, get_graph_structure, _get_llm, get_llm_info

app = Flask(__name__, static_folder="static", static_url_path="/static")

# 全局编译图实例（复用）
_graph_app = build_graph()


# ============================================================
# 页面路由
# ============================================================

@app.route("/")
def index():
    """前端主页面"""
    return send_from_directory("templates", "index.html")


@app.route("/walkthrough")
def walkthrough():
    """逐步讲解页面"""
    return send_from_directory("templates", "walkthrough.html")


@app.route("/patterns")
def patterns():
    """7种DAG模式对比页面"""
    return send_from_directory(".", "patterns_compare.html")


# ============================================================
# API 路由
# ============================================================

@app.route("/api/generate", methods=["POST"])
def generate():
    """
    执行图流水线，用 stream 捕获每个节点的中间输出
    请求体：{"topic": "..."}
    """
    data = request.get_json()
    topic = data.get("topic", "").strip()

    if not topic:
        return jsonify({"success": False, "error": "topic 不能为空"}), 400

    # 检测 LLM 模式
    _, llm_mode = _get_llm()

    node_names = {
        "planner":  "📋 计划节点",
        "writer":   "✍️ 写作节点",
        "polisher": "✨ 润色节点",
    }
    node_descs = {
        "planner":  "根据主题生成 3 段式写作大纲",
        "writer":   "根据大纲撰写 300 字正文",
        "polisher": "润色正文，修正语法与用词",
    }

    try:
        start_time = time.time()
        nodes_output = []
        final_state = {}

        # 关键：stream() 每次 yield 一个节点的执行结果
        for step in _graph_app.stream({"topic": topic}):
            node_start = time.time()

            # step 格式：{"planner": {"plan": "..."}}
            node_id = list(step.keys())[0]
            node_result = step[node_id]
            output_key = {"planner": "plan", "writer": "draft", "polisher": "final"}.get(node_id, node_id)
            output_text = node_result.get(output_key, "")

            nodes_output.append({
                "id": node_id,
                "name": node_names.get(node_id, node_id),
                "description": node_descs.get(node_id, ""),
                "output": output_text,
                "output_length": len(output_text),
                "status": "done",
            })
            final_state.update(node_result)

        total_elapsed = round((time.time() - start_time) * 1000)

        return jsonify({
            "success": True,
            "topic": topic,
            "mode": llm_mode,
            "nodes": nodes_output,
            "final": final_state.get("final", ""),
            "total_elapsed_ms": total_elapsed,
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/generate-stream", methods=["POST"])
def generate_stream():
    """
    SSE 流式端点：逐步推送每个节点的执行结果
    每完成一个节点，前端立即收到一条事件，实现"一步步分析"效果
    """
    data = request.get_json()
    topic = data.get("topic", "").strip()

    if not topic:
        def err_stream():
            yield f"data: {json.dumps({'type': 'error', 'error': 'topic 不能为空'})}\n\n"
        return Response(err_stream(), mimetype="text/event-stream", status=400)

    _, llm_mode = _get_llm()

    # ============================================================
    # 图步骤元数据 — 每个节点的 DAG 上下文解释
    # ============================================================
    STEP_META = {
        "planner": {
            "id": "planner",
            "name": "📋 计划节点",
            "description": "根据主题生成 3 段式写作大纲",
            "step": 1,
            "total_steps": 3,
            "incoming_edge": {
                "type": "入口边 (set_entry_point)",
                "from_node": "__start__",
                "from_label": "🚀 开始",
                "to_node": "planner",
                "label": "入口 → 计划",
                "explanation": "这是 DAG 的入口节点。通过 builder.set_entry_point(\"planner\") 声明为图的起点。执行开始时，LangGraph 自动从 __start__ 沿入口边进入此节点。",
            },
            "why_now": "作为 DAG 的入口节点（set_entry_point），它是整个流水线的起点。此时 State 仅有用户输入的 topic，其余字段为空。",
            "what_happens": "LLM 接收 topic → 生成 3 段式写作大纲 → 返回 {\"plan\": \"...\"} 更新 State",
            "state_in": ["topic"],
            "state_out": ["plan"],
            "node_color": "#3b82f6",
        },
        "writer": {
            "id": "writer",
            "name": "✍️ 写作节点",
            "description": "根据大纲撰写 300 字正文",
            "step": 2,
            "total_steps": 3,
            "incoming_edge": {
                "type": "直接边 (add_edge)",
                "from_node": "planner",
                "from_label": "📋 计划节点",
                "to_node": "writer",
                "label": "计划 → 写作",
                "explanation": "planner 节点完成后，通过 builder.add_edge(\"planner\", \"writer\") 声明的直接边流转到此。直接边是无条件路由 — 上游完成即触发下游。",
            },
            "why_now": "planner 节点已完成，State 中已有了 plan 字段。add_edge(\"planner\", \"writer\") 定义了从 planner 到 writer 的直接依赖 — 大纲就绪后才能开始写作。",
            "what_happens": "LLM 接收 State 中的 topic + plan → 展开成 300 字短文 → 返回 {\"draft\": \"...\"} 更新 State",
            "state_in": ["topic", "plan"],
            "state_out": ["draft"],
            "node_color": "#10b981",
        },
        "polisher": {
            "id": "polisher",
            "name": "✨ 润色节点",
            "description": "润色正文，修正语法与用词",
            "step": 3,
            "total_steps": 3,
            "incoming_edge": {
                "type": "直接边 (add_edge)",
                "from_node": "writer",
                "from_label": "✍️ 写作节点",
                "to_node": "polisher",
                "label": "写作 → 润色",
                "explanation": "writer 完成后，通过 builder.add_edge(\"writer\", \"polisher\") 流转到润色节点。这是 DAG 的最后一个业务节点，之后通过 add_edge(\"polisher\", END) 结束整个图。",
            },
            "why_now": "writer 节点已完成，State 中已有了 draft 字段。add_edge(\"writer\", \"polisher\") 定义了写作→润色的依赖。这是最后一步 — 润色完成后，图通过 add_edge(\"polisher\", END) 终止。",
            "what_happens": "LLM 接收 draft 全文 → 修正语法与用词，使表达更优美 → 返回 {\"final\": \"...\"} 更新 State，随后图流向 END 结束",
            "state_in": ["topic", "plan", "draft"],
            "state_out": ["final"],
            "node_color": "#f59e0b",
        },
    }
    node_order = ["planner", "writer", "polisher"]

    def event_stream():
        start_time = time.time()
        final_state = {}
        step_index = 0

        # 发送初始化事件：完整图结构 + 所有步骤的元数据（前端可提前渲染）
        yield f"data: {json.dumps({'type': 'init', 'mode': llm_mode, 'total_steps': len(node_order), 'topic': topic, 'edges': [{'from': '__start__', 'to': 'planner', 'type': 'entry'}, {'from': 'planner', 'to': 'writer', 'type': 'direct'}, {'from': 'writer', 'to': 'polisher', 'type': 'direct'}, {'from': 'polisher', 'to': '__end__', 'type': 'exit'}]}, ensure_ascii=False)}\n\n"

        try:
            for step in _graph_app.stream({"topic": topic}):
                node_start = time.time()
                node_id = list(step.keys())[0]
                node_result = step[node_id]
                output_key = {"planner": "plan", "writer": "draft", "polisher": "final"}.get(node_id, node_id)
                output_text = node_result.get(output_key, "")
                final_state.update(node_result)

                step_index += 1
                elapsed = round((time.time() - node_start) * 1000)
                meta = STEP_META.get(node_id, {})

                # 节点开始执行事件
                yield f"data: {json.dumps({'type': 'node_start', 'node': {'id': node_id, 'name': meta.get('name', node_id), 'step': step_index, 'total_steps': len(node_order)}, 'edge': meta.get('incoming_edge')}, ensure_ascii=False)}\n\n"

                # Mock 模式延迟（让前端动画可见）
                if llm_mode == "mock":
                    time.sleep(0.6)

                # 提取 API 调用追踪信息
                trace_key = f"_trace_{node_id}"
                api_trace = node_result.get(trace_key) or {}

                # 节点执行完成事件 — 包含完整的 DAG 解释 + API 调用详情
                yield f"data: {json.dumps({'type': 'node_done', 'node': {'id': node_id, 'name': meta.get('name', node_id), 'description': meta.get('description', ''), 'why_now': meta.get('why_now', ''), 'what_happens': meta.get('what_happens', ''), 'state_in': meta.get('state_in', []), 'state_out': meta.get('state_out', []), 'node_color': meta.get('node_color', '#3b82f6'), 'incoming_edge': meta.get('incoming_edge'), 'output': output_text, 'output_length': len(output_text), 'step': step_index, 'total_steps': len(node_order), 'elapsed_ms': elapsed, 'status': 'done', 'api_trace': api_trace}}, ensure_ascii=False)}\n\n"

            total_elapsed = round((time.time() - start_time) * 1000)
            yield f"data: {json.dumps({'type': 'done', 'final': final_state.get('final', ''), 'total_elapsed_ms': total_elapsed, 'total_steps': len(node_order)}, ensure_ascii=False)}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)}, ensure_ascii=False)}\n\n"

    return Response(
        stream_with_context(event_stream()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        }
    )


@app.route("/api/llm-info", methods=["GET"])
def llm_info():
    """返回当前 LLM 配置详情"""
    return jsonify({
        "success": True,
        **get_llm_info(),
    })


@app.route("/api/graph-info", methods=["GET"])
def graph_info():
    """返回图结构、节点和边的元数据"""
    return jsonify({
        "success": True,
        "mode": _get_llm()[1],
        **get_graph_structure(),
    })


# ============================================================
# 启动
# ============================================================
if __name__ == "__main__":
    _, mode = _get_llm()
    print("=" * 50)
    print(f"🚀 LangGraph API 启动中... [{mode.upper()} 模式]")
    print(f"   前端页面：http://localhost:8199")
    print(f"   生成接口：POST /api/generate")
    print(f"   SSE流式： POST /api/generate-stream")
    print(f"   图结构：  GET  /api/graph-info")
    print("=" * 50)
    app.run(host="0.0.0.0", port=8199, debug=True)

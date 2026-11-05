#!/usr/bin/env python3
"""
BAT Work Web Server — FastAPI 后端 + WebSocket 流式 Agent 执行

Step 7 新增：Token 级流式输出（逐字动画），含 Memory + Skill 支持

启动:
    python server.py --port 6001 --model qwen2.5:0.5b

    # 使用 OpenAI（流式 Token 输出）
    python server.py --api-key sk-xxx --model gpt-4o-mini --port 6001

    # 使用本地 Ollama + 自定义 Skills
    python server.py --api-key ollama --base-url http://localhost:11434/v1 --model qwen2.5:0.5b --port 6001 --skills-dir ./skills
"""

from __future__ import annotations
import os
import sys
import json
import argparse
import asyncio
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from skill_loader import load_skills, Skill  # noqa: F401

# LangGraph 节点名称列表（用于 astream_events 过滤）
NODE_NAMES = {
    "understand_intent", "enrich_context", "plan_tasks",
    "execute_tool", "validate_result", "generate_output", "handle_error"
}

# ─── 构建 Agent Graph ───────────────────────────────────────────

def create_graph(args) -> Any:
    """根据命令行参数构建编译好的 Agent Graph（含 Memory + Skill）"""
    from agent import build_graph  # type: ignore[import-untyped]
    from memory import AgentMemory  # Step 4
    from skill_loader import load_skills  # Step 5

    # 初始化 Memory
    workspace_abs = os.path.abspath(args.workspace)
    memory = AgentMemory(persist_dir=os.path.join(workspace_abs, "..", "memory_data"))

    # 加载 Skills
    skills = load_skills(args.skills_dir if hasattr(args, 'skills_dir') else "./skills")
    if skills:
        print(f"🎯 已加载 {len(skills)} 个 Skill")

    return build_graph(
        model_name=args.model,
        api_key=args.api_key,
        base_url=args.base_url,
        memory=memory,
        skills=skills,
    )


# ─── FastAPI App ────────────────────────────────────────────────

app = FastAPI(title="BAT Work (Step 7: Streaming)")

# 全局 graph 实例（启动时初始化）
graph: Any = None
workspace_path: str = ""


@app.get("/api/files")
async def list_files():
    """列出工作目录文件"""
    ws = workspace_path
    files = []
    if os.path.exists(ws):
        for f in sorted(os.listdir(ws)):
            full = os.path.join(ws, f)
            if os.path.isfile(full) and not f.startswith("."):
                files.append({
                    "name": f,
                    "size": os.path.getsize(full),
                })
    return {"files": files}


# ─── Skill 市场（内置预置 Skill 定义）───────────────────────────

SKILL_MARKETPLACE = [
    {
        "id": "monthly-report",
        "name": "月度经营分析报告",
        "description": "自动分析销售数据，按产品和区域分组统计，生成结构化月度经营报告",
        "triggers": ["月度报告", "经营分析", "月报"],
        "category": "数据分析",
        "premium": False,
    },
    {
        "id": "competitor-analysis",
        "name": "竞品分析报告",
        "description": "读取竞品数据文件，多维度对比分析，生成 SWOT 和策略建议",
        "triggers": ["竞品分析", "竞争对手", "市场对比"],
        "category": "市场研究",
        "premium": False,
    },
    {
        "id": "email-composer",
        "name": "客户邮件撰写",
        "description": "根据客户数据和商务场景，自动生成专业商务邮件模板",
        "triggers": ["写邮件", "客户邮件", "商务邮件", "邮件模板"],
        "category": "办公效率",
        "premium": False,
    },
    {
        "id": "data-viz",
        "name": "数据可视化图表",
        "description": "将 CSV 数据转换为交互式 HTML 图表（折线图/柱状图/饼图）",
        "triggers": ["数据可视化", "图表", "趋势图", "柱状图", "饼图"],
        "category": "数据可视化",
        "premium": False,
    },
    {
        "id": "weekly-summary",
        "name": "每周工作周报",
        "description": "基于项目文件和执行记录，自动汇总生成周报",
        "triggers": ["周报", "每周总结", "工作汇报"],
        "category": "办公效率",
        "premium": False,
    },
    {
        "id": "code-review",
        "name": "代码审查助手",
        "description": "读取代码文件，检查常见问题，生成审查报告",
        "triggers": ["代码审查", "review", "检查代码", "代码质量"],
        "category": "开发工具",
        "premium": True,
    },
]


@app.get("/api/skills")
async def list_skills():
    """返回当前已安装的 Skill 列表"""
    import os as _os  # noqa: F811
    skills_dir = _os.path.join(_os.path.dirname(__file__), "skills")
    skills = load_skills(skills_dir)
    return {
        "skills": [
            {
                "name": s.name,
                "triggers": s.triggers,
                "steps": s.steps,
                "constraints": s.constraints,
                "source_file": s.source_file,
            }
            for s in skills
        ],
        "count": len(skills),
    }


@app.get("/api/skills/marketplace")
async def list_marketplace():
    """返回 Skill 市场（可安装的 Skill 列表）"""
    # 标记已安装的 Skill
    import os as _os  # noqa: F811
    skills_dir = _os.path.join(_os.path.dirname(__file__), "skills")
    installed = load_skills(skills_dir)
    installed_names = {s.name for s in installed}

    result = []
    for item in SKILL_MARKETPLACE:
        item_copy = dict(item)
        item_copy["installed"] = item["name"] in installed_names
        result.append(item_copy)
    return {"skills": result}


@app.post("/api/skills/install/{skill_id}")
async def install_skill(skill_id: str):
    """安装指定 Skill 到 skills/ 目录"""
    import os as _os
    market_item = next((s for s in SKILL_MARKETPLACE if s["id"] == skill_id), None)
    if not market_item:
        return {"success": False, "error": f"Skill '{skill_id}' 不在市场中"}

    skills_dir = _os.path.join(_os.path.dirname(__file__), "skills")
    _os.makedirs(skills_dir, exist_ok=True)

    skill_folder = _os.path.join(skills_dir, skill_id)
    if _os.path.exists(skill_folder):
        return {"success": False, "error": f"Skill '{market_item['name']}' 已安装"}

    _os.makedirs(skill_folder, exist_ok=True)

    # 生成 SKILL.md 内容
    steps_map = {
        "monthly-report": [
            "1. 读取 sales.csv 获取当月销售数据",
            "2. 调用 analyze_csv 做统计（按产品和区域分组）",
            "3. 按以下结构生成报告：总体概览 → 产品排名 → 区域对比 → 建议",
        ],
        "competitor-analysis": [
            "1. 读取竞品数据文件（competitor_data.csv 或指定文件）",
            "2. 多维度对比分析（价格/功能/市场份额）",
            "3. 生成 SWOT 分析矩阵",
            "4. 给出差异化策略建议",
        ],
        "email-composer": [
            "1. 确认邮件场景（报价/跟进/感谢/邀约）",
            "2. 读取客户信息和历史往来",
            "3. 按商务邮件模板结构撰写",
            "4. 检查语气和格式",
        ],
        "data-viz": [
            "1. 读取 CSV 数据文件",
            "2. 分析数据字段和类型",
            "3. 选择最适合的图表类型",
            "4. 生成交互式 HTML 图表",
        ],
        "weekly-summary": [
            "1. 扫描 workspace 最近一周的文件变更",
            "2. 汇总执行记录和输出结果",
            "3. 按模板生成周报（本周完成/下周计划/风险项）",
        ],
        "code-review": [
            "1. 读取目标代码文件",
            "2. 检查命名规范、注释覆盖率",
            "3. 检查常见反模式（硬编码、N+1 查询等）",
            "4. 生成审查报告（严重/警告/建议）",
        ],
    }

    constraints_map = {
        "monthly-report": ["金额单位用万元", "增长率用百分比", "标题格式：YYYY年MM月经营分析报告"],
        "competitor-analysis": ["对比维度不少于 4 个", "每个结论需有数据支撑", "输出用中文"],
        "email-composer": ["语气专业但不生硬", "自动填入客户名称", "生成后让用户确认再发送"],
        "data-viz": ["支持深色/浅色主题", "图表需有标题和图例", "支持响应式布局"],
        "weekly-summary": ["区分已完成和进行中", "风险项必须有应对措施", "篇幅控制在 1 页"],
        "code-review": ["区分严重/警告/建议三级", "每个问题给出修复示例", "不修改原文件"],
    }

    steps = steps_map.get(skill_id, ["1. 执行用户指定的任务"])
    constraints = constraints_map.get(skill_id, [])

    triggers_raw = market_item.get('triggers', [])
    triggers: list[str] = triggers_raw if isinstance(triggers_raw, list) else []
    md_content = f"""# {market_item['name']}

## 触发条件
{chr(10).join(triggers)}

## 执行步骤
{chr(10).join(steps)}

## 约束
{chr(10).join(f'- {c}' for c in constraints) if constraints else '- (无)'}
"""

    md_path = _os.path.join(skill_folder, "SKILL.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    return {"success": True, "message": f"Skill '{market_item['name']}' 安装成功", "skill_folder": skill_folder}


@app.websocket("/ws")
async def websocket_agent(websocket: WebSocket):
    """
    WebSocket 端点 — 接收用户消息，流式返回 Agent 每一步执行结果
    Step 7 改进：使用 astream_events 支持 Token 级流式输出
    """
    await websocket.accept()

    while True:
        try:
            data = await websocket.receive_text()
        except WebSocketDisconnect:
            break

        try:
            msg = json.loads(data)
        except json.JSONDecodeError:
            await websocket.send_json({"type": "error", "message": "无效的 JSON"})
            continue

        query = msg.get("query", "").strip()
        if not query:
            continue

        # 发送开始信号
        await websocket.send_json({"type": "start", "query": query})

        import uuid
        session_id = str(uuid.uuid4())[:8]
        config = {"configurable": {"thread_id": f"web-{session_id}"}}

        initial_state = {
            "user_input": query,
            "workspace_path": workspace_path,
            "session_id": session_id,
            "intent": "",
            "enriched_context": "",
            "matched_skill": None,
            "plan": [],
            "current_step": 0,
            "tool_results": [],
            "validation_passed": False,
            "validation_feedback": "",
            "retry_count": 0,
            "final_output": "",
            "output_files": [],
        }

        try:
            # ── Step 7：使用 astream_events 支持 Token 级流式 ──
            streaming_active = False
            async for event in graph.astream_events(initial_state, config, version="v2"):
                event_type = event.get("event", "")

                # Token 级别流式输出（LLM 逐 token 推送）
                if event_type == "on_chat_model_stream":
                    chunk = event["data"]["chunk"]
                    if hasattr(chunk, "content") and chunk.content:
                        if not streaming_active:
                            streaming_active = True
                            await websocket.send_json({"type": "stream_start"})
                        await websocket.send_json({
                            "type": "token",
                            "content": chunk.content
                        })

                # 节点级别更新（非 LLM 流式事件）
                elif event_type == "on_chain_end" and event.get("name") in NODE_NAMES:
                    node_name = event["name"]
                    node_output = event["data"].get("output", {})
                    if isinstance(node_output, dict):
                        await websocket.send_json({
                            "type": "node_update",
                            "node": node_name,
                            "data": _serialize_node_output(node_name, node_output),
                        })

            if streaming_active:
                await websocket.send_json({"type": "stream_end"})

        except Exception as e:
            await websocket.send_json({"type": "error", "message": str(e)})
            continue

        # 发送完成信号
        await websocket.send_json({"type": "done"})


def _serialize_node_output(node_name: str, output: dict) -> dict:
    """把节点输出转为 JSON 可序列化格式"""
    result = {}
    for k, v in output.items():
        if k == "messages":
            result[k] = [m.content if hasattr(m, "content") else str(m) for m in v[-3:]]
        elif isinstance(v, (str, int, float, bool, type(None))):
            result[k] = v
        elif isinstance(v, list):
            result[k] = v[:50] if len(v) > 50 else v
        elif isinstance(v, dict):
            result[k] = v
        else:
            result[k] = str(v)[:500]
    return result


# ─── 静态文件 ───────────────────────────────────────────────────

@app.get("/")
async def index():
    return FileResponse(os.path.join(os.path.dirname(__file__), "static", "index.html"))


# ─── 入口 ───────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="BAT Work Web Server (Step 7: +Streaming)")
    parser.add_argument("--port", type=int, default=6001, help="服务端口（默认 6001）")
    parser.add_argument("--host", default="0.0.0.0", help="监听地址")
    parser.add_argument("--api-key", help="LLM API Key")
    parser.add_argument("--base-url", help="LLM API 地址")
    parser.add_argument("--model", help="模型名")
    parser.add_argument("--workspace", default="./workspace", help="工作目录")
    parser.add_argument("--skills-dir", default="./skills", help="Skills 目录（Step 5）")

    args = parser.parse_args()

    global graph, workspace_path
    workspace_path = os.path.abspath(args.workspace)

    print("🚀 正在初始化 Agent Graph（含 Memory + Skill + Streaming）...")
    graph = create_graph(args)
    print(f"✅ Agent 就绪")
    print(f"📂 工作目录: {workspace_path}")
    print(f"🌐 启动 Web 服务: http://localhost:{args.port}")

    import uvicorn
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()

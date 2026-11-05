#!/usr/bin/env python3
"""
BAT Work Web Server — FastAPI 后端 + WebSocket 流式 Agent 执行 + 定时任务 + 多智能体协作

Step 9 新增：多智能体显性调度（5 Agent 协作），多智能体可视化页，
LLM/模拟双模式，含 Memory + Skill + Streaming + 深色/浅色主题

启动:
    python server.py --port 6001 --model qwen2.5:0.5b

    # 启用定时任务（自动加载 tasks.yaml）
    python server.py --port 6001 --model qwen2.5:0.5b --enable-scheduler

    # 自定义任务配置
    python server.py --port 6001 --model qwen2.5:0.5b --tasks-config ./my-tasks.yaml

    # 浏览器打开多智能体页面
    open http://localhost:6001/multi-agent
"""

from __future__ import annotations
import os
import sys
import json
import argparse
import asyncio
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from skill_loader import load_skills, Skill  # noqa: F401

# ── 飞书 Bot 适配器（可选）──
try:
    from feishu_bot import FeishuBotAdapter
    HAS_FEISHU = True
except ImportError:
    HAS_FEISHU = False
    FeishuBotAdapter = None  # type: ignore

# LangGraph 节点名称列表（用于 astream_events 过滤）
NODE_NAMES = {
    "understand_intent", "enrich_context", "plan_tasks",
    "execute_tool", "validate_result", "generate_output", "handle_error"
}

# ─── 多智能体全局变量（Step 9 新增）──────────────────────────

multi_agent_graph = None  # 多智能体图实例（模拟模式）
multi_agent_graph_llm = None  # 带 LLM 的图实例
multi_agent_llm = None  # 多智能体专用 LLM
multi_agent_llm_available = False  # LLM 是否就绪

AGENT_ROLES = {
    "orchestrator": {"name": "编排器", "emoji": "🎯", "color": "#7c5cfc"},
    "researcher": {"name": "研究员", "emoji": "🔍", "color": "#3b82f6"},
    "analyst": {"name": "分析师", "emoji": "📊", "color": "#f59e0b"},
    "writer": {"name": "写手", "emoji": "✍️", "color": "#22c55e"},
    "reviewer": {"name": "审阅官", "emoji": "🔎", "color": "#ef4444"},
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

app = FastAPI(title="BAT Work (Step 9: +Multi-Agent)")

# 全局 graph 和 scheduler 实例（启动时初始化）
graph: Any = None
workspace_path: str = ""
scheduler: Any = None  # Step 8 新增：TaskScheduler 实例


# ─── 多智能体初始化函数（Step 9 新增）──────────────────────────

def _init_multi_agent_llm():
    """初始化多智能体专用 LLM（DeepSeek 或 OpenAI 兼容 API）"""
    global multi_agent_llm, multi_agent_llm_available
    
    # 读取 API Key（优先级：命令行参数 > 环境变量）
    api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("DEEPSEEK_BASE_URL") or os.getenv("OPENAI_BASE_URL") or "https://api.deepseek.com/v1"
    model = os.getenv("LLM_MODEL") or "deepseek-chat"
    
    if not api_key:
        print("⚠️  未设置 DEEPSEEK_API_KEY 或 OPENAI_API_KEY，多智能体 LLM 模式不可用")
        return False
    
    try:
        import httpx
        from langchain_openai import ChatOpenAI
        http_client = httpx.Client(timeout=httpx.Timeout(300.0, connect=10.0), trust_env=False)
        multi_agent_llm = ChatOpenAI(
            model=model,
            api_key=api_key,
            base_url=base_url,
            temperature=0.7,
            http_client=http_client,
        )
        multi_agent_llm_available = True
        print(f"🤖 多智能体 LLM 已就绪: {model} @ {base_url}")
        return True
    except Exception as e:
        print(f"⚠️  多智能体 LLM 初始化失败: {e}")
        return False


def _ensure_multi_agent(use_llm: bool = False):
    """确保多智能体图已初始化
    Args:
        use_llm: 是否使用 LLM 驱动模式
    """
    global multi_agent_graph, multi_agent_graph_llm
    from multi_agent_graph import build_multi_agent_graph
    
    if use_llm:
        if multi_agent_graph_llm is None:
            multi_agent_graph_llm = build_multi_agent_graph(llm=multi_agent_llm)
        return multi_agent_graph_llm
    else:
        if multi_agent_graph is None:
            multi_agent_graph = build_multi_agent_graph(llm=None)
        return multi_agent_graph


# ─── 文件 API ──────────────────────────────────────────────────


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

## 触发条件：
{chr(10).join(f'- {t}' for t in triggers)}

## 执行步骤：
{chr(10).join(steps)}

## 约束：
{chr(10).join(f'- {c}' for c in constraints) if constraints else '- (无)'}
"""

    md_path = _os.path.join(skill_folder, "SKILL.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    return {"success": True, "message": f"Skill '{market_item['name']}' 安装成功", "skill_folder": skill_folder}


@app.post("/api/skills/reload")
async def reload_skills():
    """热重载 Skills 到运行中的 Agent Graph，无需重启服务"""
    import os as _os
    skills_dir = _os.path.join(_os.path.dirname(__file__), "skills")
    new_skills = load_skills(skills_dir)
    
    # 注入到 Agent 图（通过 nodes 模块更新）
    from nodes import set_skills
    set_skills(new_skills)
    
    return {
        "success": True,
        "message": f"已重载 {len(new_skills)} 个 Skill",
        "skills": [s.name for s in new_skills]
    }


@app.post("/api/skills/uninstall/{skill_id}")
async def uninstall_skill(skill_id: str):
    """卸载指定 Skill"""
    import os as _os
    import shutil
    skills_dir = _os.path.join(_os.path.dirname(__file__), "skills")
    skill_folder = _os.path.join(skills_dir, skill_id)
    
    if not _os.path.exists(skill_folder):
        return {"success": False, "error": f"Skill '{skill_id}' 未安装"}
    
    shutil.rmtree(skill_folder)
    
    # 热重载
    new_skills = load_skills(skills_dir)
    from nodes import set_skills
    set_skills(new_skills)
    
    return {"success": True, "message": f"Skill '{skill_id}' 已卸载", "remaining": len(new_skills)}


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

        query = msg.get("prompt", msg.get("query", "")).strip()
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
            last_state = None
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
                        last_state = node_output
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

        # 发送完成信号（携带产物信息）
        done_msg: Any = {"type": "done"}
        if last_state:
            done_msg["task"] = last_state.get("user_input", query)[:100]
            done_msg["final_output"] = last_state.get("final_output", "")[:2000]
            done_msg["output_files"] = last_state.get("output_files", [])
            # 构建产物列表
            products = []
            for f in done_msg["output_files"]:
                filepath = os.path.join(workspace_path, f) if not os.path.isabs(f) else f
                size = os.path.getsize(filepath) if os.path.exists(filepath) else 0
                products.append({"name": f, "path": filepath, "size": _format_size(size)})
            done_msg["products"] = products
        await websocket.send_json(done_msg)


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


def _format_size(b: int) -> str:
    if b < 1024:
        return f"{b}B"
    elif b < 1048576:
        return f"{b/1024:.1f}KB"
    return f"{b/1048576:.1f}MB"


# ─── 多智能体显性调度 API（Step 9 新增）─────────────────────────

@app.get("/api/multi-agent/llm-status")
async def get_multi_agent_llm_status():
    """返回多智能体 LLM 就绪状态（供前端判断是否显示 DeepSeek 开关）"""
    return {
        "llm_available": multi_agent_llm_available,
        "model": str(multi_agent_llm.model_name) if multi_agent_llm else "N/A",
    }


@app.get("/api/multi-agent/graph")
async def get_multi_agent_graph_def():
    """返回多智能体图结构定义（供前端可视化渲染）"""
    from multi_agent_graph import get_graph_definition
    return get_graph_definition()


@app.websocket("/ws/multi-agent")
async def ws_multi_agent(websocket: WebSocket):
    """多智能体 WebSocket — 流式展示 Agent 协作过程"""
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
        
        task = msg.get("task", "").strip()
        if not task:
            continue
        
        # 读取前端传来的 LLM 开关状态
        enable_llm = msg.get("enable_llm", False)
        if enable_llm and not multi_agent_llm_available:
            await websocket.send_json({"type": "error", "message": "LLM 未就绪，请设置 DEEPSEEK_API_KEY 后重启服务"})
            enable_llm = False
        
        mgraph = _ensure_multi_agent(use_llm=enable_llm)
        
        await websocket.send_json({
            "type": "start",
            "task": task,
            "mode": "llm" if enable_llm else "simulated",
        })
        
        import uuid
        sid = f"ma-{str(uuid.uuid4())[:6]}"
        config = {"configurable": {"thread_id": sid}}
        
        initial_state: dict = {
            "user_input": task,
            "enable_llm": enable_llm,
            "task_type": "",
            "research_result": "",
            "analysis_result": "",
            "draft": "",
            "review_feedback": "",
            "revision_count": 0,
            "final_output": "",
            "agent_trace": [],
            "current_agent": "",
        }
        
        try:
            async for event in mgraph.astream_events(initial_state, config, version="v2"):
                event_type = event.get("event", "")
                
                # 节点开始
                if event_type == "on_chain_start":
                    node_name = event.get("name", "")
                    if node_name in AGENT_ROLES:
                        await websocket.send_json({
                            "type": "agent_start",
                            "agent": node_name,
                            "role": AGENT_ROLES[node_name],
                        })
                
                # 节点结束
                elif event_type == "on_chain_end":
                    node_name = event.get("name", "")
                    output = event.get("data", {}).get("output", {})
                    if node_name in AGENT_ROLES and isinstance(output, dict):
                        trace_entries = output.get("agent_trace", [])
                        last_trace = trace_entries[-1] if trace_entries else {}
                        
                        await websocket.send_json({
                            "type": "agent_end",
                            "agent": node_name,
                            "role": AGENT_ROLES[node_name],
                            "output": last_trace.get("action", ""),
                            "state": {
                                "current_agent": output.get("current_agent", ""),
                                "task_type": output.get("task_type", ""),
                                "revision_count": output.get("revision_count", 0),
                            },
                        })
            
            await websocket.send_json({"type": "done", "session_id": sid})
            
        except Exception as e:
            await websocket.send_json({"type": "error", "message": str(e)})


# ─── Step 8: 定时任务 API ───────────────────────────────────────

scheduler = None  # type: ignore

@app.get("/api/scheduler/status")
async def get_scheduler_status():
    """返回调度器状态"""
    if scheduler is None:
        return {"running": False, "task_count": 0, "tasks": [], "message": "调度器未启用"}
    return scheduler.get_status()


@app.post("/api/scheduler/toggle/{task_name}")
async def toggle_task(task_name: str):
    """启用/禁用指定定时任务"""
    if scheduler is None:
        return {"success": False, "error": "调度器未启用"}
    for task in scheduler.tasks:
        if task.name == task_name:
            task.enabled = not task.enabled
            # 重启调度器以应用更改
            scheduler.stop()
            scheduler.start()
            return {"success": True, "name": task_name, "enabled": task.enabled}
    return {"success": False, "error": f"任务 '{task_name}' 不存在"}


@app.get("/api/scheduler/logs")
async def get_scheduler_logs(task_name: str = "", limit: int = 20):
    """返回定时任务执行日志"""
    log_dir = "./task_logs"
    if not os.path.exists(log_dir):
        return {"logs": [], "total": 0}
    
    files = sorted(
        [f for f in os.listdir(log_dir) if f.endswith(".json")],
        reverse=True
    )
    
    logs = []
    for fn in files[:limit]:
        filepath = os.path.join(log_dir, fn)
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                entry = json.load(f)
            # 按任务名过滤
            if task_name and entry.get("task", "") != task_name:
                continue
            logs.append(entry)
        except Exception:
            pass
    
    return {"logs": logs[:limit], "total": len(logs)}


@app.post("/api/scheduler/tasks")
async def create_task(payload: dict):
    """创建或更新定时任务，并持久化到 tasks.yaml"""
    if scheduler is None:
        return {"success": False, "error": "调度器未启用"}
    
    name = payload.get("name", "").strip()
    prompt = payload.get("prompt", "").strip()
    schedule = payload.get("schedule", "").strip()
    enabled = payload.get("enabled", True)
    
    if not name or not prompt or not schedule:
        return {"success": False, "error": "缺少必填字段: name, prompt, schedule"}
    
    from scheduler import ScheduledTask
    
    # 查找已有任务
    existing = None
    for t in scheduler.tasks:
        if t.name == name:
            existing = t
            break
    
    if existing:
        existing.prompt = prompt
        existing.schedule = schedule
        existing.enabled = enabled
        existing.last_run = None
        existing.last_result = ""
        existing.run_count = 0
    else:
        task = ScheduledTask(name=name, schedule=schedule, prompt=prompt, enabled=enabled)
        scheduler.tasks.append(task)
    
    # 持久化到 YAML
    _save_tasks_yaml(scheduler.tasks, args.tasks_config if 'args' in dir() else "./tasks.yaml")
    
    # 重启调度器
    scheduler.stop()
    scheduler.start()
    
    return {"success": True, "name": name, "action": "updated" if existing else "created"}


@app.delete("/api/scheduler/tasks/{task_name}")
async def delete_task(task_name: str):
    """删除定时任务"""
    if scheduler is None:
        return {"success": False, "error": "调度器未启用"}
    
    for i, t in enumerate(scheduler.tasks):
        if t.name == task_name:
            scheduler.tasks.pop(i)
            _save_tasks_yaml(scheduler.tasks, args.tasks_config if 'args' in dir() else "./tasks.yaml")
            scheduler.stop()
            scheduler.start()
            return {"success": True, "name": task_name, "action": "deleted"}
    
    return {"success": False, "error": f"任务 '{task_name}' 不存在"}


def _save_tasks_yaml(tasks, config_path: str):
    """将任务列表保存为 YAML 格式"""
    import yaml
    task_list = []
    for t in tasks:
        task_list.append({
            "name": t.name,
            "schedule": t.schedule,
            "prompt": t.prompt,
            "enabled": t.enabled,
        })
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump({"tasks": task_list}, f, allow_unicode=True, default_flow_style=False)


# ─── 飞书 Bot API ──────────────────────────────────────────────

feishu_bot = None  # type: ignore


@app.get("/api/feishu/status")
async def get_feishu_status():
    """返回飞书 Bot 状态"""
    if not HAS_FEISHU:
        return {"running": False, "message": "飞书 Bot 模块未安装（需要 httpx）"}
    if feishu_bot is None:
        return {"running": False, "message": "飞书 Bot 未启用（添加 --feishu-webhook-url 参数）"}
    return feishu_bot.get_status()


@app.post("/api/feishu/chat")
async def feishu_chat(payload: dict):
    """
    通过 HTTP 接收飞书消息并调用 Agent 处理（Demo 模式）
    
    POST body: {"text": "消息内容", "user_id": "xxx", "chat_id": "xxx"}
    返回: {"reply": "Agent 回复内容"}
    """
    if not HAS_FEISHU or feishu_bot is None:
        return {"success": False, "error": "飞书 Bot 未启用"}
    
    text = payload.get("text", "").strip()
    if not text:
        return {"success": False, "error": "消息为空"}
    
    try:
        result = await feishu_bot.process(payload)
        return {"success": True, "reply": result or "", "mode": "feishu"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.post("/api/feishu/send")
async def feishu_send(payload: dict):
    """
    直接发送消息到飞书群
    
    POST body: {"text": "消息内容", "title": "卡片标题（可选）"}
    """
    if not HAS_FEISHU or feishu_bot is None:
        return {"success": False, "error": "飞书 Bot 未启用"}
    
    text = payload.get("text", "")
    title = payload.get("title", "BAT Work 通知")
    chat_id = payload.get("chat_id", "")
    
    try:
        result = await feishu_bot.send_direct(text, chat_id=chat_id, title=title)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.post("/api/feishu/webhook")
async def feishu_webhook(payload: dict):
    """
    飞书 Outgoing Webhook 回调端点
    
    接收飞书真实回调格式，调用 Agent 处理后回复。
    需要通过 --feishu-webhook-url 配置 Webhook URL。
    """
    if not HAS_FEISHU or feishu_bot is None:
        return {"code": 1, "msg": "飞书 Bot 未启用"}
    
    try:
        result = await feishu_bot.process(payload)
        return {"code": 0, "msg": "ok", "reply": result or ""}
    except Exception as e:
        return {"code": 1, "msg": str(e)}


# ─── 静态文件 ───────────────────────────────────────────────────

@app.get("/")
async def index():
    return FileResponse(os.path.join(os.path.dirname(__file__), "static", "index.html"))


@app.get("/multi-agent")
async def multi_agent_page():
    """多智能体协作可视化页面（Step 9 新增）"""
    return FileResponse(os.path.join(os.path.dirname(__file__), "static", "multi-agent.html"))


# ─── 入口 ───────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="BAT Work Web Server (Step 9: +Multi-Agent)")
    parser.add_argument("--port", type=int, default=6001, help="服务端口（默认 6001）")
    parser.add_argument("--host", default="0.0.0.0", help="监听地址")
    parser.add_argument("--api-key", help="LLM API Key")
    parser.add_argument("--base-url", help="LLM API 地址")
    parser.add_argument("--model", help="模型名")
    parser.add_argument("--workspace", default="./workspace", help="工作目录")
    parser.add_argument("--skills-dir", default="./skills", help="Skills 目录（Step 5）")
    parser.add_argument("--enable-scheduler", action="store_true", help="Step 8: 启用定时任务调度器")
    parser.add_argument("--tasks-config", default="./tasks.yaml", help="Step 8: 任务配置文件路径")
    parser.add_argument("--feishu-webhook-url", default="", help="飞书 Bot Webhook URL")

    args = parser.parse_args()

    global graph, workspace_path, scheduler, feishu_bot
    workspace_path = os.path.abspath(args.workspace)

    print("🚀 正在初始化 Agent Graph（含 Memory + Skill + Streaming）...")
    graph = create_graph(args)
    print(f"✅ Agent 就绪")
    print(f"📂 工作目录: {workspace_path}")

    # Step 9: 初始化多智能体 LLM
    _init_multi_agent_llm()

    # Step 8: 初始化定时任务调度器
    if args.enable_scheduler:
        from scheduler import TaskScheduler
        scheduler = TaskScheduler(graph, workspace_path, log_dir=os.path.join(workspace_path, "..", "task_logs"))
        scheduler.load_tasks(args.tasks_config)
        scheduler.start()
        print(f"⏰ 调度器已启动，{len([t for t in scheduler.tasks if t.enabled])} 个活跃任务")
    else:
        print("ℹ️  定时任务未启用，使用 --enable-scheduler 开启")

    # 飞书 Bot 初始化
    global feishu_bot
    if HAS_FEISHU and args.feishu_webhook_url:
        feishu_bot = FeishuBotAdapter(webhook_url=args.feishu_webhook_url)

        # 设置 Agent 回调
        async def agent_handler(msg):
            import uuid
            sid = str(uuid.uuid4())[:8]
            config = {"configurable": {"thread_id": f"feishu-{sid}"}}
            state = {
                "user_input": msg.content,
                "workspace_path": workspace_path,
                "session_id": sid,
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
                result = await graph.ainvoke(state, config)
                return result.get("final_output", "处理完成，但无输出内容")
            except Exception as e:
                return f"❌ Agent 执行出错: {e}"
        
        feishu_bot.set_agent_handler(agent_handler)
        print(f"🤖 飞书 Bot 已启用: {args.feishu_webhook_url[:40]}...")
    elif args.feishu_webhook_url:
        print(f"⚠️  飞书 Bot 模块不可用（需要 pip install httpx）")

    print(f"🌐 启动 Web 服务: http://localhost:{args.port}")

    import uvicorn
    try:
        uvicorn.run(app, host=args.host, port=args.port, log_level="warning")
    finally:
        if scheduler:
            scheduler.stop()
            print("⏹️  调度器已停止")


if __name__ == "__main__":
    main()

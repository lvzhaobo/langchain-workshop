"""
工具注册表 — 提供 Agent 可调用的所有工具

每个工具是一个函数，接收 state 和可选参数，返回执行结果字符串。
"""

import os
import csv
import json
import subprocess
from datetime import datetime
from typing import Optional
from state import AgentState


# ── 工具注册表 ──
# 格式：{ 工具名: {"fn": callable, "description": str} }
TOOLS = {}


def register(name: str, description: str):
    """装饰器：注册工具"""
    def decorator(fn):
        TOOLS[name] = {"fn": fn, "description": description}
        return fn
    return decorator


def describe_all() -> str:
    """生成所有可用工具的描述文本，注入 LLM Prompt"""
    lines = []
    for name, meta in TOOLS.items():
        lines.append(f"- {name}: {meta['description']}")
    return "\n".join(lines)


def call_tool(name: str, state: AgentState, target: str = "") -> ToolResult:
    """执行指定的工具"""
    if name not in TOOLS:
        return {"step": state["current_step"], "action": name, "success": False, "output": f"未知工具: {name}"}

    try:
        fn = TOOLS[name]["fn"]
        output = fn(state, target)
        return {"step": state["current_step"], "action": name, "success": True, "output": output}
    except Exception as e:
        return {"step": state["current_step"], "action": name, "success": False, "output": f"工具执行异常: {str(e)}"}


# ══════════════════════════════════════════════
#  文件操作工具
# ══════════════════════════════════════════════

@register("list_files", "列出工作目录下的所有文件")
def tool_list_files(state: AgentState, target: str = "") -> str:
    ws = state["workspace_path"]
    files = os.listdir(ws)
    result = []
    for f in sorted(files):
        full = os.path.join(ws, f)
        if os.path.isfile(full):
            size = os.path.getsize(full)
            result.append(f"  📄 {f} ({size} bytes)")
        else:
            result.append(f"  📁 {f}/")
    return "\n".join(result) if result else "(空目录)"


@register("read_file", "读取工作目录中的文件内容。target 为文件名")
def tool_read_file(state: AgentState, target: str) -> str:
    filepath = os.path.join(state["workspace_path"], target)
    if not os.path.exists(filepath):
        return f"文件不存在: {target}"

    ext = os.path.splitext(target)[1].lower()

    if ext == ".csv":
        with open(filepath, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            rows = list(reader)
        # 返回前 50 行 + 摘要
        header = rows[0] if rows else []
        body = rows[1:51] if len(rows) > 1 else []
        summary = f"CSV 文件: {len(rows)-1} 行数据, 列: {header}"
        table = "\n".join([",".join(r) for r in [header] + body])
        return f"{summary}\n\n{table}"

    if ext in (".txt", ".md", ".py", ".json"):
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        if len(content) > 3000:
            content = content[:3000] + "\n...(内容截断)"
        return content

    return f"不支持的文件类型: {ext}"


@register("write_file", "将内容写入工作目录。target 格式: '文件名|内容'")
def tool_write_file(state: AgentState, target: str) -> str:
    parts = target.split("|", 1)
    if len(parts) != 2:
        return "错误: 格式应为 '文件名|内容'"
    filename, content = parts
    filepath = os.path.join(state["workspace_path"], filename.strip())
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content.strip())
    return f"已写入: {filename} ({len(content)} 字符)"


# ══════════════════════════════════════════════
#  数据分析工具
# ══════════════════════════════════════════════

@register("analyze_csv", "对 CSV 文件做统计分析。target 为文件名")
def tool_analyze_csv(state: AgentState, target: str) -> str:
    filepath = os.path.join(state["workspace_path"], target)
    if not os.path.exists(filepath):
        return f"文件不存在: {target}"

    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if not rows:
        return "文件为空"

    columns = list(rows[0].keys())
    numeric_cols = []
    for col in columns:
        try:
            float(rows[0][col].replace(",", ""))
            numeric_cols.append(col)
        except (ValueError, AttributeError):
            pass

    result = [f"分析 {target}: {len(rows)} 行, {len(columns)} 列"]
    result.append(f"数值列: {numeric_cols}")

    for col in numeric_cols:
        values = [float(r[col].replace(",", "")) for r in rows if r[col]]
        if values:
            result.append(f"  {col}: 合计={sum(values):,.0f}, 均值={sum(values)/len(values):,.0f}, 最大={max(values):,.0f}, 最小={min(values):,.0f}")

    # 如果有"区域"或类似列，做分组聚合
    group_col = None
    for c in ["区域", "月份", "产品", "品类"]:
        if c in columns:
            group_col = c
            break

    if group_col and numeric_cols:
        result.append(f"\n按 {group_col} 分组:")
        groups = {}
        for r in rows:
            key = r[group_col]
            if key not in groups:
                groups[key] = {nc: 0 for nc in numeric_cols}
            for nc in numeric_cols:
                groups[key][nc] += float(r[nc].replace(",", "")) if r[nc] else 0

        for key, vals in groups.items():
            detail = ", ".join([f"{nc}={vals[nc]:,.0f}" for nc in numeric_cols[:3]])
            result.append(f"  {key}: {detail}")

    return "\n".join(result)


@register("run_python", "执行一段 Python 代码（在沙箱中）。target 为 Python 代码")
def tool_run_python(state: AgentState, target: str) -> str:
    """在 workspace 目录执行 Python 代码"""
    script = target.strip()
    # 将 workspace 加入路径
    full_script = f"""
import os, sys, csv, json
os.chdir({repr(state['workspace_path'])})
{script}
"""
    try:
        proc = subprocess.run(
            ["python3", "-c", full_script],
            capture_output=True, text=True, timeout=30
        )
        output = proc.stdout
        if proc.stderr:
            output += f"\n[stderr]:\n{proc.stderr}"
        return output.strip() or "(执行完成，无输出)"
    except subprocess.TimeoutExpired:
        return "执行超时 (30秒)"
    except Exception as e:
        return f"执行异常: {str(e)}"


# ══════════════════════════════════════════════
#  报告生成工具
# ══════════════════════════════════════════════

@register("generate_report", "汇总执行结果，生成最终报告。target 为报告标题")
def tool_generate_report(state: AgentState, target: str) -> str:
    """把 tool_results 汇总为 Markdown 报告"""
    title = target or "任务报告"
    lines = [
        f"# {title}",
        f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## 任务意图",
        state.get("intent", ""),
        "",
        "## 执行过程",
    ]

    for i, tr in enumerate(state.get("tool_results", [])):
        status = "✅" if tr["success"] else "❌"
        lines.append(f"{i+1}. {status} **{tr['action']}** — {tr['output'][:200]}")

    lines.append("")
    lines.append("## 最终产物")
    lines.append(state.get("final_output", ""))

    report = "\n".join(lines)
    filepath = os.path.join(state["workspace_path"], f"{title}.md")
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(report)

    return f"报告已生成: {title}.md ({len(report)} 字符)"

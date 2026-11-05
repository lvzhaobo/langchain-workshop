"""
Step 2: 路由函数 — 仅一个分叉点（plan 后决定执行或生成）
"""

from state import AgentState


def route_after_plan(state: AgentState) -> str:
    plan = state.get("plan", [])
    if not plan:
        return "generate"
    print(f"  ↳ 开始执行 {len(plan)} 步任务")
    return "execute"

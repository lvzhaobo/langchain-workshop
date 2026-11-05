"""
路由函数 — 定义 LangGraph 中条件边的决策逻辑

三个关键分叉点：
1. plan_tasks 之后：有计划 → 执行 / 无计划 → 直接生成
2. execute_tool 之后：还有步骤 → 校验 / 超限 → 兜底
3. validate_result 之后：通过+还有 → 继续 / 通过+完成 → 生成 / 失败 → 重试或重新规划
"""

from state import AgentState

MAX_RETRIES = 3  # 单步最大重试次数


def route_after_plan(state: AgentState) -> str:
    """规划完成后，决定走向"""
    plan = state.get("plan", [])
    if not plan:
        # 简单问题，不需要工具，直接生成回复
        print("  ↳ 无需工具，直接生成回复")
        return "generate"
    print(f"  ↳ 开始执行 {len(plan)} 步任务")
    return "execute"


def route_after_execute(state: AgentState) -> str:
    """工具执行后，决定走向"""
    retry_count = state.get("retry_count", 0)

    if retry_count > MAX_RETRIES:
        print("  ↳ 重试超限，进入兜底处理")
        return "error"

    # 还有未执行的步骤？
    if state["current_step"] < len(state.get("plan", [])):
        return "validate"
    else:
        # 全部执行完毕
        return "validate"


def route_after_validate(state: AgentState) -> str:
    """校验完成后，决定走向"""
    if state.get("validation_passed"):
        # 校验通过
        if state["current_step"] < len(state.get("plan", [])):
            print("  ↳ ✅ 校验通过，继续下一步")
            return "continue"
        else:
            print("  ↳ ✅ 全部步骤完成，生成产物")
            return "generate"
    else:
        # 校验失败
        retry_count = state.get("retry_count", 0)
        if retry_count < 2:
            print(f"  ↳ ❌ 校验失败，重试当前步骤 (第{retry_count+1}次)")
            return "retry"
        else:
            print(f"  ↳ ❌ 多次失败，重新规划")
            return "replan"

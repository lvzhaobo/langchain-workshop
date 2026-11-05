"""Tool 设计规范 — docstring 怎么写 LLM 才选得准

对比实验：同一个问题，"坏工具" vs "好工具"，Agent 调用准确率差多少。

运行：
  python tool_design.py           # 交互模式，逐个对比
  python tool_design.py --quick   # 只跑一句话结论

依赖：pip install langchain langchain-openai requests

前置实验：1.4 LangChain 智能体（必须先理解 @tool）
"""
import os
import sys
import time
from dotenv import load_dotenv

load_dotenv()

# — 尝试导入 LangChain —
try:
    from langchain_core.tools import tool
    from langchain_core.messages import SystemMessage, HumanMessage
    from langchain_openai import ChatOpenAI
except ImportError:
    print("❌ 请先安装：pip install langchain langchain-openai")
    sys.exit(1)


# ============================================================
# ① 坏工具 vs 好工具：同一个功能，docstring 天差地别
# ============================================================

# --- 坏工具：docstring 太随意 ---
@tool
def bad_query_device(device: str):
    """查设备"""
    return f"设备 {device}：温度 75°C，电压 48V，CPU 82%，内存 71%"


# --- 好工具：docstring 写清参数、返回、使用场景 ---
@tool
def good_query_device(device_id: str) -> str:
    """查询 5G 基站的实时运行指标（温度、电压、CPU、内存、接入用户数）。

    参数：
        device_id：设备编号，格式如 DEV-0001、ENB-HW-001

    返回：
        包含温度(°C)、电压(V)、CPU使用率(%)、内存使用率(%)、接入用户数 的汇总字符串。
        如果设备不存在，返回 "DEVICE_NOT_FOUND"。

    使用场景：
        当用户询问某个设备「状态」「运行情况」「负载」时调用此工具。
    """
    return f"设备 {device_id}：温度 75°C，电压 48V，CPU 82%，内存 71%，接入用户 218"


# ============================================================
# ② 坏工具：参数模糊 + 返回不可解析
# ============================================================

@tool
def bad_query_alarms(device: str):
    """查告警"""
    return f"P0 退服 P1 性能 P2 配置错误"


@tool
def good_query_alarms(device_id: str, severity: str = "") -> str:
    """查询设备的活跃告警列表，支持按严重级别筛选。

    参数：
        device_id：设备编号，格式如 DEV-0001、ENB-HW-001
        severity：可选，筛选 P0 / P1 / P2 / P3，留空返回全部

    返回：
        每行一条告警，格式：[级别] 类型 — 描述。无告警时返回 "NO_ALARMS"。

    使用场景：
        「这个设备有什么告警」「查一下 P0 级别的」「活跃异常有哪些」
    """
    return (
        "[P0] 基站退服 — 小区服务能力丧失\n"
        "[P1] 性能劣化 — 接入成功率降至 85%\n"
        "[P2] 传输中断 — 光模块收光功率异常"
    )


# ============================================================
# ③ 坏工具：返回值是"人话"但机器没法用
# ============================================================

@tool
def bad_recommend_action(device: str) -> str:
    """给你处置建议"""
    return "建议先看看光模块是不是松了，然后重启一下AAU，实在不行就换一个新的"


@tool
def good_recommend_action(device_id: str, diagnosis: str) -> str:
    """根据诊断结论给出结构化的处置建议，按优先级排列。

    参数：
        device_id：设备编号
        diagnosis：诊断结论摘要，如「光模块收光功率-28dBm」

    返回：
        JSON 格式，包含 steps 数组（按优先级排列，每项含 action、estimated_time、risk_level）：
        {
          "steps": [
            {"step": 1, "action": "…", "estimated_time": "5min", "risk": "低"},
            ...
          ]
        }

    使用场景：
        Agent 完成诊断后调用此工具，获取可执行的处置步骤列表。
    """
    import json
    return json.dumps({
        "device_id": device_id,
        "steps": [
            {"step": 1, "action": "远程复位光模块", "estimated_time": "5min", "risk": "低"},
            {"step": 2, "action": "切换备用链路", "estimated_time": "3min", "risk": "中"},
            {"step": 3, "action": "现场更换光模块", "estimated_time": "2h", "risk": "高"},
        ]
    }, ensure_ascii=False)


# ============================================================
# ④ 实验对比：坏 vs 好，LLM 选哪个？
# ============================================================

BAD_TOOLS = [bad_query_device, bad_query_alarms, bad_recommend_action]
GOOD_TOOLS = [good_query_device, good_query_alarms, good_recommend_action]

# 测试问题集
TEST_QUESTIONS = [
    "DEV-0001 现在状态如何？温度高不高？",
    "ENB-HW-001 有什么告警？只看 P0 级别的",
    "光模块老化导致退服了，DEV-0001 怎么处理？",
]


def run_comparison(label: str, tools: list, questions: list, quick: bool = False):
    """跑对比实验：同一个 LLM + 同一个问题，只是工具不同。"""
    llm = ChatOpenAI(
        model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
        api_key=os.getenv("DEEPSEEK_API_KEY"),
        base_url=os.getenv("DEEPSEEK_BASE_URL"),
        temperature=0,  # 固定温度 0，排除随机性
    ).bind_tools(tools)

    tool_names = [t.name for t in tools]

    print(f"\n{'='*60}")
    print(f"  🧪 {label}")
    print(f"  工具清单: {tool_names}")
    print(f"{'='*60}")

    for q in questions:
        print(f"\n  💬 问题: {q}")
        if quick:
            print("     ⏳ 调用中...", end=" ", flush=True)

        result = llm.invoke([
            SystemMessage(content="你是运维助手。根据问题决定调哪个工具。"),
            HumanMessage(content=q),
        ])

        tool_calls = getattr(result, "tool_calls", None) or []
        if tool_calls:
            tc = tool_calls[0]
            print(f"→ 调用了 [{tc['name']}]({tc.get('args', {})})")
            # 执行工具看结果
            for t in tools:
                if t.name == tc["name"]:
                    output = str(t.invoke(tc.get("args", {})))
                    print(f"→ 输出: {output[:120]}{'…' if len(output)>120 else ''}")
                    break
        else:
            print(f"→ 未调用工具，直接回复: {str(result.content)[:100]}")


def run_quick():
    """快速版：只对比关键差异"""
    print("\n" + "="*70)
    print("  Tool 设计规范 · 快速对比")
    print("  同一个 LLM · 同一组问题 · 唯一变量是 docstring")
    print("="*70)
    run_comparison("❌ 坏工具：docstring 随意", BAD_TOOLS, TEST_QUESTIONS, quick=True)
    print("\n  ═══════════════════════════════════")
    run_comparison("✅ 好工具：docstring 规范", GOOD_TOOLS, TEST_QUESTIONS, quick=True)
    print("\n" + "="*70)
    print("  📋 三条铁律")
    print("  ① docstring 写清「参数、返回、使用场景」——LLM 靠它决策")
    print("  ② 返回值尽量结构化（JSON/表格）——前端和下游要消费")
    print("  ③ 参数名有区分度（device_id 不是 device）——避免歧义")
    print("="*70)


def run_full():
    """完整版：逐个讲解"""
    print("\n" + "="*70)
    print("  实验 1.4b：Tool 设计规范")
    print("  1.4 让你写出了第一个 @tool，本实验教你把它写好")
    print("="*70)

    # Part 1: 坏工具
    print("\n  ┌─────────────────────────────────────────┐")
    print("  │  Part 1：坏工具长什么样                  │")
    print("  └─────────────────────────────────────────┘")
    print(f"""
  坏工具 ① — docstring 只写了「查设备」
     LLM 不知道它返回什么、参数格式是什么、什么时候该用
     结果：该调的时候不调，不该调的时候乱调

  坏工具 ② — 参数模糊
     device vs device_id：一字之差，LLM 可能传错值
     severity 没有默认值说明 → LLM 传空字符串 vs 不传 行为不一致

  坏工具 ③ — 返回值不可解析
     返回「建议先看看光模块…」这样的自然语言
     前端没法渲染结构化卡片，下游系统没法消费""")

    # Part 2: 好工具
    print("\n  ┌─────────────────────────────────────────┐")
    print("  │  Part 2：好工具的三要素                  │")
    print("  └─────────────────────────────────────────┘")
    print(f"""
  ① 描述三件套：参数（类型+格式+示例）、返回值（格式+含义）、使用场景（什么时候调用）

  ② 参数设计原则：
     · 必填参数放前面，可选参数给默认值
     · 参数名有区分度（device_id vs device、alarm_severity vs level）
     · 用类型注解（: str, : int）让 LLM 更准确

  ③ 返回值设计原则：
     · 结构化（JSON）＞ 表格（Markdown）＞ 自由文本
     · 失败状态统一（404 → "NOT_FOUND"，无数据 → "NO_DATA"）
     · 别把多种信息混在一个工具返回里——一个工具只做一件事""")

    # Part 3: 跑对比
    print("\n  ┌─────────────────────────────────────────┐")
    print("  │  Part 3：实测对比                        │")
    print("  └─────────────────────────────────────────┘")

    run_comparison("❌ 坏工具", BAD_TOOLS, TEST_QUESTIONS)
    print("\n  ═══════════════════════════════════")
    run_comparison("✅ 好工具", GOOD_TOOLS, TEST_QUESTIONS)

    # Part 4: 实战练习
    print(f"""
  ┌─────────────────────────────────────────┐
  │  💪 动手：改造你的 1.4 @tool             │
  └─────────────────────────────────────────┘

  回到 1.4 的 agent_langchain.py，检查你的三个工具：
  ① query_object     → docstring 写全了吗？参数说明清楚吗？
  ② query_events     → 无告警时返回什么？LLM 知道吗？
  ③ list_objects     → 返回格式是结构化还是自由文本？

  改完后跑 1.4 的验证 curl，对比改前改后的差异：
  · Agent 是不是更少选错工具？
  · 工具调用参数是不是更准确？
  · 前端的输出是不是更能被渲染成卡片？
""")


if __name__ == "__main__":
    if not os.getenv("DEEPSEEK_API_KEY"):
        print("❌ 请先配置 .env 中的 DEEPSEEK_API_KEY")
        sys.exit(1)

    if "--quick" in sys.argv:
        run_quick()
    else:
        run_full()

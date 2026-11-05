"""
实验一：ReAct Agent 基础 — 工具定义 + Agent 创建 + ReAct 循环观察

核心概念：
  - @tool 装饰器：把普通 Python 函数变成 Agent 可调用的工具
  - create_react_agent：组装 LLM + 工具 → Agent
  - ReAct 循环：思考(Think) → 行动(Act) → 观察(Observe) → 再思考...

运行方式：
  python 01-agent-basic/agent_basic.py            # 正常模式（需要百炼 API）
  python 01-agent-basic/agent_basic.py --offline  # 离线模式（纯本地运行）

前置条件：
  export DASHSCOPE_API_KEY=你的百炼Key   # 仅正常模式需要
  pip install langchain langchain-openai langgraph  # 仅正常模式需要
"""

import json
import os
import sys
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent


# ---------------------------------------------------------------------------
# 离线模式
# ---------------------------------------------------------------------------

def _offline() -> bool:
    return "--offline" in sys.argv


OFFLINE = _offline()

if not OFFLINE:
    from langchain_core.tools import tool


# ---------------------------------------------------------------------------
# 数据加载（线上线下共用）
# ---------------------------------------------------------------------------

def load_equipment_data():
    with open(DATA_DIR / "equipment_data.json", "r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# 工具定义
# ---------------------------------------------------------------------------

if not OFFLINE:
    @tool
    def search_equipment(keyword: str) -> str:
        """搜索电力设备。输入设备名称、编号、类型或区域的任意关键词，返回匹配的设备列表。"""
        equipments = load_equipment_data()
        keyword_lower = keyword.lower()
        results = []
        for eq in equipments:
            if (keyword_lower in eq["name"].lower()
                or keyword_lower in eq["id"].lower()
                or keyword_lower in eq["type"].lower()
                or keyword_lower in eq["region"].lower()):
                results.append(eq)
        if not results:
            return f"未找到匹配 '{keyword}' 的设备"
        return json.dumps(results, ensure_ascii=False, indent=2)

    @tool
    def get_equipment_detail(device_id: str) -> str:
        """根据设备编号获取一台设备的完整信息，包括安装日期、制造商、容量、冷却方式。"""
        equipments = load_equipment_data()
        for eq in equipments:
            if eq["id"].upper() == device_id.upper():
                return json.dumps(eq, ensure_ascii=False, indent=2)
        return f"未找到编号为 '{device_id}' 的设备"


def search_equipment_sync(keyword: str) -> str:
    """离线模式下的搜索工具（纯函数，不需要 @tool 装饰器）"""
    equipments = load_equipment_data()
    keyword_lower = keyword.lower()
    results = []
    for eq in equipments:
        if (keyword_lower in eq["name"].lower()
            or keyword_lower in eq["id"].lower()
            or keyword_lower in eq["type"].lower()
            or keyword_lower in eq["region"].lower()):
            results.append(eq)
    if not results:
        return f"未找到匹配 '{keyword}' 的设备"
    return json.dumps(results, ensure_ascii=False, indent=2)


def get_equipment_detail_sync(device_id: str) -> str:
    """离线模式下的详情工具"""
    equipments = load_equipment_data()
    for eq in equipments:
        if eq["id"].upper() == device_id.upper():
            return json.dumps(eq, ensure_ascii=False, indent=2)
    return f"未找到编号为 '{device_id}' 的设备"


# ---------------------------------------------------------------------------
# 在线模式：真实 Agent
# ---------------------------------------------------------------------------

if not OFFLINE:
    from openai import OpenAI

    DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "")
    BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    MODEL = "qwen-plus"

    TOOLS = [{
        "type": "function",
        "function": {
            "name": "search_equipment",
            "description": "搜索电力设备。输入设备名称、编号、类型或区域的任意关键词。",
            "parameters": {"type": "object", "properties": {"keyword": {"type": "string"}}, "required": ["keyword"]}
        }
    }, {
        "type": "function",
        "function": {
            "name": "get_equipment_detail",
            "description": "根据设备编号获取设备的完整信息。",
            "parameters": {"type": "object", "properties": {"device_id": {"type": "string"}}, "required": ["device_id"]}
        }
    }]

    TOOL_MAP = {
        "search_equipment": lambda **a: search_equipment.invoke(a["keyword"]),
        "get_equipment_detail": lambda **a: get_equipment_detail.invoke(a["device_id"]),
    }

    def run_online():
        if not DASHSCOPE_API_KEY:
            print("\n⚠️  请先设置环境变量 DASHSCOPE_API_KEY 或使用 --offline"); sys.exit(1)
        client = OpenAI(base_url=BASE_URL, api_key=DASHSCOPE_API_KEY)

        print("\n📋 [1/4] 设备数据加载测试...")
        data = load_equipment_data()
        print(f"   ✅ 共加载 {len(data)} 台设备")

        print("\n🔍 [2/4] 工具自测...")
        result = search_equipment.invoke("变压器")
        count = len(json.loads(result))
        print(f"   ✅ search_equipment('变压器') → {count} 条结果")

        # ReAct 循环
        print("\n🧠 [3/4] 手动 ReAct 循环...")
        question = "#1 主变压器最后一次巡检是谁做的？巡检日期是哪天？"
        print(f"   ❓ 问题：{question}\n")
        messages = [{"role": "user", "content": question}]
        for turn in range(5):
            resp = client.chat.completions.create(model=MODEL, messages=messages, tools=TOOLS, temperature=0)
            msg = resp.choices[0].message
            if msg.tool_calls:
                for tc in msg.tool_calls:
                    func = TOOL_MAP.get(tc.function.name)
                    args = json.loads(tc.function.arguments)
                    result = func(**args) if func else "未知工具"
                    print(f"   🔧 {tc.function.name}({args}) → {str(result)[:80]}...")
                    messages.append({"role": "assistant", "tool_calls": [tc.model_dump()]})
                    messages.append({"role": "tool", "tool_call_id": tc.id, "content": str(result)})
            else:
                print(f"   💬 最终回答：{msg.content}")
                break
        else:
            print("   ⚠️ 达到最大轮次")

        # LLM vs Agent 对比
        print("\n📊 [4/4] 对比实验：单次 LLM vs Agent...")
        questions = [
            "天河区有哪些设备？把它们的名称和状态列出来。",
            "EP-D-002 的当前状态和巡检人是谁？",
        ]
        for q in questions:
            print(f"\n{'─'*50}")
            print(f"   ❓ 问题：{q}")
            llm_result = client.chat.completions.create(model=MODEL, messages=[{"role": "user", "content": q}], temperature=0)
            print(f"   📝 单次 LLM（无工具）：{llm_result.choices[0].message.content[:200]}")
            # Agent 模式：复用上面的 ReAct 循环逻辑
            messages = [{"role": "user", "content": q}]
            for turn in range(5):
                resp = client.chat.completions.create(model=MODEL, messages=messages, tools=TOOLS, temperature=0)
                msg = resp.choices[0].message
                if msg.tool_calls:
                    for tc in msg.tool_calls:
                        func = TOOL_MAP.get(tc.function.name)
                        args = json.loads(tc.function.arguments)
                        result = func(**args) if func else "?"
                        messages.append({"role": "assistant", "tool_calls": [tc.model_dump()]})
                        messages.append({"role": "tool", "tool_call_id": tc.id, "content": str(result)})
                else:
                    print(f"   🤖 Agent（可调工具）：{msg.content[:200]}")
                    break


# ---------------------------------------------------------------------------
# 离线模式：模拟 ReAct 循环
# ---------------------------------------------------------------------------

def offline_demo():
    """离线演示：用纯 Python 模拟 ReAct 循环全过程

    每一步都实际调用工具函数（查 JSON 文件），
    只是 LLM 的"思考"和"回答"用本地模拟代替。
    数据流 100% 真实：搜索 → 拿到数据 → 组织回答。
    """
    print("\n📋 [1/4] 设备数据加载测试...")
    data = load_equipment_data()
    print(f"   ✅ 共加载 {len(data)} 台设备")

    print("\n🔍 [2/4] 工具自测...")
    result = search_equipment_sync("变压器")
    count = len(json.loads(result))
    print(f"   ✅ search_equipment('变压器') → {count} 条结果")
    result = get_equipment_detail_sync("EP-D-002")
    detail = json.loads(result)
    print(f"   ✅ get_equipment_detail('EP-D-002') → {detail['name']}，状态={detail['status']}")

    # ===== 模拟 ReAct 循环 =====
    print("\n🧠 [3/4] 模拟 ReAct 循环...")
    print("""
   ┌─ ReAct 循环（模拟）──────────────────────────────┐
   │                                                    │
   │  Step 1 💭 Think：用户问"#1主变压器最后一次巡检"   │
   │         → AI 判断需要查设备数据                     │
   │                                                    │
   │  Step 2 🔧 Act：调用 search_equipment("#1主变压器") │""")

    # 实际调用工具！（用设备编号确保精确匹配）
    search_result = search_equipment_sync("EP-B-001")
    try:
        devices = json.loads(search_result)
    except json.JSONDecodeError:
        devices = []
    ep_b_001 = devices[0] if devices else {}
    print(f"   │         → 找到设备：{ep_b_001.get('name')} ({ep_b_001.get('id')})    │")
    print(f"""   │                                                    │
   │  Step 3 📥 Observe：拿到设备数据                     │
   │         → 巡检人={ep_b_001.get('checker')}，日期={ep_b_001.get('lastCheck')}                  │
   │                                                    │
   │  Step 4 💭 Think Again：信息够了，组织回答           │
   │                                                    │
   │  Step 5 💬 Answer（模拟 LLM 生成）：                 │
   │    "#1 主变压器（EP-B-001）最近一次巡检是           │
   │     {ep_b_001.get('checker')}在 {ep_b_001.get('lastCheck')} 完成的，           │
   │     当前设备状态为{ep_b_001.get('status')}。"                   │
   └────────────────────────────────────────────────────┘""")

    # ===== LLM vs Agent 对比 =====
    print("\n📊 [4/4] 对比实验：单次 LLM vs Agent（模拟）...")

    test_cases = [
        ("天河区有哪些设备？", "天河区"),
        ("EP-D-002 的当前状态和巡检人是谁？", "EP-D-002"),
    ]

    for question, keyword in test_cases:
        print(f"\n{'─'*50}")
        print(f"   ❓ 问题：{question}")

        # 模拟 LLM 直接回答（无工具）
        print(f"   📝 单次 LLM（无工具）：")
        print(f"      [模拟] 抱歉，我没有这些设备的实时数据，无法准确回答。")

        # 模拟 Agent（有工具）
        print(f"   🤖 Agent（可调工具）：")
        print(f"      🔧 Step 1: 调用 search_equipment('{keyword}')")
        tool_result = search_equipment_sync(keyword)
        matches = json.loads(tool_result)
        if isinstance(matches, list) and matches:
            item = matches[0]
            print(f"      📥 拿到数据：{item.get('name', '')} → 状态={item.get('status', '')}，巡检人={item.get('checker', '')}，日期={item.get('lastCheck', '')}")
            print(f"      💬 最终回答（模拟 LLM 生成）：{item.get('name')}当前状态为{item.get('status')}，最近巡检由{item.get('checker')}在{item.get('lastCheck')}完成。")
        else:
            print(f"      📥 搜索结果：{tool_result[:100]}")


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------

def main():
    print("=" * 60)
    if OFFLINE:
        print("🧪 实验一：ReAct Agent 基础 [离线模式]")
        print("=" * 60)
        print("\n  ⚡ 离线模式：所有 LLM 调用用本地模拟代替")
        print("  ⚡ 工具调用（查 JSON 文件）仍然真实执行")
        print("  ⚡ 去掉 --offline 参数即可使用真实百炼 API\n")
        offline_demo()
    else:
        print("🧪 实验一：ReAct Agent 基础")
        print("=" * 60)
        run_online()

    print("\n" + "=" * 60)
    print("🎉 实验一完成！")
    print("=" * 60)


if __name__ == "__main__":
    main()

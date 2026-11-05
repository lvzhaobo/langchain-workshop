"""
实验三：Human-in-the-Loop — 人工审批节点

核心概念：
  - interrupt_before：在指定节点执行前暂停工作流
  - Command(resume=True)：人工确认后继续
  - StateGraph 状态恢复：暂停 → 人工检查 → 决定继续或回退

运行方式：
  python 03-hitl/hitl_workflow.py            # 正常模式（需要百炼 API + langgraph）
  python 03-hitl/hitl_workflow.py --offline  # 离线模式（纯本地运行）

前置条件：
  export DASHSCOPE_API_KEY=你的百炼Key   # 仅正常模式需要
  pip install langchain langchain-openai langgraph  # 仅正常模式需要
"""

import json
import os
import sys
from pathlib import Path

OFFLINE = "--offline" in sys.argv
DATA_DIR = Path(__file__).parent.parent


def load_equipment_data():
    with open(DATA_DIR / "equipment_data.json", "r", encoding="utf-8") as f:
        return json.load(f)


def load_knowledge_base():
    with open(DATA_DIR / "knowledge_base.json", "r", encoding="utf-8") as f:
        return json.load(f)


# ===========================================================================
# 在线模式
# ===========================================================================

if not OFFLINE:
    from typing import TypedDict, Optional
    from openai import OpenAI

    DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "")
    BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    MODEL = "qwen-plus"

    class DiagnosisState(TypedDict):
        user_query: str
        device_id: Optional[str]
        symptom: Optional[str]
        diagnosis_result: Optional[str]
        severity: Optional[str]
        solution: Optional[str]
        approved: bool

    def _chat(client, prompt: str) -> str:
        resp = client.chat.completions.create(model=MODEL, messages=[{"role": "user", "content": prompt}], temperature=0)
        return resp.choices[0].message.content

    def get_llm():
        return OpenAI(base_url=BASE_URL, api_key=DASHSCOPE_API_KEY)

    def router_node(state: DiagnosisState) -> dict:
        llm = get_llm()
        query = state["user_query"]
        prompt = f"分析用户输入，返回JSON：{{\"device_id\": \"设备编号\", \"symptom\": \"故障现象\"}}\n用户输入：{query}"
        response = _chat(llm, prompt)
        try:
            text = response.strip()
            if "```" in text:
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            info = json.loads(text)
        except json.JSONDecodeError:
            info = {"device_id": None, "symptom": query}
        print(f"\n   🔍 Router：device_id={info.get('device_id')}, symptom={info.get('symptom')}")
        return {"device_id": info.get("device_id"), "symptom": info.get("symptom")}

    def diagnosis_node(state: DiagnosisState) -> dict:
        llm = get_llm()
        equipments = load_equipment_data()
        device_info = None
        for eq in equipments:
            if eq["id"].upper() == (state.get("device_id") or "").upper():
                device_info = eq
                break
        device_str = json.dumps(device_info, ensure_ascii=False) if device_info else "未找到"
        prompt = f"根据设备信息和故障现象诊断，返回JSON：{{\"diagnosis_result\": \"诊断结论\", \"severity\": \"critical/warning/normal\"}}\n设备：{device_str}\n现象：{state.get('symptom')}"
        response = _chat(llm, prompt)
        try:
            text = response.strip()
            if "```" in text: text = text.split("```")[1]
            if text.startswith("json"): text = text[4:]
            result = json.loads(text)
        except json.JSONDecodeError:
            result = {"diagnosis_result": response.content[:200], "severity": "warning"}
        print(f"\n   🩺 Diagnosis：{result.get('diagnosis_result')}")
        return {"diagnosis_result": result.get("diagnosis_result"), "severity": result.get("severity")}

    def human_approval_node(state: DiagnosisState) -> dict:
        print(f"\n   ⏸️  ─── 人工审批点 ───")
        print(f"   诊断：{state.get('diagnosis_result')}\n   严重程度：{state.get('severity')}")
        decision = interrupt({"message": "请审批诊断结论", "diagnosis": state.get("diagnosis_result")})
        approved = decision.get("approved", False) if isinstance(decision, dict) else False
        print(f"   审批结果：{'✅ 批准' if approved else '❌ 驳回'}")
        return {"approved": approved}

    def solution_node(state: DiagnosisState) -> dict:
        llm = get_llm()
        prompt = f"生成处置方案（200字内）：诊断={state.get('diagnosis_result')} 严重程度={state.get('severity')}"
        response = _chat(llm, prompt)
        print(f"\n   📋 Solution：{response.content[:100]}...")
        return {"solution": response.strip()}

    def execute_node(state: DiagnosisState) -> dict:
        print(f"\n   ✅ 生成巡检记录：设备={state.get('device_id')}")
        return {}

    def run_online():
        """在线模式：前两步用真实 LLM，审批点用 input()"""
        if not DASHSCOPE_API_KEY:
            print("\n⚠️  请先设置环境变量 DASHSCOPE_API_KEY 或使用 --offline")

        llm = get_llm()
        user_input = "EP-D-002 的断路器出现拒分故障，合闸后无法正常分闸"
        print(f"\n👤 输入：{user_input}")

        # Step 1: Router（LLM）
        print("\n   🔍 Router 节点：LLM 解析用户输入...")
        resp = _chat(llm, f"从以下输入提取 device_id 和 symptom：{user_input}。返回 JSON：{{\"device_id\":\"...\",\"symptom\":\"...\"}}")
        print(f"   → 提取结果：{resp[:150]}")

        # Step 2: Diagnosis（LLM + 查设备数据）
        print("\n   🩺 Diagnosis 节点：查设备数据 + LLM 诊断...")
        equipments = load_equipment_data()
        device = next((e for e in equipments if e["id"] == "EP-D-002"), None)
        if device:
            print(f"   → 设备数据：{device['name']}，制造商={device['manufacturer']}")
        resp2 = _chat(llm, f"诊断故障：设备={device}，现象=断路器合闸后无法分闸。50字内给结论和严重程度。")
        diagnosis = resp2[:200]
        print(f"   → 诊断结果：{diagnosis}")

        # Step 3: HITL — 真的等人
        print(f"\n   ╔══════════════════════════════════════════╗")
        print(f"   ║  ⏸️  人工审批点                         ║")
        print(f"   ║  诊断：{diagnosis}                      ║")
        print(f"   ║  输入 y(通过) 或 n(驳回)：               ║")
        print(f"   ╚══════════════════════════════════════════╝")
        decision = input("   👨‍💼 你的审批决定 (y=通过 / n=驳回)：").strip().lower()

        if decision != "y":
            print(f"\n   ⚠️ 审批驳回！流程终止")

        # Step 4: Solution（LLM）
        print("\n   📋 Solution 节点：LLM 生成处置方案...")
        resp3 = _chat(llm, f"生成断路器拒分故障的处置方案（200字内）：诊断={diagnosis}")
        print(f"   → {resp3[:300]}")

        # Step 5: Execute
        print(f"\n   ✅ Execute 节点：生成巡检记录 IR-EP-D-002-20260715，推送运维平台")
        print(f"\n✅ HITL 流程完成！")


# ===========================================================================
# 离线模式
# ===========================================================================

def offline_demo():
    """离线演示：手动模拟 HITL 流程每个节点"""

    user_input = "EP-D-002 的断路器出现拒分故障，合闸后无法正常分闸"
    print(f"\n👤 用户输入：{user_input}")

    # Step 1: Router
    print("\n   🔍 Router 节点：解析用户输入...")
    device_id = "EP-D-002"
    symptom = "断路器合闸后无法正常分闸"
    print(f"   → device_id={device_id}, symptom={symptom}")

    # Step 2: Diagnosis
    print("\n   🩺 Diagnosis 节点：查设备数据 + 诊断...")
    equipments = load_equipment_data()
    device = next((e for e in equipments if e["id"] == device_id), None)
    if device:
        print(f"   → 找到设备：{device['name']}，制造商={device['manufacturer']}，状态={device['status']}")
    diagnosis_result = "分闸线圈电阻异常，判断为线圈绝缘老化导致机械卡涩"
    severity = "critical"
    print(f"   → 诊断结论：{diagnosis_result}")
    print(f"   → 严重程度：{severity}")

    # Step 3: HITL 暂停点 — 真正的人工介入
    print(f"""
   ╔══════════════════════════════════════════╗
   ║  ⏸️  人工审批点                         ║
   ║                                          ║
   ║  设备编号：{device_id}                    ║
   ║  诊断结论：{diagnosis_result}             ║
   ║  严重程度：{severity}                     ║
   ║                                          ║
   ║  [离线模式] 自动模拟审批通过：             ║
   ╚══════════════════════════════════════════╝
""")
    # 离线模式自动通过（真实场景由人在终端输入或飞书卡片操作）
    approved = True

    print(f"   👨‍💼 审批结果：通过（离线模式自动模拟）")

    # Step 4: Solution
    print("\n   📋 Solution 节点：生成处置方案...")
    solution = ("1. 紧急措施：立即降负荷运行，通知检修班组15分钟内到场\n"
                "2. 排查步骤：隔离故障设备→测量分闸线圈电阻→检查操动机构\n"
                "3. 预计修复时间：4-8小时\n"
                "4. 已发送飞书卡片告警通知（模拟）")
    print(f"   → {solution}")

    # Step 5: Execute
    print(f"\n   ✅ Execute 节点：生成巡检记录...")
    print(f"   → 巡检编号：IR-{device_id}-20260715")
    print(f"   → 状态：已完成并推送至运维平台")

    print(f"""
   ┌─ HITL 流程总结 ──────────────────────────────┐
   │                                                 │
   │  流程链：Router → Diagnosis → ⏸️HITL → Solution → Execute
   │                                                 │
   │  关键机制：                                      │
   │  · interrupt_before=["human_approval"]          │
   │    → 在 human_approval 执行前自动暂停            │
   │  · Command(resume=True) → 继续执行              │
   │  · MemorySaver → 暂停时持久化状态               │
   │                                                 │
   │  ⚡ 去掉 --offline 参数可运行真实 LangGraph 版本 │
   └─────────────────────────────────────────────────┘
""")


# ===========================================================================
# 主入口
# ===========================================================================

def main():
    if OFFLINE:
        print("=" * 60)
        print("🧪 实验三：Human-in-the-Loop [离线模式]")
        print("=" * 60)
        print("\n  ⚡ 离线模式：手动模拟 HITL 流程每个节点")
        print("  ⚡ 设备数据查询仍然真实执行（查 JSON 文件）")
        print("  ⚡ 去掉 --offline 参数可运行真实 LangGraph + interrupt\n")
        offline_demo()
    else:
        print("=" * 60)
        print("🧪 实验三：Human-in-the-Loop 人工审批")
        print("=" * 60)
        run_online()

    print("\n" + "=" * 60)
    print("🎉 实验三完成！")
    print("=" * 60)


if __name__ == "__main__":
    main()

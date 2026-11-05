"""
实验五：Supervisor 多 Agent 协作 — 三个专家 + 一个调度中心

核心概念：
  - 每个 Agent 有自己的 System Prompt + 专属 Tool 集合 → 领域专家
  - Supervisor：读 State → 决定调谁 → Agent 回来 → 再决定
  - 状态共享：Diagnosis 写入的诊断结论，Solution 直接读取

运行方式：
  python 05-multi-agent/multi_agent.py            # 正常模式（需要百炼 API + langgraph）
  python 05-multi-agent/multi_agent.py --offline  # 离线模式（纯本地运行）
"""

import json
import os
import sys
from pathlib import Path

OFFLINE = "--offline" in sys.argv
DATA_DIR = Path(__file__).parent.parent
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "")
BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
MODEL = "qwen-plus"


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
    from openai import OpenAI
    from typing import TypedDict, Optional, Literal
    from langgraph.graph import StateGraph, END

    def _chat(client, prompt: str, system: str = "") -> str:
        msgs = []
        if system: msgs.append({"role": "system", "content": system})
        msgs.append({"role": "user", "content": prompt})
        resp = client.chat.completions.create(model=MODEL, messages=msgs, temperature=0)
        return resp.choices[0].message.content

    class MultiAgentState(TypedDict):
        user_query: str; device_id: Optional[str]; symptom: Optional[str]
        diagnosis_result: Optional[str]; severity: Optional[str]
        solution_plan: Optional[str]; execution_record: Optional[str]
        next_action: str; task_history: list

    def run_online():
        if not DASHSCOPE_API_KEY:
            print("\n⚠️  请设置 DASHSCOPE_API_KEY 或使用 --offline"); sys.exit(1)
        client = OpenAI(base_url=BASE_URL, api_key=DASHSCOPE_API_KEY)

        # === Agent 节点定义（纯函数，单次 LLM 调用）===
        def supervisor_node(state: MultiAgentState) -> dict:
            diag = state.get("diagnosis_result")
            sol = state.get("solution_plan")
            rec = state.get("execution_record")
            if not diag: decision = "diagnosis_agent"
            elif not sol: decision = "solution_agent"
            elif not rec: decision = "execute_agent"
            else: decision = "FINISH"
            print(f"[Supervisor] ->{decision}")
            return {"next_action": decision}

        def diagnosis_node(state: MultiAgentState) -> dict:
            print("[Diagnosis] 分析故障...")
            eqs = load_equipment_data()
            device = next((e for e in eqs if e["id"] == state["device_id"]), None)
            kb = load_knowledge_base()
            kb_docs = [d for d in kb if "断路器" in d["title"] or "拒分" in d["content"]]
            prompt = f"设备数据：{json.dumps(device, ensure_ascii=False) if device else '无'}\n知识库：{json.dumps(kb_docs[:2], ensure_ascii=False)}\n现象：{state['symptom']}\n给出诊断结论和严重程度。"
            diagnosis = _chat(client, prompt, "你是电力设备故障诊断专家。")
            print(f"     诊断:{diagnosis[:120]}")
            return {"diagnosis_result": diagnosis, "task_history": state.get("task_history", []) + ["diagnosis"]}

        def solution_node(state: MultiAgentState) -> dict:
            print("[Solution] 生成处置方案...")
            solution = _chat(client, f"诊断结论：{state['diagnosis_result']}\n生成紧急处置方案。", "你是维修方案专家。")
            print(f"     方案:{solution[:120]}")
            return {"solution_plan": solution, "task_history": state.get("task_history", []) + ["solution"]}

        def execute_node(state: MultiAgentState) -> dict:
            print("[Execute] 生成巡检记录...")
            record = _chat(client, f"诊断：{state['diagnosis_result'][:100]}，方案：{state.get('solution_plan','')[:100]}。生成巡检记录。", "你是巡检记录专员。")
            print(f"     记录已生成")
            return {"execution_record": record, "task_history": state.get("task_history", []) + ["execute"]}

        def summarize_node(state: MultiAgentState) -> dict:
            report = f"\n╔══════════════════════════════════════╗\n║  故障诊断报告：{state['device_id']}\n║  诊断：{state.get('diagnosis_result','')[:150]}\n║  方案：{state.get('solution_plan','')[:150]}\n╚══════════════════════════════════════╝"
            print(report)
            print(f"任务序列:{' → '.join(state.get('task_history', []))}")
            return {}

        def route(state):
            nxt = state["next_action"]
            return nxt if nxt != "FINISH" else "summarize"

        # === 构建 LangGraph 工作流（真实的图编排）===
        wf = StateGraph(MultiAgentState)
        for name, fn in [("supervisor", supervisor_node), ("diagnosis_agent", diagnosis_node),
                          ("solution_agent", solution_node), ("execute_agent", execute_node), ("summarize", summarize_node)]:
            wf.add_node(name, fn)
        wf.set_entry_point("supervisor")
        wf.add_conditional_edges("supervisor", route, {"diagnosis_agent": "diagnosis_agent", "solution_agent": "solution_agent", "execute_agent": "execute_agent", "summarize": "summarize"})
        for a in ["diagnosis_agent", "solution_agent", "execute_agent"]:
            wf.add_edge(a, "supervisor")
        wf.add_edge("summarize", END)

        print("\n▶️  开始执行 LangGraph Supervisor 多 Agent 协作...")
        wf.compile().invoke({
            "user_query": "EP-D-002 断路器拒分", "device_id": "EP-D-002",
            "symptom": "合闸后无法分闸", "diagnosis_result": None, "severity": None,
            "solution_plan": None, "execution_record": None,
            "next_action": "diagnosis_agent", "task_history": [],
        })


# ===========================================================================
# 离线模式
# ===========================================================================

def offline_demo():
    """离线演示：手动模拟 Supervisor 调度三个专家的完整流程"""

    device_id = "EP-D-002"
    symptom = "合闸后无法正常分闸，机械指示卡在合闸位置"

    print(f"\n👤 用户输入：{device_id} 断路器拒分故障")
    print(f"   故障现象：{symptom}\n")

    # === Round 1: Diagnosis Agent ===
    print("🧠 Supervisor 决策：需要诊断 → 调用 Diagnosis Agent")
    print("[Diagnosis] 分析故障...")

    equipments = load_equipment_data()
    device = next((e for e in equipments if e["id"] == device_id), None)
    if device:
        print(f"   🛠 search_equipment_by_id('{device_id}') → {device['name']}，制造商={device['manufacturer']}，状态={device['status']}")

    kb = load_knowledge_base()
    found = [d for d in kb if "断路器" in d["title"] or "拒分" in d["content"]]
    if found:
        print(f"   🛠 search_knowledge_base('断路器拒分') → 找到 {found[0]['title']}")

    diagnosis_result = "分闸线圈电阻异常，判断为线圈绝缘老化导致机械卡涩"
    severity = "critical"
    print(f"     输出:{diagnosis_result}")
    print(f"   📤 严重程度：{severity}")
    print(f"     -> 回到 Supervisor\n")

    # === Round 2: Solution Agent ===
    print("🧠 Supervisor 决策：有诊断无方案 → 调用 Solution Agent")
    print("[Solution] 生成处置方案...")
    print(f"   📥 读取 State：diagnosis_result='{diagnosis_result}'，severity='{severity}'")
    print(f"   🛠 generate_repair_plan('{diagnosis_result[:20]}...', 'critical') → 紧急处置方案")
    print(f"   🛠 send_alert('{device_id}', 'critical', ...) → 飞书卡片告警已发送（模拟）")
    solution_plan = "立即降负荷 → 隔离故障设备 → 测量分闸线圈电阻 → 更换故障部件，预计4-8小时"
    print(f"   📤 输出方案：{solution_plan}")
    print(f"     -> 回到 Supervisor\n")

    # === Round 3: Execute Agent ===
    print("🧠 Supervisor 决策：有方案未执行 → 调用 Execute Agent")
    print("[Execute] 生成巡检记录...")
    print(f"   🛠 create_inspection_record('{device_id}', ...) → 巡检记录已生成")
    print(f"   🛠 push_notification(...) → 已推送至运维平台")
    print(f"     -> 回到 Supervisor\n")

    # === Round 4: FINISH ===
    print("🧠 Supervisor 决策：全部完成 → 汇总输出\n")

    print(f"""
╔══════════════════════════════════════════════╗
║           故障诊断报告                       ║
╠══════════════════════════════════════════════╣
║ 设备编号：{device_id} ({device['name']})
║ 故障现象：{symptom}
╠══════════════════════════════════════════════╣
║ 🔍 诊断结论：{diagnosis_result}
║ ⚠️  严重程度：{severity}
║ 📋 处置方案：{solution_plan}
║ ✅ 执行状态：已完成并推送至运维平台
╚══════════════════════════════════════════════╝
""")
    print(f"任务序列:diagnosis → solution → execute")
    print(f"   共 3 个 Agent 执行，Supervisor 调度 4 次\n")

    print("💡 三种编排模式总结：")
    print("   实验一 ReAct Agent：AI 自主决策 → 探索型任务")
    print("   实验三 StateGraph：编译时确定路径 → 固化流程")
    print("   实验五 Supervisor：LLM 半动态调度 → 多专家协作")
    print("   ⚡ 去掉 --offline 参数可运行真实 LangGraph Supervisor")


# ===========================================================================
# 主入口
# ===========================================================================

def main():
    if OFFLINE:
        print("=" * 60)
        print("🧪 实验五：Supervisor 多 Agent 协作 [离线模式]")
        print("=" * 60)
        print("\n  ⚡ 离线模式：手动模拟 Supervisor 调度三专家完整流程")
        print("  ⚡ 设备/知识库查询真实执行（查 JSON 文件）")
        print("  ⚡ 去掉 --offline 可运行真实 LangGraph Supervisor\n")
        offline_demo()
    else:
        print("=" * 60)
        print("🧪 实验五：Supervisor 多 Agent 协作")
        print("=" * 60)
        run_online()

    print("=" * 60)
    print("🎉 实验五完成！")
    print("=" * 60)


if __name__ == "__main__":
    main()

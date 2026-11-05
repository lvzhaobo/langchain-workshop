"""RunnableBranch — LCEL 版的 if/elif/else：不同告警级别走不同处理通道"""
import os
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableBranch
from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI

from _mock_llm import scripted, use_mock

if use_mock():
    print("⚠️  没检测到 AGENT_API_KEY —— 用预设回复跑通流程（零 Key 模式）")
    print("   想看真模型：填好 .env 里的 AGENT_API_KEY 再跑，代码不用改。\n")
    llm = scripted([
        ("P0 立即行动：\n1) 15 分钟内到场，检查 AAU5613 光模块与电源；"
         "\n2) 若光功率低于 -20dBm，直接更换尾纤；"
         "\n3) 30 分钟未恢复则升级到省级值班，并启动周边小区负载分担。", None),
        ("P1 排查步骤：\n1) 查 SCTP 链路状态与对端 IP 可达性；"
         "\n2) 核对 VLAN 与路由表；\n3) 必要时重启 SCTP 偶联。", None),
        ("例行检查建议：\n1) 每日核对告警与性能 KPI；\n2) 每周检查天馈驻波比；"
         "\n3) 每月演练一次退服应急预案。", None),
    ])
else:
    llm = ChatOpenAI(
        model=os.getenv("AGENT_MODEL", "deepseek-chat"),
        temperature=0,
        api_key=os.getenv("AGENT_API_KEY"),
        base_url=os.getenv("AGENT_API_BASE", "https://api.deepseek.com/v1"),
    )

# ── 三条通道，三个 Prompt ──
p0_prompt = ChatPromptTemplate.from_template(
    "P0 紧急告警！设备 {device_id}（{vendor} {model}，{site}）。给出立即行动方案和升级条件。"
)
p1_prompt = ChatPromptTemplate.from_template(
    "P1 重要告警！设备 {device_id}（{vendor} {model}，{site}）。分析问题并给出排查步骤。"
)
default_prompt = ChatPromptTemplate.from_template(
    "设备 {device_id}（{vendor} {model}，{site}）状态正常。给出例行检查建议，不超过 3 条。"
)

# ── 核心：RunnableBranch = if/elif/else ──
#
# 当前例子：severity 是已知字段，用 lambda 做确定性路由
# 进阶用法（Day 3 实验 3.1）：route_condition 里放 LLM，让它从自然语言判断意图：
#
#   def classify_intent(text: str) -> str:
#       return llm.invoke(f"判断意图（emergency/diagnose/routine）：{text}")
#
#   RunnableBranch(
#       (lambda x: classify_intent(x["input"]) == "emergency", emergency_chain),
#       (lambda x: classify_intent(x["input"]) == "diagnose",  diagnose_chain),
#       routine_chain,
#   )
#
# Python if/else 做不到"上不了网了！！！"和"最近掉线率有点高"的语义区分——LLM 可以。
chain = RunnableBranch(
    (lambda x: x["severity"] == "P0", p0_prompt | llm | StrOutputParser()),
    (lambda x: x["severity"] == "P1", p1_prompt | llm | StrOutputParser()),
    default_prompt | llm | StrOutputParser(),  # 默认通道
)


if __name__ == "__main__":
    # 模拟三台不同告警级别的设备
    devices = [
        {"device_id": "DEV-0001", "vendor": "华为", "model": "AAU5613", "site": "北京朝阳", "severity": "P0"},
        {"device_id": "DEV-0002", "vendor": "中兴", "model": "AAU8851", "site": "广州天河", "severity": "P1"},
        {"device_id": "DEV-0003", "vendor": "爱立信", "model": "AIR 6488", "site": "深圳南山", "severity": "NONE"},
    ]

    for d in devices:
        print(f"\n── {d['device_id']} (severity={d['severity']}) ──")
        result = chain.invoke(d)
        print(result[:200])

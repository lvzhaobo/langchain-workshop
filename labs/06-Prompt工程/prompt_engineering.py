"""Prompt 工程 — 三版 Prompt 对照：裸问 → 角色+约束 → Few-shot

运行：python prompt_engineering.py
依赖：pip install langchain langchain-openai
"""
import os
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

from langchain_core.prompts import ChatPromptTemplate, FewShotChatMessagePromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(
    model=os.getenv("AGENT_MODEL", "deepseek-chat"),
    temperature=0,
    api_key=os.getenv("AGENT_API_KEY"),
    base_url=os.getenv("AGENT_API_BASE", "https://api.deepseek.com/v1"),
)

# ── 样例设备数据（自包含，不依赖平台）──
DEVICE_INFO = (
    "设备ID：DEV-0001\n"
    "厂商/型号：华为 AAU5613\n"
    "站点：北京望京SOHO\n"
    "状态：告警\n"
    "告警（2条）：\n"
    "  - [P0] 基站退服: SCTP链路中断导致小区服务能力丧失\n"
    "  - [P1] 性能劣化: 接入成功率降至85%"
)


# ═══ v1：裸问 — 没有 Prompt 设计 ═══
v1_prompt = ChatPromptTemplate.from_template("{device_info}\n\n这个设备怎么样？")


# ═══ v2：角色 + 约束 — System Prompt 设计 ═══
v2_prompt = ChatPromptTemplate.from_messages([
    ("system", """你是 5G 基站运维专家。

回答约束：
1. 只根据设备数据回答，不要编造
2. 无法判断根因时明确说"需要进一步排查"
3. 按严重级别排序处理建议：P0 最先
4. 输出不超过 200 字
5. 结论先行：第一句必须是风险等级判断"""),
    ("human", "{device_info}\n\n请分析这台设备的状态。"),
])


# ═══ v3：Few-shot — v2 + 示例锁定格式 ═══
FEW_SHOT_EXAMPLES = [
    {
        "input": "设备ID：DEV-EX01\n厂商/型号：中兴 A9611\n站点：金融街\n状态：告警\n告警（1条）：\n  - [P0] 基站退服: 传输链路中断",
        "output": "【风险等级】高危 — P0 退服，业务已中断。\n【处理建议】\n1. [P0] 立即检查传输链路，预计10分钟\n2. 若链路正常，检查基带板\n【升级条件】30分钟内未恢复，上报重大故障。",
    },
    {
        "input": "设备ID：DEV-EX02\n厂商/型号：爱立信 AIR6449\n站点：中关村\n状态：正常\n告警（0条）：\n无告警",
        "output": "【风险等级】正常 — 无告警，业务运行正常。\n【处理建议】无需处理，保持例行巡检即可。",
    },
]

few_shot = FewShotChatMessagePromptTemplate(
    example_prompt=ChatPromptTemplate.from_messages([("human", "{input}"), ("ai", "{output}")]),
    examples=FEW_SHOT_EXAMPLES,
)

v3_prompt = ChatPromptTemplate.from_messages([
    ("system", "你是 5G 基站运维专家。约束同 v2。严格模仿示例的输出格式。"),
    few_shot,
    ("human", "{device_info}\n\n请分析这台设备的状态。"),
])


# ═══ 幻觉探针：故意问数据里没有的信息 ═══
HALLUCINATION_QUESTION = "这台设备的 IP 地址和软件版本号是多少？上次维护是什么时候？"

probe_v1 = ChatPromptTemplate.from_template("{device_info}\n\n" + HALLUCINATION_QUESTION)

probe_v2 = ChatPromptTemplate.from_messages([
    ("system", "只根据设备数据回答，数据里没有的信息一律回答'数据中未提供'，严禁编造。"),
    ("human", "{device_info}\n\n" + HALLUCINATION_QUESTION),
])


# ═══ 主程序 ═══
if __name__ == "__main__":
    print("=" * 50)
    print("实验 1.4a：Prompt 工程 — 三版对照")
    print("=" * 50)
    print(f"\n被测设备：\n{DEVICE_INFO}")

    parser = StrOutputParser()
    versions = [
        ("v1 裸问", v1_prompt, "没有角色、没有约束"),
        ("v2 角色+约束", v2_prompt, "专家角色 + 5条约束"),
        ("v3 Few-shot", v3_prompt, "v2 + 2条示例锁定格式"),
    ]

    results = {}
    for name, prompt, desc in versions:
        print(f"\n{'─'*40}")
        print(f"  {name} — {desc}")
        print(f"{'─'*40}")
        chain = prompt | llm | parser
        reply = chain.invoke({"device_info": DEVICE_INFO})
        results[name] = reply
        print(reply)

    # ── 对比统计 ──
    print(f"\n{'='*50}")
    print("三版对比")
    print(f"{'='*50}")
    print(f"{'版本':<14} {'字数':>6}  {'含风险等级':>8}  {'含升级条件':>8}")
    for name, reply in results.items():
        has_risk = "✓" if "风险等级" in reply or "高危" in reply else "✗"
        has_esc = "✓" if "升级" in reply else "✗"
        print(f"{name:<14} {len(reply):>6}  {has_risk:>8}  {has_esc:>8}")

    # ── 幻觉探针 ──
    print(f"\n{'='*50}")
    print("幻觉探针：问数据里没有的 IP / 版本号")
    print(f"{'='*50}")

    for name, prompt in [("v1 裸问", probe_v1), ("v2 带约束", probe_v2)]:
        print(f"\n── {name} ──")
        chain = prompt | llm | parser
        reply = chain.invoke({"device_info": DEVICE_INFO})
        print(reply[:300])

        fabricated = any(w in reply for w in ["10.", "192.168", "V100", "R0", "版本号"])
        honest = any(w in reply for w in ["未提供", "没有", "无法", "不包含"])
        print(f"判定：{'⚠️ 疑似编造' if (fabricated and not honest) else '✓ 诚实回答'}")

    print(f"\n{'='*50}")
    print("核心收获：")
    print("1. 角色+约束让输出从'随缘'变'可控'")
    print("2. Few-shot 锁定格式——比指令描述更有效")
    print("3. '只根据数据回答'能抑制幻觉——Day 2 RAG 的前置")

"""多 Agent 协作 — 检测 Agent + 诊断 Agent + 报告 Agent 协同分析 5G 故障"""

from deepagents import create_deep_agent


# ═══ 三个专业 Agent ═══

detect_agent = create_deep_agent(
    model="anthropic:claude-sonnet-4-20250514",
    system_prompt="你是 5G 基站检测专家。职责：查询设备状态、告警列表，输出结构化检测结果。不做诊断。",
    tools=[query_device, query_alarms],  # MCP 或 @tool 定义的工具
)

diagnose_agent = create_deep_agent(
    model="anthropic:claude-sonnet-4-20250514",
    system_prompt="你是 5G 根因分析专家。职责：基于检测结果推理根因，给出处理建议。不做检测也不写报告。",
)

report_agent = create_deep_agent(
    model="anthropic:claude-sonnet-4-20250514",
    system_prompt="你是运维报告撰写专家。职责：将检测和诊断结果整理成标准格式报告，写入文件。不做技术分析。",
)


# ═══ 编排 Supervisor ═══

supervisor = create_deep_agent(
    model="anthropic:claude-sonnet-4-20250514",
    system_prompt="""你是运维指挥 Supervisor。流程：
1. 调用 detect_agent 检测设备
2. 将检测结果发给 diagnose_agent 做根因分析
3. 将两部分结果发给 report_agent 生成最终报告
4. 向用户汇报结论""",
    subagents=[detect_agent, diagnose_agent, report_agent],
)

result = supervisor.invoke({
    "messages": "DEV-0001 上报了光模块异常告警，请组织完整分析并输出报告。"
})
print(result["messages"][-1].content)

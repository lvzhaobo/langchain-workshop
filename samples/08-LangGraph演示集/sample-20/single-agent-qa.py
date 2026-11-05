"""单 Agent 问答 — DeepAgents 最简用法"""

from deepagents import create_deep_agent

agent = create_deep_agent(
    model="anthropic:claude-sonnet-4-20250514",
    system_prompt="你是 5G 网络运维专家，回答简洁准确。",
)

# 单轮问答
result = agent.invoke({"messages": "5G AAU 光模块收光功率低于 -28dBm 意味着什么？"})
print(result["messages"][-1].content)

# 多轮对话（自动保留上下文）
result = agent.invoke({"messages": "这种场景下应该先查哪些指标？"})
print(result["messages"][-1].content)

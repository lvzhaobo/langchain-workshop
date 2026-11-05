"""单 Agent（sample-6 ReAct 模式）—— 对接 5G 平台 API"""

import os
from typing import Literal
from dotenv import load_dotenv
load_dotenv()

from langgraph.graph import StateGraph, START, END
from langgraph.graph import MessagesState
from langgraph.prebuilt import ToolNode
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from agents.tools import query_device, query_alarms, list_devices

TOOLS = [query_device, query_alarms, list_devices]

LLM = ChatOpenAI(
    model="deepseek-v4-pro",
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url=os.getenv("DEEPSEEK_BASE_URL"),
).bind_tools(TOOLS)

SYSTEM_PROMPT = """你是 5G 基站运维助手。可以使用工具查询设备和告警信息。
拿到数据后，分析并给出排查结论。"""


def llm_node(state: MessagesState) -> dict:
    messages = [SystemMessage(content=SYSTEM_PROMPT)] + state["messages"]
    return {"messages": [LLM.invoke(messages)]}


def should_continue(state: MessagesState) -> Literal["tools", "__end__"]:
    last = state["messages"][-1]
    if hasattr(last, "tool_calls") and last.tool_calls:
        return "tools"
    return "__end__"


builder = StateGraph(MessagesState)
builder.add_node("llm", llm_node)
builder.add_node("tools", ToolNode(TOOLS))
builder.add_edge(START, "llm")
builder.add_conditional_edges("llm", should_continue, {"tools": "tools", "__end__": END})
builder.add_edge("tools", "llm")

single_agent = builder.compile()

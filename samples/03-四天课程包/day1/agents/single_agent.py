"""LangChain ReAct Agent —— 代码级 Agent 通道（无 langgraph 依赖）

纯 while 循环实现：llm 调用 → 有 tool_calls → 执行工具 → 结果喂回 → 继续
换场景时只需改 SYSTEM_PROMPT 和 tools.py 里的返回格式。
"""
import os
from functools import reduce
from typing import Iterator

from dotenv import load_dotenv
from pydantic import SecretStr

load_dotenv()

from langchain_core.messages import (
    BaseMessage, SystemMessage, HumanMessage, AIMessage, AIMessageChunk, ToolMessage
)
from langchain_openai import ChatOpenAI

from agents.tools import TOOLS

LLM = ChatOpenAI(
    model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
    api_key=SecretStr(os.getenv("DEEPSEEK_API_KEY") or ""),
    base_url=os.getenv("DEEPSEEK_BASE_URL"),
    streaming=True,
).bind_tools(TOOLS)

# 换场景改这里：角色 + 分析要求
SYSTEM_PROMPT = """你是 5G 基站运维助手。可以使用工具查询对象详情、异常事件和对象清单。
拿到数据后给出简洁的分析结论：1) 现状 2) 可能原因 3) 处置建议。"""

MAX_TOOL_ROUNDS = 10  # 最多 10 轮工具调用，防止无限循环


def _run_tool(tool_call: dict) -> str:
    """执行单个工具调用并返回结果字符串。"""
    name = tool_call.get("name", "")
    args = tool_call.get("args", {})
    for t in TOOLS:
        if t.name == name:
            try:
                return str(t.invoke(args))
            except Exception as e:
                return f"工具执行失败: {e}"
    return f"未找到工具: {name}"


def stream(messages: list[BaseMessage], stream_mode: str = "messages") -> Iterator[tuple]:
    """
    兼容原 LangGraph 风格的 stream 接口。
    yield (chunk, metadata) 元组，metadata 含 langgraph_node 等字段供 app.py 使用。
    """
    full_messages = [SystemMessage(content=SYSTEM_PROMPT)] + list(messages)
    tool_rounds = 0

    while tool_rounds < MAX_TOOL_ROUNDS:
        chunks = []
        reasoning_content = ""

        print(f"  📡 [LLM] 第 {tool_rounds + 1} 轮调用...")

        for chunk in LLM.stream(full_messages):
            chunks.append(chunk)
            content = getattr(chunk, "content", "")
            if content:
                yield (chunk, {"langgraph_node": "llm"})
            # 收集 DeepSeek 思考模式的 reasoning_content
            rc = chunk.additional_kwargs.get("reasoning_content", "") if hasattr(chunk, "additional_kwargs") else ""
            if rc:
                reasoning_content += rc

        # 用 langchain 内置 + 运算符合并 chunk（正确处理 tool_calls 跨 chunk 累积）
        merged = reduce(lambda a, b: a + b, chunks) if chunks else AIMessageChunk(content="")

        # 构建最终 AIMessage，保留 reasoning_content
        msg_kwargs = {
            "content": merged.content if hasattr(merged, "content") else str(merged),
        }
        tc = getattr(merged, "tool_calls", None)
        if tc:
            msg_kwargs["tool_calls"] = tc
        if reasoning_content:
            msg_kwargs["additional_kwargs"] = {"reasoning_content": reasoning_content}

        ai_msg = AIMessage(**msg_kwargs)
        full_messages.append(ai_msg)

        if not tc:
            print(f"  💬 [LLM] 无工具调用，直接回复（{len(str(merged.content))} 字符）")
            break

        print(f"  🔨 [Agent] 发起 {len(tc)} 个工具调用: {[t.get('name', '?') for t in tc]}")

        for tc_item in tc:
            result = _run_tool({
                "name": tc_item.get("name", ""),
                "args": tc_item.get("args", {}),
            })
            tm = ToolMessage(content=result, tool_call_id=tc_item.get("id", ""))
            full_messages.append(tm)
            yield (tm, {"langgraph_node": "tools"})

        tool_rounds += 1

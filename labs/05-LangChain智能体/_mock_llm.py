"""零 Key 用的假模型 —— 让这个 lab 在没有任何 API Key 时也能跑通。

判定顺序：
  1. LANGCHAIN_MOCK=0/false/no  → 强制用真模型
  2. 填了 AGENT_API_KEY         → 用真模型
  3. 其它情况                   → 用这里的预设回复（不联网、不花钱）

想看真模型的效果，填好 .env 里的 AGENT_API_KEY 再跑即可，代码不用改。
"""
import os

from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage


def use_mock() -> bool:
    if os.getenv("LANGCHAIN_MOCK", "").strip().lower() in {"0", "false", "no"}:
        return False
    return not os.getenv("AGENT_API_KEY")


class FakeToolChat(GenericFakeChatModel):
    """补上 bind_tools —— create_agent 会调用它，基类抛 NotImplementedError。"""

    def bind_tools(self, tools, **kwargs):  # noqa: ARG002
        return self


def scripted(steps):
    """steps: [(content, tool_calls_or_None), ...]；按顺序回放，模拟多轮工具调用。"""
    msgs = []
    for content, calls in steps:
        msgs.append(AIMessage(content=content, tool_calls=calls or []))
    return FakeToolChat(messages=iter(msgs))

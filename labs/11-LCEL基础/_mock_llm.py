"""零 Key 用的假模型 —— 让这个 lab 在没有任何 API Key 时也能跑通。

两种用法：
  scripted([...])     按顺序回放固定回复（适合流程确定的 lab）
  rule_based(...)     按用户问题里的关键词决定调哪个工具（适合任务不定的 lab）

判定顺序：
  1. LANGCHAIN_MOCK=0/false/no  → 强制用真模型
  2. 填了 AGENT_API_KEY         → 用真模型
  3. 其它情况                   → 用假模型（不联网、不花钱）

想看真模型的效果，填好 .env 里的 AGENT_API_KEY 再跑即可，代码不用改。
"""
import os

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult


def use_mock() -> bool:
    if os.getenv("LANGCHAIN_MOCK", "").strip().lower() in {"0", "false", "no"}:
        return False
    return not os.getenv("AGENT_API_KEY")


def scripted(steps):
    """steps: [(content, tool_calls_or_None), ...]；按顺序回放，模拟多轮工具调用。"""
    msgs = [AIMessage(content=c, tool_calls=t or []) for c, t in steps]
    return FakeToolChat(messages=iter(msgs))


def computed(fn):
    """fn(prompt_text, call_index) -> str；按输入内容动态生成答复。"""
    return ComputedFakeChat(fn=fn)


def rule_based(rules, answer="已完成。"):
    """rules: [(关键词, 工具名, 参数字典), ...]；命中就调对应工具，之后给总结答复。"""
    return RuleFakeChat(rules=list(rules), answer=answer)


class FakeToolChat(GenericFakeChatModel):
    """补上 bind_tools —— create_agent 会调用它，基类抛 NotImplementedError。"""

    def bind_tools(self, tools, **kwargs):  # noqa: ARG002
        return self


class ComputedFakeChat(BaseChatModel):
    """把回复交给一个函数算：适合「按问题生成 SQL」「按 rubric 打分」这类场景。"""

    fn: object = None
    n: int = 0

    @property
    def _llm_type(self) -> str:
        return "computed-fake-chat"

    def bind_tools(self, tools, **kwargs):  # noqa: ARG002
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):  # noqa: ARG002
        text = "\n".join(str(getattr(m, "content", "")) for m in messages)
        out = self.fn(text, self.n)
        object.__setattr__(self, "n", self.n + 1)
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=out))])


class RuleFakeChat(BaseChatModel):
    """按用户问题里的关键词选工具；工具执行完就给最终答复。"""

    rules: list = []
    answer: str = "已完成。"

    @property
    def _llm_type(self) -> str:
        return "rule-fake-chat"

    def bind_tools(self, tools, **kwargs):  # noqa: ARG002
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):  # noqa: ARG002
        user = ""
        for m in messages:
            if getattr(m, "type", "") == "human":
                user = str(m.content)

        if any(getattr(m, "type", "") == "tool" for m in messages):
            reply = AIMessage(content=self.answer)
        else:
            hit = next((r for r in self.rules if r[0] in user), None)
            if hit:
                reply = AIMessage(content="", tool_calls=[
                    {"name": hit[1], "args": hit[2], "id": "call_1"}])
            else:
                reply = AIMessage(content=self.answer)

        return ChatResult(generations=[ChatGeneration(message=reply)])

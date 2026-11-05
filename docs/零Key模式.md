# 零 Key 模式：没有 API Key 也能跑通

> 目的：学员 `clone` 下来不配任何 Key，也能看到 lab 的完整输出。
> 想用真模型时，填好 `.env` 即可，**代码不用改**。

## 已完成

| Lab | 形态 | 靠什么跑通 |
|---|---|---|
| `01-hello-graph` | StateGraph | 无模型，纯节点 |
| `02-tools` | 工具循环 | 写死 `tool_calls` 的假 assistant 节点 |
| `03-memory` | Checkpointer | 无模型，纯计数器 |
| `05-LangChain智能体` | `create_agent` | `_mock_llm.py` 预设 tool_calls + 最终答复 |
| `10-RunnableBranch` | LCEL 链 | `_mock_llm.py` 预设三条通道答复 |

## 两种做法

### 做法 A：不需要模型（最彻底）

如果这个 lab 的教学点不是"模型怎么回答"，而是"图/状态/路由怎么走"，
**直接用假节点**，像 `02-tools` 那样把 `tool_calls` 写死：

```python
def assistant(state):
    return {"messages": [AIMessage(content="", tool_calls=[
        {"name": "get_device_status", "args": {"device_id": "DEV-0001"}, "id": "c1"}
    ])]}
```

优点：零依赖、零网络、输出完全确定。

### 做法 B：需要一个假模型（`_mock_llm.py`）

如果 lab 用的是 `create_agent` 或 LCEL 链，模型对象必须存在，就放一个 `_mock_llm.py`：

```python
# _mock_llm.py —— 放进 lab 目录，_ 开头的文件 run.sh 不会当成入口
import os
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage


def use_mock() -> bool:
    if os.getenv("LANGCHAIN_MOCK", "").strip().lower() in {"0", "false", "no"}:
        return False
    return not os.getenv("AGENT_API_KEY")


class FakeToolChat(GenericFakeChatModel):
    """必须补 bind_tools —— create_agent 会调它，基类抛 NotImplementedError。"""

    def bind_tools(self, tools, **kwargs):
        return self


def scripted(steps):
    """steps: [(content, tool_calls_or_None), ...]，按顺序回放。"""
    return FakeToolChat(messages=iter([AIMessage(content=c, tool_calls=t or []) for c, t in steps]))
```

主文件里改成：

```python
from _mock_llm import scripted, use_mock

if use_mock():
    print("⚠️  没检测到 AGENT_API_KEY —— 用预设回复跑通流程（零 Key 模式）")
    llm = scripted([("...", None), ("...", None)])
else:
    llm = ChatOpenAI(...)
```

## 三条规则

1. **预设回复要"像真的"** —— 内容必须是这个 lab 想教的那个结论，不能是 `"mock response"`。
   学员看到的应该是"跑通了的输出"，而不是"打桩的痕迹"。
2. **必须能切回真模型** —— `AGENT_API_KEY` 一填就走真模型，`LANGCHAIN_MOCK=0` 可强制真模型。
3. **打印一行提示** —— 让学员知道现在是零 Key 模式，而不是以为模型就这点本事。

## 坑

| 坑 | 现象 | 解 |
|---|---|---|
| `bind_tools` 未实现 | `NotImplementedError`（create_agent 里） | 按上面那样继承 `GenericFakeChatModel` 覆盖 |
| `with_structured_output` 未实现 | lab 08 这类 OutputParser 会挂 | 假模型里再覆盖一个，返回固定 Pydantic 对象 |
| 预设备选耗尽 | `StopIteration` | 多发一条兜底回复，或确认调用次数 |
| 辅助文件被当入口 | `run.sh` 报"多个入口" | 文件名加 `_` 前缀（`run.sh` 已忽略 `_*.py`） |
| `with_fallbacks` 的演示失效 | 假模型不会"失败" | 那个 `broken_llm` 保持真 `ChatOpenAI` + 假 key，让它真的报错 |

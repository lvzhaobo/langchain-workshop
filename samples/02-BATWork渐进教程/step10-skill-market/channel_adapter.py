"""
Channel Adapter — 多通道适配器抽象层 (BAT Work)

支持：
- WebSocket 通道（浏览器前端）
- 飞书 Bot 通道（IM 消息）
- 后续扩展：钉钉、企业微信、Slack
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional, Callable


class ChannelType(Enum):
    WEBSOCKET = "websocket"
    FEISHU = "feishu"
    DINGTALK = "dingtalk"
    WECOM = "wecom"


@dataclass
class ChannelMessage:
    """统一消息格式，所有通道适配器都转换为此格式"""
    channel: ChannelType
    user_id: str            # 发送者 ID
    user_name: str          # 发送者名称
    content: str            # 消息文本
    chat_id: str            # 会话 ID
    raw: dict = field(default_factory=dict)  # 原始消息数据
    attachments: list[dict] = field(default_factory=list)


@dataclass
class ChannelResponse:
    """统一回复格式"""
    content: str            # 回复文本
    channel: str            # 通道标识
    chat_id: str            # 目标会话
    metadata: dict = field(default_factory=dict)


class BaseChannelAdapter(ABC):
    """
    通道适配器基类
    
    每种通道（WebSocket、飞书 Bot等）实现此类，
    完成：
    1. 接收消息 → _parse_message() → ChannelMessage
    2. 发送回复 ← ChannelResponse ← _send_response()
    """

    def __init__(self, channel_type: ChannelType, name: str = ""):
        self.channel_type = channel_type
        self.name = name or channel_type.value
        self._agent_handler: Optional[Callable] = None

    @abstractmethod
    async def handle_incoming(self, raw_payload: Any) -> Optional[ChannelMessage]:
        """接收原始消息，解析为 ChannelMessage"""
        ...

    @abstractmethod
    async def send_response(self, response: ChannelResponse) -> bool:
        """发送回复到通道"""
        ...

    def set_agent_handler(self, handler: Callable):
        """设置 Agent 回调：async (ChannelMessage) -> str"""
        self._agent_handler = handler

    async def process(self, raw_payload: Any) -> Optional[str]:
        """
        完整处理流程：接收 → 解析 → Agent → 回复
        
        返回 Agent 生成的回复文本
        """
        msg = await self.handle_incoming(raw_payload)
        if not msg or not self._agent_handler:
            return None

        # 调用 Agent 处理
        result_text = await self._agent_handler(msg)

        # 发送回复
        await self.send_response(ChannelResponse(
            content=result_text,
            channel=self.channel_type.value,
            chat_id=msg.chat_id,
            metadata={"user_id": msg.user_id, "user_name": msg.user_name}
        ))

        return result_text

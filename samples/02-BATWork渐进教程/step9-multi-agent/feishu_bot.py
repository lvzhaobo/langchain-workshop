"""
飞书 Bot 适配器 — BAT Work 飞书通道

支持两种模式：
1. 自定义 Bot Webhook（仅发消息到群里）— 需要 Webhook URL
2. 双向对话模式（通过 HTTP API 模拟接收）

配置方式：
- 环境变量 FEISHU_WEBHOOK_URL
- 或启动参数 --feishu-webhook-url
- 或 config 文件
"""

import json
import logging
from typing import Any, Optional

import httpx

from channel_adapter import (
    BaseChannelAdapter,
    ChannelMessage,
    ChannelResponse,
    ChannelType,
)

logger = logging.getLogger(__name__)


class FeishuBotAdapter(BaseChannelAdapter):
    """飞书自定义机器人适配器"""

    def __init__(
        self,
        webhook_url: str = "",
        bot_name: str = "BAT Work Bot",
        http_client: Optional[httpx.AsyncClient] = None,
    ):
        super().__init__(ChannelType.FEISHU, name=bot_name)
        self.webhook_url = webhook_url
        self.bot_name = bot_name
        self._client = http_client or httpx.AsyncClient(timeout=30.0)
        self._conversations = {}  # 本地会话历史

    # ── 消息格式 ──────────────────────────────────────────

    @staticmethod
    def build_text_card(title: str, content: str, color: str = "blue") -> Any:
        """构建飞书消息卡片"""
        return {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {"tag": "plain_text", "content": title},
                    "template": color,
                },
                "elements": [
                    {
                        "tag": "markdown",
                        "content": content,
                    }
                ],
            },
        }

    @staticmethod
    def build_text_msg(text: str) -> Any:
        """构建飞书普通文本消息"""
        return {
            "msg_type": "text",
            "content": {"text": text},
        }

    # ── 接收消息 ──────────────────────────────────────────

    async def handle_incoming(self, raw_payload: Any) -> Optional[ChannelMessage]:
        """
        解析飞书传入的消息
        
        支持格式：
        1. 飞书 Outgoing Webhook 格式（真实飞书回调）
        2. 简化 REST 格式（Demo 用）
        
        真实飞书 Outgoing Webhook 格式:
        {
            "timestamp": "...",
            "sign": "...",
            "msg_type": "text",
            "content": {"text": "..."}
        }
        
        简化 Demo 格式:
        {"text": "消息内容", "user_id": "xxx", "chat_id": "xxx"}
        """
        if isinstance(raw_payload, str):
            try:
                raw_payload = json.loads(raw_payload)
            except json.JSONDecodeError:
                raw_payload = {"text": raw_payload}

        if not isinstance(raw_payload, dict):
            return None

        # 格式 1: 飞书 Outgoing Webhook
        if "content" in raw_payload and isinstance(raw_payload["content"], dict):
            text = raw_payload["content"].get("text", "")
            user_id = raw_payload.get("open_id", "feishu-user")
            chat_id = raw_payload.get("open_chat_id", "feishu-chat")
        # 格式 2: 简化 Demo 格式
        else:
            text = raw_payload.get("text", raw_payload.get("content", ""))
            user_id = raw_payload.get("user_id", "demo-user")
            chat_id = raw_payload.get("chat_id", "demo-chat")

        if not text:
            return None

        return ChannelMessage(
            channel=ChannelType.FEISHU,
            user_id=user_id,
            user_name=raw_payload.get("user_name", user_id),
            content=text,
            chat_id=chat_id,
            raw=raw_payload,
        )

    # ── 发送消息 ──────────────────────────────────────────

    async def send_response(self, response: ChannelResponse) -> bool:
        """
        发送回复到飞书
        
        包含发送回 Webhook（卡片消息）和本地模拟会话记录
        """
        await self._send_to_webhook(response)

        # 本地记录会话
        if response.chat_id not in self._conversations:
            self._conversations[response.chat_id] = []
        self._conversations[response.chat_id].append({
            "role": "assistant",
            "content": response.content,
            "metadata": response.metadata,
        })
        return True

    async def _send_to_webhook(self, response: ChannelResponse) -> bool:
        """通过飞书 Webhook 发送消息"""
        if not self.webhook_url:
            logger.warning("飞书 Webhook URL 未配置，跳过发送")
            return False

        try:
            payload = self.build_text_msg(response.content)
            r = await self._client.post(
                self.webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            result = r.json()
            if result.get("code") == 0:
                logger.info(f"飞书消息发送成功: {response.chat_id}")
                return True
            else:
                logger.error(f"飞书消息发送失败: {result}")
                return False
        except Exception as e:
            logger.error(f"飞书消息发送异常: {e}")
            return False

    # ── 管理接口 ──────────────────────────────────────────

    def get_status(self) -> Any:
        """返回 Bot 状态"""
        return {
            "name": self.bot_name,
            "channel": self.channel_type.value,
            "webhook_configured": bool(self.webhook_url),
            "conversations_count": len(self._conversations),
            "running": True,
        }

    async def close(self):
        """清理资源"""
        await self._client.aclose()

    async def send_direct(
        self, text: str, chat_id: str = "", title: str = "BAT Work 通知"
    ) -> Any:
        """直接发送消息到飞书（外部调用接口）"""
        # 发送文本消息
        success = await self._send_to_webhook(ChannelResponse(
            content=text,
            channel=ChannelType.FEISHU.value,
            chat_id=chat_id or "default",
        ))

        if not self.webhook_url:
            # 无 Webhook 时返回模拟结果
            return {
                "success": True,
                "mode": "simulated",
                "text": text,
                "message": "飞书 Webhook 未配置，消息已记录但不发送",
            }

        return {
            "success": success,
            "mode": "webhook",
            "text": text,
        }

import asyncio
from enum import Enum
from typing import Dict, Any, List, Optional, Callable, Awaitable
from pydantic import BaseModel, Field
from lxion.core.logger import logger, AuditLogger

class ChannelType(str, Enum):
    TELEGRAM = "telegram"
    DISCORD = "discord"
    WHATSAPP = "whatsapp"
    WEB = "web"
    CLI = "cli"

class InboundMessage(BaseModel):
    channel: ChannelType
    sender_id: str
    sender_name: str = "User"
    session_id: str
    text: str
    metadata: Dict[str, Any] = Field(default_factory=dict)

class OutboundMessage(BaseModel):
    channel: ChannelType
    recipient_id: str
    text: str
    reply_to_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

class MessageBus:
    def __init__(self):
        self._handlers: Dict[ChannelType, Callable[[OutboundMessage], Awaitable[None]]] = {}
        self._core_agent_handler: Optional[Callable[[InboundMessage], Awaitable[str]]] = None
        self._broadcast_subscribers: List[Callable[[OutboundMessage], Awaitable[None]]] = []

    def register_channel_sender(
        self,
        channel: ChannelType,
        sender_func: Callable[[OutboundMessage], Awaitable[None]]
    ):
        """Register the outbound sending handler for a channel."""
        self._handlers[channel] = sender_func
        logger.info(f"✓ Registered outbound message sender for channel: {channel.value}")

    def set_agent_handler(self, handler: Callable[[InboundMessage], Awaitable[str]]):
        """Set the core agent handler that processes inbound messages."""
        self._core_agent_handler = handler

    async def dispatch_inbound(self, msg: InboundMessage) -> str:
        """Route an inbound message to the core agent and return the agent response."""
        AuditLogger.log_event("MESSAGE_INBOUND", msg.channel.value, {
            "sender": msg.sender_id, "text_len": len(msg.text)
        })
        if self._core_agent_handler:
            response_text = await self._core_agent_handler(msg)
            return response_text
        else:
            return "Agent core handler not initialized."

    handle_inbound = dispatch_inbound

    async def send_outbound(self, msg: OutboundMessage):
        """Send a message out through the appropriate channel sender."""
        AuditLogger.log_event("MESSAGE_OUTBOUND", msg.channel.value, {
            "recipient": msg.recipient_id, "text_len": len(msg.text)
        })
        sender = self._handlers.get(msg.channel)
        if sender:
            await sender(msg)
        else:
            logger.warning(f"No sender registered for channel {msg.channel.value}")

    async def broadcast(self, text: str, preferred_channel: Optional[ChannelType] = None):
        """Broadcast an alert or notification to active channels."""
        for ch, sender in self._handlers.items():
            if preferred_channel and ch != preferred_channel:
                continue
            try:
                # Default broadcast target can be configured
                await sender(OutboundMessage(channel=ch, recipient_id="broadcast", text=text))
            except Exception as e:
                logger.error(f"Failed to broadcast on {ch.value}: {e}")

message_bus = MessageBus()
import asyncio
from typing import Dict, Any, Optional
from lxion.channels.bus import message_bus, ChannelType, InboundMessage, OutboundMessage
from lxion.core.logger import logger, AuditLogger

class WhatsAppSidecarBridge:
    """HTTP/WebSocket bridge to communicate with Baileys Node.js sidecar process."""
    def __init__(self, sidecar_url: str = "http://localhost:3001"):
        self.sidecar_url = sidecar_url
        message_bus.register_channel_sender(ChannelType.WHATSAPP, self.send_to_whatsapp)

    async def handle_inbound_from_sidecar(self, payload: Dict[str, Any]) -> str:
        """Called by FastAPI webhook when Baileys receives a WhatsApp message."""
        sender_phone = payload.get("from", "unknown")
        text = payload.get("body", "")
        push_name = payload.get("pushName", "WhatsApp User")

        inbound = InboundMessage(
            channel=ChannelType.WHATSAPP,
            sender_id=sender_phone,
            sender_name=push_name,
            session_id=f"wa_{sender_phone}",
            text=text,
            metadata=payload
        )
        return await message_bus.dispatch_inbound(inbound)

    async def send_to_whatsapp(self, msg: OutboundMessage):
        """Send message back through Baileys HTTP sidecar."""
        import httpx
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                await client.post(
                    f"{self.sidecar_url}/send",
                    json={"to": msg.recipient_id, "message": msg.text}
                )
        except Exception as e:
            logger.error(f"Failed to forward message to WhatsApp Baileys sidecar: {e}")

whatsapp_bridge = WhatsAppSidecarBridge()
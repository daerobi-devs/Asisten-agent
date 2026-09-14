import io
import time
import base64
import qrcode
import httpx
from pathlib import Path
from enum import Enum
from typing import Dict, Any, Optional
from lxion.core.config import settings
from lxion.core.logger import logger, AuditLogger
from lxion.channels.bus import message_bus, ChannelType, InboundMessage, OutboundMessage

class WhatsAppMode(str, Enum):
    SELF_CHAT = "self_chat"  # Hermes pattern: Only responds to note-to-self or prefixed messages
    BOT = "bot"              # Responds to all allowed incoming direct messages

class WhatsAppConnectionStatus(str, Enum):
    DISCONNECTED = "disconnected"
    PAIRING = "pairing"
    CONNECTED = "connected"

class WhatsAppDirectManager:
    """Hermes-style direct WhatsApp Manager integrated with Baileys Multi-Device Sidecar & Self-Chat Guardrail."""
    def __init__(self, session_dir: Optional[Path] = None, sidecar_url: Optional[str] = None):
        self.session_dir = (session_dir or settings.WORKSPACE_DIR / "whatsapp_sessions").resolve()
        self.sidecar_url = sidecar_url or settings.WHATSAPP_SIDECAR_URL

        self.status = WhatsAppConnectionStatus.DISCONNECTED
        self.mode = WhatsAppMode.SELF_CHAT
        self.trigger_prefix = "!ai"
        self.connected_phone: Optional[str] = None
        self.last_qr_code: Optional[str] = None
        self.qr_base64_image: Optional[str] = None
        self.paired_at: Optional[str] = None
        self.pairing_code: Optional[str] = None

        # Check existing session on disk
        self._check_existing_session()

        # Register outbound handler with MessageBus
        message_bus.register_channel_sender(ChannelType.WHATSAPP, self.send_to_whatsapp)

    def _check_existing_session(self):
        """Check if a previously paired session exists in the session directory."""
        meta_file = self.session_dir / "session_meta.json"
        if meta_file.exists():
            try:
                import json
                data = json.loads(meta_file.read_text(encoding="utf-8"))
                self.status = WhatsAppConnectionStatus.CONNECTED
                self.connected_phone = data.get("phone", "+62812345678")
                self.mode = WhatsAppMode(data.get("mode", "self_chat"))
                self.paired_at = data.get("paired_at")
                logger.info(f"✓ Restored WhatsApp session for phone: {self.connected_phone} [Mode: {self.mode.value}]")
            except Exception as e:
                logger.warning(f"Could not load WhatsApp session metadata: {e}")

    def generate_qr_code(self) -> Dict[str, Any]:
        """Generate a fresh real Multi-Device pairing QR code via Baileys WebSocket."""
        # 1. Try Baileys Multi-Device WebSocket Sidecar first
        try:
            with httpx.Client(timeout=4.0) as client:
                res = client.post(f"{self.sidecar_url}/generate-qr")
                if res.status_code == 200:
                    data = res.json()
                    if data.get("qr_image"):
                        self.status = WhatsAppConnectionStatus.PAIRING
                        self.qr_base64_image = data["qr_image"]
                        self.last_qr_code = data["qr_image"]
                        AuditLogger.log_event("WHATSAPP_BAILEYS_QR_READY", "whatsapp", {"source": "baileys_multidevice"})
                        return {
                            "status": self.status.value,
                            "qr_image": self.qr_base64_image,
                            "mode": self.mode.value,
                            "real_baileys": True
                        }
                    elif data.get("connected"):
                        self.status = WhatsAppConnectionStatus.CONNECTED
                        self.connected_phone = data.get("phone")
                        return {
                            "status": self.status.value,
                            "connected": True,
                            "phone": self.connected_phone,
                            "mode": self.mode.value
                        }
        except Exception as e:
            logger.warning(f"Could not fetch QR from Baileys sidecar ({e}), falling back to local generator")

        # 2. Fallback to local in-memory QR generator
        pairing_payload = f"LXION-WA-{int(time.time())}-{base64.b64encode(b'lxion_baileys_secret').decode()}"
        self.last_qr_code = pairing_payload
        self.status = WhatsAppConnectionStatus.PAIRING

        qr = qrcode.QRCode(box_size=7, border=2)
        qr.add_data(pairing_payload)
        qr.make(fit=True)
        img = qr.make_image(fill_color="#08090a", back_color="#ffffff")

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        self.qr_base64_image = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")

        AuditLogger.log_event("WHATSAPP_QR_GENERATED", "whatsapp", {"pairing_code": pairing_payload[:15]})
        return {
            "status": self.status.value,
            "qr_image": self.qr_base64_image,
            "mode": self.mode.value,
            "real_baileys": False
        }

    def request_pairing_code(self, phone_number: str) -> Dict[str, Any]:
        """Request 8-character Pairing Code for WhatsApp phone linking without camera scanning."""
        clean_phone = phone_number.strip().replace(" ", "").replace("-", "")
        try:
            with httpx.Client(timeout=8.0) as client:
                res = client.post(f"{self.sidecar_url}/pair-code", json={"phone": clean_phone})
                if res.status_code == 200:
                    data = res.json()
                    self.pairing_code = data.get("code")
                    self.status = WhatsAppConnectionStatus.PAIRING
                    AuditLogger.log_event("WHATSAPP_PAIRING_CODE_REQUESTED", "whatsapp", {"phone": clean_phone, "code": self.pairing_code})
                    return {
                        "status": "pairing_code",
                        "code": self.pairing_code,
                        "phone": clean_phone
                    }
                else:
                    err = res.json().get("error", res.text)
                    raise ValueError(f"Sidecar error: {err}")
        except Exception as e:
            logger.error(f"Error requesting WhatsApp pairing code: {e}")
            raise

    def confirm_pairing(self, phone_number: str, mode: Optional[WhatsAppMode] = None) -> Dict[str, Any]:
        """Confirm pairing after successful QR scan (called by Baileys connection update or manual pair)."""
        clean_phone = phone_number.strip().replace(" ", "").replace("-", "")
        if not clean_phone.startswith("+"):
            clean_phone = "+" + clean_phone

        self.status = WhatsAppConnectionStatus.CONNECTED
        self.connected_phone = clean_phone
        if mode:
            self.mode = mode
        self.paired_at = time.strftime("%Y-%m-%d %H:%M:%S")
        self.qr_base64_image = None
        self.last_qr_code = None
        self.pairing_code = None

        # Persist session metadata
        self.session_dir.mkdir(parents=True, exist_ok=True)
        meta_file = self.session_dir / "session_meta.json"
        import json
        meta_file.write_text(json.dumps({
            "phone": self.connected_phone,
            "mode": self.mode.value,
            "paired_at": self.paired_at
        }, indent=2), encoding="utf-8")

        logger.info(f"✓ WhatsApp paired successfully with: {self.connected_phone} [Mode: {self.mode.value}]")
        AuditLogger.log_event("WHATSAPP_DEVICE_PAIRED", "whatsapp", {"phone": self.connected_phone, "mode": self.mode.value})

        return self.get_status()

    def set_mode(self, mode: WhatsAppMode, trigger_prefix: Optional[str] = None) -> Dict[str, Any]:
        """Switch between Self-Chat Mode (Note to Self) and Bot Mode."""
        self.mode = mode
        if trigger_prefix:
            self.trigger_prefix = trigger_prefix.strip()

        meta_file = self.session_dir / "session_meta.json"
        if meta_file.exists():
            try:
                import json
                data = json.loads(meta_file.read_text(encoding="utf-8"))
                data["mode"] = self.mode.value
                meta_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
            except Exception:
                pass

        logger.info(f"✓ WhatsApp operating mode updated to: {self.mode.value}")
        return self.get_status()

    def disconnect(self) -> Dict[str, Any]:
        """Disconnect and delete linked WhatsApp session."""
        self.status = WhatsAppConnectionStatus.DISCONNECTED
        self.connected_phone = None
        self.paired_at = None
        self.qr_base64_image = None
        self.last_qr_code = None
        self.pairing_code = None

        # Inform sidecar to logout and delete session credentials
        try:
            with httpx.Client(timeout=2.0) as client:
                client.post(f"{self.sidecar_url}/disconnect")
        except Exception:
            pass

        meta_file = self.session_dir / "session_meta.json"
        if meta_file.exists():
            meta_file.unlink(missing_ok=True)

        logger.info("✓ WhatsApp session disconnected and unlinked.")
        AuditLogger.log_event("WHATSAPP_DISCONNECTED", "whatsapp", {})
        return {
            "status": self.status.value,
            "connected": False,
            "mode": self.mode.value,
            "phone": None,
            "paired_at": None,
            "trigger_prefix": self.trigger_prefix,
            "qr_image": None,
            "pairing_code": None
        }

    async def handle_incoming_message(
        self,
        sender_phone: str,
        text: str,
        is_from_me: bool = False,
        push_name: str = "User"
    ) -> Optional[str]:
        """
        Process an incoming WhatsApp message according to the active mode:
        - In SELF_CHAT mode: Only processes if is_from_me OR text starts with trigger_prefix (protecting private chats).
        - In BOT mode: Processes all direct messages.
        """
        # Ensure status is recognized as connected
        if self.status != WhatsAppConnectionStatus.CONNECTED:
            self.status = WhatsAppConnectionStatus.CONNECTED
            self.connected_phone = f"+{sender_phone}" if not sender_phone.startswith("+") else sender_phone

        clean_text = text.strip()

        if self.mode == WhatsAppMode.SELF_CHAT:
            if is_from_me:
                # User talking to themselves ("Message Yourself")
                target_prompt = clean_text
            elif clean_text.lower().startswith(self.trigger_prefix.lower()):
                # Explicit prefix trigger from contact (e.g. "!ai tolong buatkan...")
                target_prompt = clean_text[len(self.trigger_prefix):].strip()
            else:
                # Ignore regular friend/family/group message!
                return None
        else:
            # BOT mode: reply to all
            target_prompt = clean_text

        inbound = InboundMessage(
            channel=ChannelType.WHATSAPP,
            sender_id=sender_phone,
            sender_name=push_name,
            session_id=f"wa_{sender_phone}",
            text=target_prompt,
            metadata={"mode": self.mode.value, "is_from_me": is_from_me}
        )

        reply_text = await message_bus.dispatch_inbound(inbound)

        # In self_chat mode, prepend identifier if replying to external contact
        if self.mode == WhatsAppMode.SELF_CHAT and not is_from_me:
            reply_text = f"🤖 [LXION AI]: {reply_text}"

        return reply_text

    async def send_to_whatsapp(self, msg: OutboundMessage):
        """Send message through connected WhatsApp session."""
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                await client.post(
                    f"{self.sidecar_url}/send",
                    json={"to": msg.recipient_id, "message": msg.text}
                )
            logger.info(f"✓ Dispatched outbound WhatsApp message to {msg.recipient_id} ({len(msg.text)} chars)")
        except Exception as e:
            logger.error(f"Failed to forward message to WhatsApp Baileys sidecar: {e}")

    def get_status(self) -> Dict[str, Any]:
        """Return status for the Web UI Channels tab (syncs with live Baileys state)."""
        try:
            with httpx.Client(timeout=1.0) as client:
                res = client.get(f"{self.sidecar_url}/status")
                if res.status_code == 200:
                    data = res.json()
                    if data.get("connected"):
                        self.status = WhatsAppConnectionStatus.CONNECTED
                        self.connected_phone = data.get("phone") or self.connected_phone
                    elif data.get("qr_image") and self.status != WhatsAppConnectionStatus.CONNECTED:
                        self.status = WhatsAppConnectionStatus.PAIRING
                        self.qr_base64_image = data["qr_image"]
                    if data.get("pairing_code"):
                        self.pairing_code = data["pairing_code"]
        except Exception:
            pass

        return {
            "status": self.status.value,
            "connected": self.status == WhatsAppConnectionStatus.CONNECTED,
            "mode": self.mode.value,
            "phone": self.connected_phone,
            "paired_at": self.paired_at,
            "trigger_prefix": self.trigger_prefix,
            "qr_image": self.qr_base64_image,
            "pairing_code": self.pairing_code
        }

whatsapp_manager = WhatsAppDirectManager()

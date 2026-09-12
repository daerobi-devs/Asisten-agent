import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from lxion.channels.whatsapp_manager import WhatsAppDirectManager, WhatsAppMode, WhatsAppConnectionStatus
from lxion.channels.discord_bot import DiscordGateway
from lxion.channels.bus import ChannelType, InboundMessage, OutboundMessage, message_bus
from lxion.main import app

@pytest.fixture
def tmp_whatsapp_manager(tmp_path):
    mgr = WhatsAppDirectManager(session_dir=tmp_path / "wa_session")
    mgr.sidecar_url = "http://127.0.0.1:9999"
    mgr._check_baileys_health = lambda: {"connected": False, "status": "disconnected"}
    return mgr

@pytest.mark.asyncio
async def test_whatsapp_qr_generation(tmp_whatsapp_manager):
    mgr = tmp_whatsapp_manager
    res = mgr.generate_qr_code()
    assert res["status"] == WhatsAppConnectionStatus.PAIRING.value
    assert res["qr_image"].startswith("data:image/png;base64,")
    assert mgr.status == WhatsAppConnectionStatus.PAIRING

@pytest.mark.asyncio
async def test_whatsapp_pairing_and_disconnect(tmp_whatsapp_manager):
    mgr = tmp_whatsapp_manager
    mgr.generate_qr_code()
    pair_res = mgr.confirm_pairing("+62812345678", mode=WhatsAppMode.SELF_CHAT)
    assert pair_res["connected"] is True
    assert pair_res["phone"] == "+62812345678"
    assert mgr.status == WhatsAppConnectionStatus.CONNECTED

    disc_res = mgr.disconnect()
    assert disc_res["connected"] is False
    assert mgr.status == WhatsAppConnectionStatus.DISCONNECTED

@pytest.mark.asyncio
async def test_whatsapp_self_chat_guardrail(tmp_whatsapp_manager):
    mgr = tmp_whatsapp_manager
    mgr.confirm_pairing("+62812345678", mode=WhatsAppMode.SELF_CHAT)

    # Mock MessageBus agent handler
    async def mock_handler(inbound: InboundMessage) -> str:
        return f"Echo: {inbound.text}"
    message_bus.set_agent_handler(mock_handler)

    # 1. Normal message from outside contact without !ai prefix -> must be ignored!
    ignored = await mgr.handle_incoming_message(
        sender_phone="+62899999999",
        text="Halo bro apa kabar?",
        is_from_me=False
    )
    assert ignored is None

    # 2. Message from outside contact with !ai prefix -> must be processed
    prefixed = await mgr.handle_incoming_message(
        sender_phone="+62899999999",
        text="!ai tolong bantu hitung 5+5",
        is_from_me=False
    )
    assert prefixed is not None
    assert "Echo: tolong bantu hitung 5+5" in prefixed

    # 3. Note-to-self (is_from_me=True) -> must be processed without prefix
    self_msg = await mgr.handle_incoming_message(
        sender_phone="+62812345678",
        text="Catat ide proyek LXION besok",
        is_from_me=True
    )
    assert self_msg is not None
    assert "Echo: Catat ide proyek LXION besok" in self_msg

@pytest.mark.asyncio
async def test_whatsapp_bot_mode(tmp_whatsapp_manager):
    mgr = tmp_whatsapp_manager
    mgr.confirm_pairing("+62812345678", mode=WhatsAppMode.BOT)

    async def mock_handler(inbound: InboundMessage) -> str:
        return f"Bot Reply: {inbound.text}"
    message_bus.set_agent_handler(mock_handler)

    # In BOT mode, replies to all incoming chats
    reply = await mgr.handle_incoming_message(
        sender_phone="+62899999999",
        text="Siapa kamu?",
        is_from_me=False
    )
    assert reply == "Bot Reply: Siapa kamu?"

def test_discord_gateway_status():
    gw = DiscordGateway()
    status = gw.get_status()
    assert "configured" in status
    assert "running" in status
    assert status["running"] is False

def test_channels_api_endpoints():
    client = TestClient(app)

    # 1. Channels Status
    res = client.get("/api/channels/status")
    assert res.status_code == 200
    data = res.json()
    assert "telegram" in data
    assert "whatsapp" in data
    assert "discord" in data

    # 2. WhatsApp QR
    with patch("lxion.main.whatsapp_manager.generate_qr_code", return_value={"status": "pairing", "qr_image": "data:image/png;base64,mockqr", "mode": "self_chat", "real_baileys": False}):
        qr_res = client.post("/api/channels/whatsapp/qr")
        assert qr_res.status_code == 200
        assert qr_res.json()["qr_image"].startswith("data:image/png;base64,")

    # 3. WhatsApp Pair
    pair_res = client.post("/api/channels/whatsapp/pair", json={"phone": "+628111222333", "mode": "self_chat"})
    assert pair_res.status_code == 200
    assert pair_res.json()["whatsapp"]["connected"] is True

    # 4. WhatsApp Mode Switch
    mode_res = client.post("/api/channels/whatsapp/mode", json={"mode": "bot", "trigger_prefix": "#ai"})
    assert mode_res.status_code == 200
    assert mode_res.json()["whatsapp"]["mode"] == "bot"

    # 5. WhatsApp Inbound Webhook
    wb_res = client.post("/api/channels/whatsapp/webhook", json={
        "sender": "+62899999999",
        "text": "Hello from webhook",
        "is_from_me": False
    })
    assert wb_res.status_code == 200
    assert wb_res.json()["status"] == "ok"

    # 6. WhatsApp Disconnect
    disc_res = client.post("/api/channels/whatsapp/disconnect")
    assert disc_res.status_code == 200
    assert disc_res.json()["whatsapp"]["connected"] is False

    # 7. Discord Stop
    dc_stop = client.post("/api/channels/discord/stop")
    assert dc_stop.status_code == 200
    assert dc_stop.json()["discord"]["running"] is False

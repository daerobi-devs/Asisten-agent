import pytest
from lxion.channels.bus import MessageBus, ChannelType, InboundMessage, OutboundMessage
from lxion.channels.telegram_bot import TelegramGateway

@pytest.mark.asyncio
async def test_message_bus_routing():
    bus = MessageBus()
    outbound_captured = []

    # 1. Register mock channel sender
    async def mock_telegram_sender(msg: OutboundMessage):
        outbound_captured.append(msg)

    bus.register_channel_sender(ChannelType.TELEGRAM, mock_telegram_sender)

    # 2. Register agent core handler
    async def mock_agent_handler(inbound: InboundMessage) -> str:
        return f"Echo from agent: {inbound.text}"

    bus.set_agent_handler(mock_agent_handler)

    # 3. Test inbound dispatch
    inbound = InboundMessage(
        channel=ChannelType.TELEGRAM,
        sender_id="123456",
        sender_name="Alice",
        session_id="chat_123456",
        text="Halo LXION"
    )
    res = await bus.dispatch_inbound(inbound)
    assert res == "Echo from agent: Halo LXION"

    # 4. Test outbound send
    out = OutboundMessage(
        channel=ChannelType.TELEGRAM,
        recipient_id="123456",
        text="Balasan dari LXION"
    )
    await bus.send_outbound(out)
    assert len(outbound_captured) == 1
    assert outbound_captured[0].text == "Balasan dari LXION"

def test_telegram_gateway_whitelist():
    gw = TelegramGateway(token="dummy_token")
    # Empty allowed users means open to owner
    assert gw._is_allowed(999) is True

    # Set whitelist
    gw.allowed_users = ["123", "456"]
    assert gw._is_allowed(123) is True
    assert gw._is_allowed(999) is False
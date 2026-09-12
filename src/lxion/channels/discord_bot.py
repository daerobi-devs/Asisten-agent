import asyncio
import discord
from typing import Optional, List, Dict, Any
from lxion.core.config import settings
from lxion.core.logger import logger, AuditLogger
from lxion.channels.bus import message_bus, ChannelType, InboundMessage, OutboundMessage

class DiscordGateway:
    """Discord Bot Gateway using discord.py integrated with unified MessageBus."""
    def __init__(self):
        self.client: Optional[discord.Client] = None
        self._task: Optional[asyncio.Task] = None
        self.is_running: bool = False
        self.token: Optional[str] = settings.DISCORD_BOT_TOKEN
        self.allowed_channels: List[int] = []
        self.allowed_users: List[int] = []
        
        # Register outbound handler
        message_bus.register_channel_sender(ChannelType.DISCORD, self.send_to_discord)

    def _create_client(self) -> discord.Client:
        intents = discord.Intents.default()
        intents.message_content = True
        client = discord.Client(intents=intents)

        @client.event
        async def on_ready():
            self.is_running = True
            logger.info(f"✓ Discord Gateway logged in as: {client.user} (ID: {client.user.id})")
            AuditLogger.log_event("DISCORD_GATEWAY_ONLINE", "discord", {"username": str(client.user)})

        @client.event
        async def on_message(message: discord.Message):
            # Do not reply to self
            if message.author == client.user:
                return

            # Check channel whitelist if configured
            if self.allowed_channels and message.channel.id not in self.allowed_channels:
                return

            # Check user whitelist if configured
            if self.allowed_users and message.author.id not in self.allowed_users:
                return

            # Trigger Discord typing indicator
            async with message.channel.typing():
                inbound = InboundMessage(
                    channel=ChannelType.DISCORD,
                    sender_id=str(message.author.id),
                    sender_name=message.author.display_name,
                    session_id=f"discord_{message.channel.id}",
                    text=message.content,
                    metadata={
                        "channel_id": message.channel.id,
                        "guild_id": message.guild.id if message.guild else None,
                        "message_id": message.id
                    }
                )

                reply_text = await message_bus.dispatch_inbound(inbound)

            # Auto-split long messages (Discord has 2000 char limit)
            max_len = 1900
            for i in range(0, len(reply_text), max_len):
                chunk = reply_text[i:i + max_len]
                await message.channel.send(chunk)

        return client

    async def start(self, token: Optional[str] = None, allowed_channels: Optional[List[int]] = None):
        """Start the Discord Gateway client."""
        bot_token = token or self.token
        if not bot_token:
            raise ValueError("No Discord Bot Token configured")

        if self.is_running:
            return

        if allowed_channels:
            self.allowed_channels = allowed_channels

        self.token = bot_token
        self.client = self._create_client()
        self._task = asyncio.create_task(self.client.start(bot_token))
        self.is_running = True
        logger.info("✓ Discord Gateway background runner launched.")

    async def stop(self):
        """Stop the Discord Gateway client."""
        if self.client and not self.client.is_closed():
            await self.client.close()
        if self._task and not self._task.done():
            self._task.cancel()
        self.is_running = False
        logger.info("✓ Discord Gateway stopped.")

    async def send_to_discord(self, msg: OutboundMessage):
        """Send an outbound message directly to a Discord channel."""
        if not self.client or not self.is_running:
            logger.warning("Cannot send Discord message: Gateway is not active.")
            return

        try:
            channel_id = int(msg.recipient_id)
            channel = self.client.get_channel(channel_id)
            if not channel:
                channel = await self.client.fetch_channel(channel_id)

            if channel:
                max_len = 1900
                for i in range(0, len(msg.text), max_len):
                    await channel.send(msg.text[i:i + max_len])
        except Exception as e:
            logger.error(f"Failed to send outbound message to Discord: {e}")

    def get_status(self) -> Dict[str, Any]:
        """Return live status of Discord Gateway."""
        bot_user = str(self.client.user) if self.client and self.client.user else None
        guild_count = len(self.client.guilds) if self.client and self.client.is_ready() else 0
        return {
            "configured": bool(self.token),
            "running": self.is_running,
            "bot_user": bot_user,
            "guild_count": guild_count,
            "allowed_channels": self.allowed_channels
        }

discord_gateway = DiscordGateway()

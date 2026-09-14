import asyncio
from typing import Optional, List, Dict, Any
from telegram import Update, constants
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes
)
from lxion.core.config import settings
from lxion.core.logger import logger
from lxion.core.context import SessionContext
from lxion.core.agent import Agent
from lxion.channels.bus import message_bus, ChannelType, InboundMessage, OutboundMessage
from lxion.tools.registry import registry
from lxion.llm.token_tracker import tracker

class TelegramGateway:
    def __init__(self, token: Optional[str] = None):
        self.token = token or settings.TELEGRAM_BOT_TOKEN
        self.app: Optional[Application] = None
        self.agent = Agent()
        self.sessions: Dict[int, SessionContext] = {}
        self.allowed_users: List[str] = []
        self._is_running: bool = False
        self.bot_username: Optional[str] = None
        self.session_file = settings.WORKSPACE_DIR / "telegram_session.json"
        self.last_chat_id: Optional[int] = self._load_last_chat_id()

    def _load_last_chat_id(self) -> Optional[int]:
        if self.session_file.exists():
            try:
                import json
                data = json.loads(self.session_file.read_text(encoding="utf-8"))
                return data.get("last_chat_id")
            except Exception:
                pass
        return 7045828398

    def _save_last_chat_id(self, chat_id: int, user_name: str = ""):
        try:
            import json
            self.session_file.write_text(json.dumps({"last_chat_id": chat_id, "user": user_name}), encoding="utf-8")
        except Exception:
            pass

    @property
    def is_running(self) -> bool:
        return self._is_running

    def _is_allowed(self, user_id: int) -> bool:
        if not self.allowed_users:
            return True
        return str(user_id) in self.allowed_users

    async def _split_and_send(self, update: Update, text: str):
        """Split messages longer than Telegram's 4096 char limit."""
        max_len = 4000
        for i in range(0, len(text), max_len):
            chunk = text[i:i + max_len]
            try:
                await update.message.reply_text(chunk, parse_mode=constants.ParseMode.MARKDOWN)
            except Exception:
                await update.message.reply_text(chunk)

    async def _cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not update.effective_user or not update.message:
            return
        user = update.effective_user
        if not self._is_allowed(user.id):
            await update.message.reply_text("⛔ Unauthorized access.")
            return

        greeting = (
            f"⚡ *Halo, {user.first_name}! Saya LXION.*\n\n"
            f"Asisten AI otonom pribadi Anda siap digunakan.\n"
            f"Ketik pertanyaan atau tugas apa saja untuk langsung berinteraksi, "
            f"atau gunakan perintah:\n\n"
            f"• `/tools` - Lihat daftar tools aktif\n"
            f"• `/stats` - Cek pemakaian token\n"
            f"• `/clear` - Reset riwayat percakapan\n"
            f"• `/help` - Bantuan lengkap"
        )
        await update.message.reply_text(greeting, parse_mode=constants.ParseMode.MARKDOWN)

    async def _cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not update.message:
            return
        help_text = (
            "🛠 *Perintah Tersedia:*\n"
            "• `/tools` - Daftar semua tool agen\n"
            "• `/stats` - Telemetri token dan latensi\n"
            "• `/clear` - Bersihkan riwayat chat\n"
            "• Kirim pesan teks biasa untuk berinteraksi dengan LXION."
        )
        await update.message.reply_text(help_text, parse_mode=constants.ParseMode.MARKDOWN)

    async def _cmd_tools(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not update.message:
            return
        tools = registry.get_all_tools()
        tool_names = [f"• `{t.name}`: {t.description[:60]}..." for t in tools]
        msg = f"🔧 *{len(tools)} Tools Aktif di LXION:*\n\n" + "\n".join(tool_names)
        await self._split_and_send(update, msg)

    async def _cmd_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not update.message:
            return
        stats = tracker.get_summary()
        msg = (
            f"📊 *Telemetri Penggunaan LXION:*\n"
            f"• Total Requests: `{stats['total_requests']}`\n"
            f"• Prompt Tokens: `{stats['prompt_tokens']}`\n"
            f"• Completion Tokens: `{stats['completion_tokens']}`\n"
            f"• Total Tokens: `{stats['total_tokens']}`\n"
            f"• Model Terakhir: `{stats['last_model']}`\n"
            f"• Latensi Terakhir: `{stats['last_latency_ms']} ms`"
        )
        await update.message.reply_text(msg, parse_mode=constants.ParseMode.MARKDOWN)

    async def _cmd_clear(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not update.effective_chat or not update.message:
            return
        chat_id = update.effective_chat.id
        self.sessions[chat_id] = SessionContext(session_id=str(chat_id))
        await update.message.reply_text("🧹 Konteks percakapan telah dibersihkan.")

    async def _handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not update.message or not update.message.text or not update.effective_user or not update.effective_chat:
            return

        user = update.effective_user
        chat = update.effective_chat

        # Block messages from bots (prevents echo / self-reply loops)
        if user.is_bot:
            return

        # Block if message originated from this bot itself
        if self.app and self.app.bot and user.id == self.app.bot.id:
            return

        if not self._is_allowed(user.id):
            await update.message.reply_text("⛔ Akses ditolak.")
            return


        if chat.id not in self.sessions:
            self.sessions[chat.id] = SessionContext(session_id=str(chat.id))
        self.last_chat_id = chat.id
        self._save_last_chat_id(chat.id, user.first_name)

        user_text = update.message.text
        
        try:
            await context.bot.send_chat_action(chat_id=chat.id, action=constants.ChatAction.TYPING)
        except Exception:
            pass

        inbound = InboundMessage(
            channel=ChannelType.TELEGRAM,
            sender_id=str(user.id),
            sender_name=user.first_name,
            session_id=str(chat.id),
            text=user_text
        )

        try:
            # Route through unified MessageBus
            response = await message_bus.handle_inbound(inbound)
            if not response:
                session_ctx = self.sessions[chat.id]
                response = await self.agent.run(user_prompt=user_text, context=session_ctx)
            await self._split_and_send(update, response)
        except Exception as e:
            logger.error(f"Telegram agent error: {e}")
            await update.message.reply_text(f"⚠️ Terjadi kesalahan saat memproses: {e}")

    async def send_outbound(self, msg: OutboundMessage):
        """Send message or document from bus to Telegram chat."""
        if not self.app or not self.app.bot:
            return
        try:
            recipient = msg.recipient_id
            if recipient == "default" or recipient == "broadcast":
                if self.sessions:
                    recipient = list(self.sessions.keys())[-1]
                elif self.last_chat_id:
                    recipient = self.last_chat_id
                else:
                    logger.warning("No active chat sessions for outbound Telegram message.")
                    return

            file_rel = msg.metadata.get("file_path") or msg.metadata.get("file_rel")
            if msg.metadata.get("is_document") and file_rel:
                from lxion.memory.workspace import workspace
                file_abs = workspace._resolve_safe_path(file_rel)
                if file_abs.exists() and file_abs.is_file():
                    with open(file_abs, "rb") as doc:
                        await self.app.bot.send_document(
                            chat_id=int(recipient),
                            document=doc,
                            filename=file_abs.name,
                            caption=msg.text or None
                        )
                    logger.info(f"✓ Dispatched document {file_abs.name} to Telegram chat {recipient}")
                    return

            try:
                await self.app.bot.send_message(
                    chat_id=int(recipient),
                    text=msg.text,
                    parse_mode=constants.ParseMode.MARKDOWN
                )
            except Exception:
                await self.app.bot.send_message(
                    chat_id=int(recipient),
                    text=msg.text
                )
            logger.info(f"✓ Dispatched outbound Telegram message to chat {recipient}")
        except Exception as e:
            logger.error(f"Failed to send outbound telegram message: {e}")

    def build_application(self) -> Application:
        if not self.token:
            raise ValueError("TELEGRAM_BOT_TOKEN not configured.")
        
        builder = Application.builder().token(self.token)
        app = builder.build()

        app.add_handler(CommandHandler("start", self._cmd_start))
        app.add_handler(CommandHandler("help", self._cmd_help))
        app.add_handler(CommandHandler("tools", self._cmd_tools))
        app.add_handler(CommandHandler("stats", self._cmd_stats))
        app.add_handler(CommandHandler("clear", self._cmd_clear))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_message))

        self.app = app
        message_bus.register_channel_sender(ChannelType.TELEGRAM, self.send_outbound)
        return app

    async def start(self, token: Optional[str] = None) -> bool:
        """Start or restart the Telegram bot with the given or configured token."""
        if token:
            self.token = token
        if not self.token:
            self.token = settings.TELEGRAM_BOT_TOKEN
        if not self.token:
            logger.warning("Cannot start Telegram Bot: no token provided.")
            return False

        if self._is_running:
            await self.stop()

        try:
            self.build_application()
            await self.app.initialize()
            await self.app.start()
            await self.app.updater.start_polling(drop_pending_updates=False)
            self._is_running = True
            self.bot_username = self.app.bot.username if self.app.bot else None
            logger.info(f"✓ Telegram Bot gateway started polling (@{self.bot_username})")
            return True
        except Exception as e:
            logger.error(f"Failed to start Telegram Bot: {e}")
            self._is_running = False
            return False

    async def stop(self):
        """Gracefully stop the Telegram bot polling."""
        if self.app and self._is_running:
            try:
                if self.app.updater and self.app.updater.running:
                    await self.app.updater.stop()
                if self.app.running:
                    await self.app.stop()
                await self.app.shutdown()
            except Exception as e:
                logger.warning(f"Error while stopping Telegram Bot: {e}")
            finally:
                self._is_running = False
                logger.info("🛑 Telegram Bot gateway stopped")

    def get_status(self) -> Dict[str, Any]:
        return {
            "configured": bool(self.token),
            "running": self._is_running,
            "bot_name": self.app.bot.first_name if (self.app and self.app.bot and self._is_running) else None,
            "username": self.bot_username or (self.app.bot.username if (self.app and self.app.bot) else None)
        }

telegram_gateway = TelegramGateway()

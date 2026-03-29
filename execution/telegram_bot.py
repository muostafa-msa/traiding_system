from __future__ import annotations

import asyncio
import threading
from datetime import datetime, timezone

from core.config import AppConfig
from core.logger import get_logger
from storage.database import Database

logger = get_logger(__name__)


class TelegramBot:
    def __init__(self, config: AppConfig, database: Database):
        self._config = config
        self._db = database
        self._token = config.telegram_bot_token
        self._chat_id = config.telegram_chat_id
        self._bot = None
        self._app = None
        self._thread = None
        self._started_at: datetime | None = None
        self.last_cycle_time: datetime | None = None

    @property
    def active(self) -> bool:
        return bool(self._token and self._chat_id)

    def start(self) -> None:
        if not self.active:
            logger.info("Telegram bot disabled (no token or chat ID configured)")
            return

        try:
            from telegram.ext import ApplicationBuilder

            self._app = ApplicationBuilder().token(self._token).build()
            self._register_handlers()
            self._started_at = datetime.now(timezone.utc)

            self._thread = threading.Thread(target=self._run_polling, daemon=True)
            self._thread.start()
            logger.info("Telegram bot started")
        except Exception as e:
            logger.error("Failed to start Telegram bot: %s", e)

    def _run_polling(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._app.initialize())
            loop.run_until_complete(self._app.start())
            loop.run_until_complete(self._app.updater.start_polling())
            loop.run_forever()
        except Exception as e:
            logger.error("Telegram polling error: %s", e)

    def _register_handlers(self) -> None:
        from telegram.ext import CommandHandler

        self._app.add_handler(CommandHandler("status", self._cmd_status))
        self._app.add_handler(CommandHandler("last_signal", self._cmd_last_signal))
        self._app.add_handler(CommandHandler("performance", self._cmd_performance))
        self._app.add_handler(CommandHandler("kill", self._cmd_kill))

    async def _check_chat_id(self, update, context) -> bool:
        if not update.message or not update.message.chat_id:
            return False
        if str(update.message.chat_id) != str(self._chat_id):
            logger.warning(
                "Unauthorized access from chat_id: %s", update.message.chat_id
            )
            return False
        return True

    async def _cmd_status(self, update, context) -> None:
        if not await self._check_chat_id(update, context):
            return
        state = self._db.get_account_state()
        open_count = self._db.get_open_positions_count()
        uptime = ""
        if self._started_at:
            delta = datetime.now(timezone.utc) - self._started_at
            hours, remainder = divmod(int(delta.total_seconds()), 3600)
            mins, _ = divmod(remainder, 60)
            uptime = f"{hours}h {mins}m"
        last_cycle = self.last_cycle_time.strftime("%H:%M:%S UTC") if self.last_cycle_time else "N/A"
        msg = (
            f"SYSTEM STATUS\n"
            f"Uptime: {uptime or 'N/A'}\n"
            f"Last Cycle: {last_cycle}\n"
            f"Open Positions: {open_count}\n"
            f"Kill Switch: {'ACTIVE' if state.kill_switch_active else 'INACTIVE'}\n"
            f"Daily P&L: {state.daily_pnl:.2f}\n"
            f"Capital: {state.capital:.2f}"
        )
        await update.message.reply_text(msg)

    async def _cmd_last_signal(self, update, context) -> None:
        if not await self._check_chat_id(update, context):
            return
        signal = self._db.get_last_signal("XAU/USD")
        if signal is None:
            await update.message.reply_text("No signals found.")
            return
        msg = (
            f"LAST SIGNAL\n"
            f"Asset: {signal['asset']}\n"
            f"Direction: {signal['direction']}\n"
            f"Entry: {signal['entry_price']}\n"
            f"SL: {signal['stop_loss']}\n"
            f"TP: {signal['take_profit']}\n"
            f"Status: {signal['status']}\n"
            f"Time: {signal['created_at']}"
        )
        await update.message.reply_text(msg)

    async def _cmd_performance(self, update, context) -> None:
        if not await self._check_chat_id(update, context):
            return
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        perf = self._db.get_daily_performance(today)
        state = self._db.get_account_state()
        msg = (
            f"DAILY PERFORMANCE ({today})\n"
            f"Total Signals: {perf['total_signals']}\n"
            f"Trades Taken: {perf['trades_taken']}\n"
            f"Win Rate: {perf['win_rate']:.1%}\n"
            f"Profit Factor: {perf['profit_factor']:.2f}\n"
            f"Daily P&L: {state.daily_pnl:.2f}"
        )
        await update.message.reply_text(msg)

    async def _cmd_kill(self, update, context) -> None:
        if not await self._check_chat_id(update, context):
            return
        self._db.update_account_state(kill_switch_active=True)
        await update.message.reply_text(
            "KILL SWITCH ACTIVATED. All signals blocked until UTC midnight reset."
        )

    def stop(self) -> None:
        if not self.active or self._app is None:
            return
        try:
            loop = asyncio.new_event_loop()
            loop.run_until_complete(self._app.updater.stop())
            loop.run_until_complete(self._app.stop())
            loop.run_until_complete(self._app.shutdown())
            logger.info("Telegram bot stopped")
        except Exception as e:
            logger.error("Error stopping Telegram bot: %s", e)

    def broadcast(self, message: str) -> None:
        if not self.active or self._app is None:
            logger.info("Broadcast (no-op): %s", message[:100])
            return
        try:
            loop = asyncio.new_event_loop()
            loop.run_until_complete(
                self._app.bot.send_message(chat_id=self._chat_id, text=message)
            )
            loop.close()
        except Exception as e:
            logger.error("Broadcast error: %s", e)

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from core.config import AppConfig
from core.types import TradeSignal
from execution.telegram_bot import TelegramBot
from storage.database import Database
from tests.conftest import _default_sentiment_fields


@pytest.fixture
def bot_config() -> AppConfig:
    return AppConfig(
        market_data_provider="twelvedata",
        market_data_api_key="test",
        initial_capital=10000.0,
        telegram_bot_token="fake_token",
        telegram_chat_id="123456",
        signal_threshold=0.68,
        max_risk_per_trade=0.01,
        max_daily_risk=0.03,
        max_open_positions=2,
        kill_switch_threshold=0.05,
        sl_atr_multiplier=1.5,
        tp_atr_multiplier=3.0,
        log_level="INFO",
        db_path=":memory:",
        **_default_sentiment_fields(),
    )


@pytest.fixture
def noop_config() -> AppConfig:
    return AppConfig(
        market_data_provider="twelvedata",
        market_data_api_key="test",
        initial_capital=10000.0,
        telegram_bot_token="",
        telegram_chat_id="",
        signal_threshold=0.68,
        max_risk_per_trade=0.01,
        max_daily_risk=0.03,
        max_open_positions=2,
        kill_switch_threshold=0.05,
        sl_atr_multiplier=1.5,
        tp_atr_multiplier=3.0,
        log_level="INFO",
        db_path=":memory:",
        **_default_sentiment_fields(),
    )


@pytest.fixture
def bot(bot_config: AppConfig) -> TelegramBot:
    db = Database(bot_config)
    return TelegramBot(bot_config, db)


def _make_update(chat_id: str = "123456") -> MagicMock:
    update = MagicMock()
    update.message = MagicMock()
    update.message.chat_id = int(chat_id)
    update.message.reply_text = AsyncMock()
    return update


class TestChatIDRestriction:
    @pytest.mark.asyncio
    async def test_authorized_chat_id_passes(self, bot: TelegramBot):
        update = _make_update("123456")
        result = await bot._check_chat_id(update, None)
        assert result is True

    @pytest.mark.asyncio
    async def test_unauthorized_chat_id_rejected(self, bot: TelegramBot):
        update = _make_update("999999")
        result = await bot._check_chat_id(update, None)
        assert result is False

    @pytest.mark.asyncio
    async def test_unauthorized_does_not_reply(self, bot: TelegramBot):
        update = _make_update("999999")
        await bot._cmd_status(update, None)
        update.message.reply_text.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_message_rejected(self, bot: TelegramBot):
        update = MagicMock()
        update.message = None
        result = await bot._check_chat_id(update, None)
        assert result is False


class TestStatusCommand:
    @pytest.mark.asyncio
    async def test_status_returns_system_info(self, bot: TelegramBot):
        update = _make_update("123456")
        await bot._cmd_status(update, None)
        update.message.reply_text.assert_called_once()
        msg = update.message.reply_text.call_args[0][0]
        assert "SYSTEM STATUS" in msg
        assert "Last Cycle: N/A" in msg
        assert "Kill Switch: INACTIVE" in msg
        assert "Capital: 10000.00" in msg

    @pytest.mark.asyncio
    async def test_status_shows_last_cycle_time(self, bot: TelegramBot):
        bot.last_cycle_time = datetime(2026, 3, 29, 14, 30, 0, tzinfo=timezone.utc)
        update = _make_update("123456")
        await bot._cmd_status(update, None)
        msg = update.message.reply_text.call_args[0][0]
        assert "Last Cycle: 14:30:00 UTC" in msg

    @pytest.mark.asyncio
    async def test_status_shows_kill_switch_active(self, bot: TelegramBot):
        bot._db.update_account_state(kill_switch_active=True)
        update = _make_update("123456")
        await bot._cmd_status(update, None)
        msg = update.message.reply_text.call_args[0][0]
        assert "Kill Switch: ACTIVE" in msg

    @pytest.mark.asyncio
    async def test_status_shows_live_open_positions(self, bot: TelegramBot):
        signal = TradeSignal(
            asset="XAU/USD",
            direction="BUY",
            entry_price=2350.0,
            stop_loss=2335.0,
            take_profit=2380.0,
            probability=0.85,
            reasoning="Test",
            timeframe="1h",
            timestamp=datetime(2026, 1, 15, 10, 0, tzinfo=timezone.utc),
        )
        sid = bot._db.save_signal(signal, "approved")
        bot._db.open_trade(sid, 0.1, 2350.0)
        update = _make_update("123456")
        await bot._cmd_status(update, None)
        msg = update.message.reply_text.call_args[0][0]
        assert "Open Positions: 1" in msg


class TestLastSignalCommand:
    @pytest.mark.asyncio
    async def test_last_signal_no_signals(self, bot: TelegramBot):
        update = _make_update("123456")
        await bot._cmd_last_signal(update, None)
        update.message.reply_text.assert_called_once()
        msg = update.message.reply_text.call_args[0][0]
        assert "No signals found" in msg

    @pytest.mark.asyncio
    async def test_last_signal_with_signal(self, bot: TelegramBot):
        signal = TradeSignal(
            asset="XAU/USD",
            direction="BUY",
            entry_price=2350.0,
            stop_loss=2335.0,
            take_profit=2380.0,
            probability=0.85,
            reasoning="Test",
            timeframe="1h",
            timestamp=datetime(2026, 1, 15, 10, 0, tzinfo=timezone.utc),
        )
        bot._db.save_signal(signal, "approved")
        update = _make_update("123456")
        await bot._cmd_last_signal(update, None)
        msg = update.message.reply_text.call_args[0][0]
        assert "LAST SIGNAL" in msg
        assert "BUY" in msg
        assert "approved" in msg


class TestPerformanceCommand:
    @pytest.mark.asyncio
    async def test_performance_returns_daily_stats(self, bot: TelegramBot):
        update = _make_update("123456")
        await bot._cmd_performance(update, None)
        update.message.reply_text.assert_called_once()
        msg = update.message.reply_text.call_args[0][0]
        assert "DAILY PERFORMANCE" in msg
        assert "Total Signals: 0" in msg
        assert "Daily P&L: 0.00" in msg

    @pytest.mark.asyncio
    async def test_performance_with_data(self, bot: TelegramBot):
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        bot._db.update_daily_performance(
            today, total_signals=5, trades_taken=3, win_rate=0.667, profit_factor=2.1
        )
        update = _make_update("123456")
        await bot._cmd_performance(update, None)
        msg = update.message.reply_text.call_args[0][0]
        assert "Total Signals: 5" in msg
        assert "Win Rate: 66.7%" in msg


class TestKillCommand:
    @pytest.mark.asyncio
    async def test_kill_activates_kill_switch(self, bot: TelegramBot):
        update = _make_update("123456")
        await bot._cmd_kill(update, None)
        state = bot._db.get_account_state()
        assert state.kill_switch_active is True
        update.message.reply_text.assert_called_once()
        msg = update.message.reply_text.call_args[0][0]
        assert "KILL SWITCH ACTIVATED" in msg


class TestNoOpMode:
    def test_noop_when_no_token(self, noop_config: AppConfig):
        db = Database(noop_config)
        bot = TelegramBot(noop_config, db)
        assert bot.active is False

    def test_broadcast_noop_logs_instead(self, noop_config: AppConfig):
        db = Database(noop_config)
        bot = TelegramBot(noop_config, db)
        bot.broadcast("test message")

    def test_start_noop(self, noop_config: AppConfig):
        db = Database(noop_config)
        bot = TelegramBot(noop_config, db)
        bot.start()

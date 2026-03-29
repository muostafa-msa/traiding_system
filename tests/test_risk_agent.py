from __future__ import annotations

from datetime import datetime, timezone

import pytest

from agents.risk_agent import RiskAgent
from core.config import AppConfig
from core.types import TradeSignal
from storage.database import Database


@pytest.fixture
def risk_config() -> AppConfig:
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
    )


@pytest.fixture
def risk_agent(risk_config: AppConfig) -> RiskAgent:
    db = Database(risk_config)
    return RiskAgent(risk_config, db)


@pytest.fixture
def buy_signal() -> TradeSignal:
    return TradeSignal(
        asset="XAU/USD",
        direction="BUY",
        entry_price=2350.0,
        stop_loss=2335.0,
        take_profit=2380.0,
        probability=0.85,
        reasoning="Test signal",
        timeframe="1h",
        timestamp=datetime(2026, 1, 15, 10, 0, tzinfo=timezone.utc),
    )


class TestRiskAgentApproved:
    def test_approved_signal_with_position_sizing(
        self, risk_agent: RiskAgent, buy_signal: TradeSignal
    ):
        verdict = risk_agent.evaluate(buy_signal)
        assert verdict.approved is True
        assert verdict.position_size > 0
        assert verdict.rejection_reason is None
        assert verdict.open_positions == 0

    def test_position_size_calculation(
        self, risk_agent: RiskAgent, buy_signal: TradeSignal
    ):
        verdict = risk_agent.evaluate(buy_signal)
        capital = 10000.0
        risk_per_trade = 0.01
        risk_amount = capital * risk_per_trade
        price_risk = buy_signal.entry_price - buy_signal.stop_loss
        expected_size = risk_amount / price_risk
        assert abs(verdict.position_size - expected_size) < 1e-6

    def test_daily_risk_used_on_approve(
        self, risk_agent: RiskAgent, buy_signal: TradeSignal
    ):
        verdict = risk_agent.evaluate(buy_signal)
        assert verdict.daily_risk_used == pytest.approx(0.01, abs=0.001)


class TestKillSwitch:
    def test_kill_switch_active_blocks_signal(
        self, risk_agent: RiskAgent, risk_config: AppConfig, buy_signal: TradeSignal
    ):
        risk_agent._db.update_account_state(kill_switch_active=True)
        verdict = risk_agent.evaluate(buy_signal)
        assert verdict.approved is False
        assert "kill switch" in verdict.rejection_reason.lower()

    def test_daily_loss_exceeds_5pct_activates_kill_switch(
        self, risk_agent: RiskAgent, risk_config: AppConfig, buy_signal: TradeSignal
    ):
        capital = risk_config.initial_capital
        loss = capital * 0.06
        risk_agent._db.update_account_state(daily_pnl=-loss)
        verdict = risk_agent.evaluate(buy_signal)
        assert verdict.approved is False
        state = risk_agent._db.get_account_state()
        assert state.kill_switch_active is True


class TestMaxPositions:
    def test_rejects_at_max_positions(
        self, risk_agent: RiskAgent, risk_config: AppConfig, buy_signal: TradeSignal
    ):
        signal_id = risk_agent._db.save_signal(buy_signal, "approved")
        risk_agent._db.open_trade(signal_id, 0.1, 2350.0)
        risk_agent._db.open_trade(signal_id, 0.1, 2350.0)
        verdict = risk_agent.evaluate(buy_signal)
        assert verdict.approved is False
        assert "position" in verdict.rejection_reason.lower()

    def test_allows_below_max(
        self, risk_agent: RiskAgent, risk_config: AppConfig, buy_signal: TradeSignal
    ):
        signal_id = risk_agent._db.save_signal(buy_signal, "approved")
        risk_agent._db.open_trade(signal_id, 0.1, 2350.0)
        verdict = risk_agent.evaluate(buy_signal)
        assert verdict.approved is True


class TestDailyRiskLimitAndRR:
    def test_daily_risk_limit_rejection(
        self, risk_agent: RiskAgent, risk_config: AppConfig, buy_signal: TradeSignal
    ):
        risk_agent._db.update_account_state(
            daily_pnl=-risk_config.initial_capital * 0.025
        )
        verdict = risk_agent.evaluate(buy_signal)
        assert verdict.approved is False
        assert "daily risk" in verdict.rejection_reason.lower()

    def test_risk_reward_ratio_rejection(
        self, risk_agent: RiskAgent, buy_signal: TradeSignal
    ):
        bad_rr_signal = TradeSignal(
            asset="XAU/USD",
            direction="BUY",
            entry_price=2350.0,
            stop_loss=2345.0,
            take_profit=2352.0,
            probability=0.7,
            reasoning="Bad RR",
            timeframe="1h",
            timestamp=datetime(2026, 1, 15, 10, 0, tzinfo=timezone.utc),
        )
        verdict = risk_agent.evaluate(bad_rr_signal)
        assert verdict.approved is False
        assert "risk-reward" in verdict.rejection_reason.lower()

    def test_good_rr_passes(self, risk_agent: RiskAgent, buy_signal: TradeSignal):
        verdict = risk_agent.evaluate(buy_signal)
        price_risk = buy_signal.entry_price - buy_signal.stop_loss
        price_reward = buy_signal.take_profit - buy_signal.entry_price
        rr = price_reward / price_risk
        assert rr >= 1.8
        assert verdict.approved is True


class TestDailyReset:
    def test_utc_midnight_reset_clears_kill_switch(
        self, risk_agent: RiskAgent, risk_config: AppConfig, buy_signal: TradeSignal
    ):
        from datetime import timedelta

        risk_agent._db.update_account_state(kill_switch_active=True, daily_pnl=-600.0)
        yesterday = datetime.now(timezone.utc) - timedelta(days=1)
        risk_agent._db.update_account_state(updated_at=yesterday.isoformat())

        risk_agent._db.reset_daily_if_needed()
        verdict = risk_agent.evaluate(buy_signal)
        assert verdict.approved is True

    def test_utc_midnight_reset_clears_daily_pnl(
        self, risk_agent: RiskAgent, risk_config: AppConfig, buy_signal: TradeSignal
    ):
        from datetime import timedelta

        risk_agent._db.update_account_state(daily_pnl=-250.0)
        yesterday = datetime.now(timezone.utc) - timedelta(days=1)
        risk_agent._db.update_account_state(updated_at=yesterday.isoformat())

        risk_agent._db.reset_daily_if_needed()
        verdict = risk_agent.evaluate(buy_signal)
        assert verdict.approved is True

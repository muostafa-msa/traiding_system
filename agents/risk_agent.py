from __future__ import annotations

from core.config import AppConfig
from core.logger import get_logger
from core.types import RiskVerdict, TradeSignal
from storage.database import Database

logger = get_logger(__name__)


class RiskAgent:
    def __init__(self, config: AppConfig, database: Database):
        self._config = config
        self._db = database

    def evaluate(self, signal: TradeSignal) -> RiskVerdict:
        state = self._db.get_account_state()
        capital = state.capital
        daily_pnl = state.daily_pnl
        open_positions = state.open_positions
        kill_active = state.kill_switch_active

        daily_risk_used = abs(min(daily_pnl, 0)) / capital if capital > 0 else 0.0

        if kill_active:
            logger.info("Signal rejected: kill switch active")
            return RiskVerdict(
                approved=False,
                position_size=0.0,
                rejection_reason="Kill switch is active",
                daily_risk_used=daily_risk_used,
                open_positions=open_positions,
            )

        if capital > 0 and daily_pnl < 0:
            daily_loss_pct = abs(daily_pnl) / capital
            if daily_loss_pct > self._config.kill_switch_threshold:
                self._db.update_account_state(kill_switch_active=True)
                logger.warning(
                    "Kill switch activated: daily loss %.2f%% exceeds %.2f%%",
                    daily_loss_pct * 100,
                    self._config.kill_switch_threshold * 100,
                )
                return RiskVerdict(
                    approved=False,
                    position_size=0.0,
                    rejection_reason=f"Daily loss {daily_loss_pct:.1%} exceeds kill switch threshold {self._config.kill_switch_threshold:.1%}",
                    daily_risk_used=daily_risk_used,
                    open_positions=open_positions,
                )

        prospective_risk = daily_risk_used + self._config.max_risk_per_trade
        if prospective_risk > self._config.max_daily_risk:
            logger.info(
                "Signal rejected: daily risk limit %.2f%% would exceed %.2f%%",
                prospective_risk * 100,
                self._config.max_daily_risk * 100,
            )
            return RiskVerdict(
                approved=False,
                position_size=0.0,
                rejection_reason=f"Daily risk limit {self._config.max_daily_risk:.1%} would be exceeded ({prospective_risk:.1%})",
                daily_risk_used=daily_risk_used,
                open_positions=open_positions,
            )

        current_open = self._db.get_open_positions_count()
        if current_open >= self._config.max_open_positions:
            logger.info(
                "Signal rejected: %d open positions (max %d)",
                current_open,
                self._config.max_open_positions,
            )
            return RiskVerdict(
                approved=False,
                position_size=0.0,
                rejection_reason=f"Max open positions reached ({current_open}/{self._config.max_open_positions})",
                daily_risk_used=daily_risk_used,
                open_positions=current_open,
            )

        if self._db.is_blackout_active():
            logger.info("Signal rejected: news blackout period active")
            return RiskVerdict(
                approved=False,
                position_size=0.0,
                rejection_reason="News blackout period",
                daily_risk_used=daily_risk_used,
                open_positions=current_open,
            )

        rr = self._calculate_risk_reward(signal)
        if rr < 1.8:
            logger.info("Signal rejected: risk-reward ratio %.2f < 1.8", rr)
            return RiskVerdict(
                approved=False,
                position_size=0.0,
                rejection_reason=f"Risk-reward ratio {rr:.2f} below minimum 1.8",
                daily_risk_used=daily_risk_used,
                open_positions=current_open,
            )

        position_size = self._calculate_position_size(signal, capital)
        logger.info("Signal approved: position_size=%.4f, RR=%.2f", position_size, rr)
        return RiskVerdict(
            approved=True,
            position_size=position_size,
            rejection_reason=None,
            daily_risk_used=daily_risk_used + self._config.max_risk_per_trade,
            open_positions=current_open,
        )

    def _calculate_risk_reward(self, signal: TradeSignal) -> float:
        if signal.direction == "BUY":
            price_risk = signal.entry_price - signal.stop_loss
            price_reward = signal.take_profit - signal.entry_price
        else:
            price_risk = signal.stop_loss - signal.entry_price
            price_reward = signal.entry_price - signal.take_profit

        if price_risk <= 0:
            return 0.0
        return price_reward / price_risk

    def _calculate_position_size(self, signal: TradeSignal, capital: float) -> float:
        risk_amount = capital * self._config.max_risk_per_trade

        if signal.direction == "BUY":
            price_risk = signal.entry_price - signal.stop_loss
        else:
            price_risk = signal.stop_loss - signal.entry_price

        if price_risk <= 0:
            return 0.0

        return risk_amount / price_risk

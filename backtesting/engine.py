from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime

from agents.chart_agent import ChartAgent
from agents.prediction_agent import PredictionAgent
from agents.risk_agent import RiskAgent
from agents.signal_agent import SignalAgent
from core.config import AppConfig
from core.logger import get_logger
from core.types import (
    MacroSentiment,
    OHLCBar,
    PricePrediction,
    TradeSignal,
)
from models.model_manager import ModelManager
from storage.database import Database

logger = get_logger(__name__)


@dataclass
class SimulatedAccount:
    capital: float
    open_positions: int = 0
    daily_pnl: float = 0.0
    kill_switch_active: bool = False
    open_trades: list = field(default_factory=list)
    _current_date: str | None = field(default=None, repr=False)

    def to_risk_override(self) -> dict:
        return {
            "capital": self.capital,
            "open_positions": self.open_positions,
            "daily_pnl": self.daily_pnl,
            "kill_switch_active": self.kill_switch_active,
        }

    def update_daily_reset(self, current_date: str) -> None:
        if self._current_date is not None and current_date != self._current_date:
            self.daily_pnl = 0.0
            self.kill_switch_active = False
        self._current_date = current_date

    def open_trade(self, trade: dict) -> None:
        self.open_trades.append(trade)
        self.open_positions = len(self.open_trades)

    def close_trade(self, trade: dict, exit_price: float, pnl: float) -> None:
        self.open_trades.remove(trade)
        self.open_positions = len(self.open_trades)
        self.capital += pnl
        self.daily_pnl += pnl


@dataclass
class BacktestResult:
    trades: list[dict] = field(default_factory=list)
    initial_capital: float = 0.0
    final_capital: float = 0.0
    total_bars: int = 0
    start_date: datetime | None = None
    end_date: datetime | None = None
    rejected_signals: int = 0
    scoring_method: str = "fallback"


_TIMEFRAME_INTERVALS: dict[str, int] = {
    "5min": 5 * 60,
    "15min": 15 * 60,
    "1h": 60 * 60,
    "4h": 4 * 60 * 60,
}


class BacktestEngine:
    def __init__(
        self,
        config: AppConfig,
        database: Database,
        bars: list[OHLCBar],
        timeframe: str = "1h",
        initial_capital: float = 10000.0,
        sentiment_score: float = 0.0,
        verbose: bool = False,
    ):
        self._config = config
        self._database = database
        self._bars = bars
        self._timeframe = timeframe
        self._initial_capital = initial_capital
        self._sentiment_score = sentiment_score
        self._verbose = verbose

        self._chart_agent = ChartAgent()

        lstm_file = os.path.join(config.lstm_model_path, "lstm.pt")
        if not os.path.exists(lstm_file):
            logger.warning(
                "LSTM model not found at %s. Using fallback scoring method.",
                config.lstm_model_path,
            )

        xgb_file = os.path.join(config.xgboost_model_path, "classifier.pkl")
        xgb_json = os.path.join(config.xgboost_model_path, "model.json")
        if not os.path.exists(xgb_file) and not os.path.exists(xgb_json):
            logger.warning(
                "XGBoost model not found at %s. Using fallback scoring method.",
                config.xgboost_model_path,
            )

        self._scoring_method = "fallback"

        model_manager = ModelManager(config)
        self._prediction_agent = PredictionAgent(config, model_manager)
        self._signal_agent = SignalAgent(config)
        self._risk_agent = RiskAgent(config, database)

        self._sim_account = SimulatedAccount(capital=initial_capital)
        self._trade_counter = 0

    def run(self) -> BacktestResult:
        bars = self._bars
        sim = self._sim_account
        trades: list[dict] = []
        rejected = 0
        total_bars = len(bars)
        gap_after_bar: int | None = None

        for i in range(200, total_bars):
            bar = bars[i]
            current_date = bar.timestamp.strftime("%Y-%m-%d")
            sim.update_daily_reset(current_date)

            gap_detected = self._check_gap(bars, i)
            if gap_detected:
                gap_after_bar = i
                if self._verbose:
                    logger.debug(
                        "Gap detected at bar %d (%s)", i, bar.timestamp.isoformat()
                    )
                self._close_open_trades_at_price(
                    trades, sim, bar.close, "end_of_data", i, bar.timestamp
                )
                continue

            if gap_after_bar is not None:
                if i <= gap_after_bar:
                    continue
                gap_after_bar = None

            self._check_exits(trades, sim, bar, i)

            window = bars[max(0, i - 250) : i + 1]
            if len(window) < 200:
                continue

            try:
                analysis = self._chart_agent.analyze(window, self._timeframe)
            except Exception as e:
                logger.warning("ChartAgent failed at bar %d: %s", i, e)
                continue

            sentiment = MacroSentiment(
                macro_score=self._sentiment_score,
                headline_count=0,
                is_blackout=False,
            )

            try:
                prediction = self._prediction_agent.predict(window, analysis.indicators)
            except Exception as e:
                logger.warning("PredictionAgent failed at bar %d: %s", i, e)
                prediction = PricePrediction(
                    direction="NEUTRAL",
                    confidence=0.0,
                    volatility=0.0,
                    trend_strength=0.0,
                    horizon_bars=12,
                )

            try:
                decision = self._signal_agent.decide(analysis, sentiment, prediction)
                self._scoring_method = decision.scoring_method
            except Exception as e:
                logger.warning("SignalAgent failed at bar %d: %s", i, e)
                continue

            if decision.direction == "NO_TRADE":
                continue

            atr = analysis.indicators.atr
            if atr <= 0:
                continue

            signal = self._create_signal(decision, bar, atr, i)
            if signal is None:
                continue

            verdict = self._risk_agent.evaluate(
                signal, account_override=sim.to_risk_override()
            )

            if not verdict.approved:
                rejected += 1
                continue

            trade = {
                "id": self._trade_counter,
                "direction": signal.direction,
                "entry_bar_index": i,
                "exit_bar_index": None,
                "entry_timestamp": bar.timestamp,
                "exit_timestamp": None,
                "entry_price": signal.entry_price,
                "exit_price": None,
                "stop_loss": signal.stop_loss,
                "take_profit": signal.take_profit,
                "position_size": verdict.position_size,
                "pnl": 0.0,
                "pnl_percent": 0.0,
                "exit_reason": None,
                "probability": decision.probability,
            }
            self._trade_counter += 1
            sim.open_trade(trade)

            if self._verbose:
                print(
                    f"  [BAR {i}] {signal.direction} @ {signal.entry_price:.2f} | "
                    f"SL: {signal.stop_loss:.2f} | TP: {signal.take_profit:.2f} | "
                    f"Prob: {decision.probability:.2f}"
                )

        last_bar = bars[-1]
        self._close_open_trades_at_price(
            trades,
            sim,
            last_bar.close,
            "end_of_data",
            total_bars - 1,
            last_bar.timestamp,
        )

        return BacktestResult(
            trades=trades,
            initial_capital=self._initial_capital,
            final_capital=sim.capital,
            total_bars=total_bars,
            start_date=bars[0].timestamp,
            end_date=bars[-1].timestamp,
            rejected_signals=rejected,
            scoring_method=self._scoring_method,
        )

    def _check_gap(self, bars: list[OHLCBar], index: int) -> bool:
        if index == 0:
            return False
        interval = _TIMEFRAME_INTERVALS.get(self._timeframe)
        if interval is None:
            return False
        prev_ts = bars[index - 1].timestamp
        curr_ts = bars[index].timestamp
        gap_seconds = (curr_ts - prev_ts).total_seconds()
        return gap_seconds > interval * 2

    def _check_exits(
        self,
        trades: list[dict],
        sim: SimulatedAccount,
        bar: OHLCBar,
        bar_index: int,
    ) -> None:
        for trade in list(sim.open_trades):
            direction = trade["direction"]
            sl = trade["stop_loss"]
            tp = trade["take_profit"]
            entry = trade["entry_price"]
            size = trade["position_size"]

            sl_hit = False
            tp_hit = False

            if direction == "BUY":
                if bar.low <= sl:
                    sl_hit = True
                if bar.high >= tp:
                    tp_hit = True
            else:
                if bar.high >= sl:
                    sl_hit = True
                if bar.low <= tp:
                    tp_hit = True

            if sl_hit and tp_hit:
                exit_price = sl
                exit_reason = "stop_loss"
                sign = 1 if direction == "BUY" else -1
                pnl = (exit_price - entry) * size * sign
            elif sl_hit:
                exit_price = sl
                exit_reason = "stop_loss"
                sign = 1 if direction == "BUY" else -1
                pnl = (exit_price - entry) * size * sign
            elif tp_hit:
                exit_price = tp
                exit_reason = "take_profit"
                sign = 1 if direction == "BUY" else -1
                pnl = (exit_price - entry) * size * sign
            else:
                continue

            pnl_pct = (pnl / (entry * size)) * 100 if (entry * size) != 0 else 0.0
            trade_copy = dict(trade)
            trade_copy["exit_bar_index"] = bar_index
            trade_copy["exit_timestamp"] = bar.timestamp
            trade_copy["exit_price"] = exit_price
            trade_copy["pnl"] = pnl
            trade_copy["pnl_percent"] = pnl_pct
            trade_copy["exit_reason"] = exit_reason
            trades.append(trade_copy)

            sim.close_trade(trade, exit_price, pnl)

            if self._verbose:
                pnl_sign = "+" if pnl >= 0 else ""
                print(
                    f"  [BAR {bar_index}] CLOSED:{exit_reason} @ {exit_price:.2f} | "
                    f"P&L: {pnl_sign}${pnl:.2f} ({pnl_sign}{pnl_pct:.1f}%)"
                )

    def _close_open_trades_at_price(
        self,
        trades: list[dict],
        sim: SimulatedAccount,
        price: float,
        reason: str,
        bar_index: int,
        timestamp: datetime,
    ) -> None:
        for trade in list(sim.open_trades):
            direction = trade["direction"]
            entry = trade["entry_price"]
            size = trade["position_size"]
            sign = 1 if direction == "BUY" else -1
            pnl = (price - entry) * size * sign
            pnl_pct = (pnl / (entry * size)) * 100 if (entry * size) != 0 else 0.0

            trade_copy = dict(trade)
            trade_copy["exit_bar_index"] = bar_index
            trade_copy["exit_timestamp"] = timestamp
            trade_copy["exit_price"] = price
            trade_copy["pnl"] = pnl
            trade_copy["pnl_percent"] = pnl_pct
            trade_copy["exit_reason"] = reason
            trades.append(trade_copy)

            sim.close_trade(trade, price, pnl)

    def _create_signal(
        self,
        decision,
        bar: OHLCBar,
        atr: float,
        bar_index: int,
    ) -> TradeSignal | None:
        direction = decision.direction
        close = bar.close

        if direction == "BUY":
            sl = close - self._config.sl_atr_multiplier * atr
            tp = close + self._config.tp_atr_multiplier * atr
        elif direction == "SELL":
            sl = close + self._config.sl_atr_multiplier * atr
            tp = close - self._config.tp_atr_multiplier * atr
        else:
            return None

        try:
            return TradeSignal(
                asset="XAU/USD",
                direction=direction,
                entry_price=close,
                stop_loss=sl,
                take_profit=tp,
                probability=decision.probability,
                reasoning=decision.explanation,
                timeframe=self._timeframe,
                timestamp=bar.timestamp,
            )
        except ValueError as e:
            logger.debug("Invalid signal at bar %d: %s", bar_index, e)
            return None

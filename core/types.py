from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class OHLCBar:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float

    def __post_init__(self):
        for name in ("open", "high", "low", "close"):
            val = getattr(self, name)
            if val <= 0:
                raise ValueError(f"{name} must be > 0, got {val}")
        if self.volume < 0:
            raise ValueError(f"volume must be >= 0, got {self.volume}")
        if self.high < max(self.open, self.close):
            raise ValueError("high must be >= max(open, close)")
        if self.low > min(self.open, self.close):
            raise ValueError("low must be <= min(open, close)")


@dataclass(frozen=True)
class IndicatorResult:
    rsi: float
    macd_line: float
    macd_signal: float
    macd_hist: float
    ema_20: float
    ema_50: float
    ema_200: float
    bb_upper: float
    bb_middle: float
    bb_lower: float
    atr: float
    support: float
    resistance: float
    trend_direction: str
    breakout_probability: float

    def __post_init__(self):
        if not (0 <= self.rsi <= 100):
            raise ValueError(f"rsi must be in [0, 100], got {self.rsi}")
        if self.trend_direction not in ("bullish", "bearish", "neutral"):
            raise ValueError(
                f"trend_direction must be bullish/bearish/neutral, got {self.trend_direction}"
            )
        if not (0.0 <= self.breakout_probability <= 1.0):
            raise ValueError(
                f"breakout_probability must be in [0.0, 1.0], got {self.breakout_probability}"
            )


@dataclass(frozen=True)
class TradeSignal:
    asset: str
    direction: str
    entry_price: float
    stop_loss: float
    take_profit: float
    probability: float
    reasoning: str
    timeframe: str
    timestamp: datetime

    def __post_init__(self):
        if self.direction not in ("BUY", "SELL", "NO_TRADE"):
            raise ValueError(
                f"direction must be BUY/SELL/NO_TRADE, got {self.direction}"
            )
        if not (0.0 <= self.probability <= 1.0):
            raise ValueError(
                f"probability must be in [0.0, 1.0], got {self.probability}"
            )
        if self.direction == "BUY":
            if not (self.stop_loss < self.entry_price < self.take_profit):
                raise ValueError("BUY requires stop_loss < entry_price < take_profit")
        elif self.direction == "SELL":
            if not (self.take_profit < self.entry_price < self.stop_loss):
                raise ValueError("SELL requires take_profit < entry_price < stop_loss")


@dataclass(frozen=True)
class RiskVerdict:
    approved: bool
    position_size: float
    rejection_reason: str | None
    daily_risk_used: float
    open_positions: int

    def __post_init__(self):
        if self.approved:
            if self.position_size <= 0:
                raise ValueError("approved verdict must have position_size > 0")
            if self.rejection_reason is not None:
                raise ValueError("approved verdict must have rejection_reason=None")
        else:
            if self.rejection_reason is None:
                raise ValueError("rejected verdict must have a rejection_reason")


@dataclass(frozen=True)
class AccountState:
    capital: float
    open_positions: int
    daily_pnl: float
    kill_switch_active: bool
    updated_at: datetime


@dataclass(frozen=True)
class FinalSignal:
    signal: TradeSignal
    risk: RiskVerdict
    formatted_message: str

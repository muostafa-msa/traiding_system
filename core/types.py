from __future__ import annotations

from dataclasses import dataclass, field
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


@dataclass(frozen=True)
class NewsItem:
    source: str
    headline: str
    url: str
    published_at: datetime
    raw_text: str = ""

    def __post_init__(self):
        if not self.headline.strip():
            raise ValueError("headline must be non-empty")
        if not self.source.strip():
            raise ValueError("source must be non-empty")


@dataclass(frozen=True)
class SentimentResult:
    classification: str
    confidence: float
    positive_score: float
    negative_score: float
    neutral_score: float

    def __post_init__(self):
        if self.classification not in ("Bullish", "Bearish", "Neutral"):
            raise ValueError(
                f"classification must be Bullish/Bearish/Neutral, got {self.classification}"
            )
        for name in ("confidence", "positive_score", "negative_score", "neutral_score"):
            val = getattr(self, name)
            if not (0.0 <= val <= 1.0):
                raise ValueError(f"{name} must be in [0.0, 1.0], got {val}")


@dataclass
class MacroSentiment:
    macro_score: float = 0.0
    headline_count: int = 0
    sentiments: list[SentimentResult] = field(default_factory=list)
    is_blackout: bool = False
    blackout_activated_at: datetime | None = None


@dataclass(frozen=True)
class PatternResult:
    pattern_type: str
    confidence: float
    direction: str
    price_level: float

    def __post_init__(self):
        valid_types = (
            "breakout",
            "triangle",
            "double_top",
            "double_bottom",
            "head_shoulders",
            "range",
        )
        if self.pattern_type not in valid_types:
            raise ValueError(
                f"pattern_type must be one of {valid_types}, got {self.pattern_type}"
            )
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError(f"confidence must be in [0.0, 1.0], got {self.confidence}")
        if self.direction not in ("BUY", "SELL", "NEUTRAL"):
            raise ValueError(
                f"direction must be BUY/SELL/NEUTRAL, got {self.direction}"
            )
        if self.price_level <= 0:
            raise ValueError(f"price_level must be > 0, got {self.price_level}")


@dataclass
class PatternDetectionResult:
    patterns: list[PatternResult] = field(default_factory=list)
    strongest_confidence: float = 0.0
    strongest_direction: str = "NEUTRAL"

    def __post_init__(self):
        if self.patterns and self.strongest_confidence == 0.0:
            best = max(self.patterns, key=lambda p: p.confidence)
            self.strongest_confidence = best.confidence
            self.strongest_direction = best.direction
        if not (0.0 <= self.strongest_confidence <= 1.0):
            raise ValueError(
                f"strongest_confidence must be in [0.0, 1.0], got {self.strongest_confidence}"
            )
        if self.strongest_direction not in ("BUY", "SELL", "NEUTRAL"):
            raise ValueError(
                f"strongest_direction must be BUY/SELL/NEUTRAL, got {self.strongest_direction}"
            )


@dataclass(frozen=True)
class PricePrediction:
    direction: str
    confidence: float
    volatility: float
    trend_strength: float
    horizon_bars: int

    def __post_init__(self):
        if self.direction not in ("BUY", "SELL", "NEUTRAL"):
            raise ValueError(
                f"direction must be BUY/SELL/NEUTRAL, got {self.direction}"
            )
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError(f"confidence must be in [0.0, 1.0], got {self.confidence}")
        if self.volatility < 0.0:
            raise ValueError(f"volatility must be >= 0.0, got {self.volatility}")
        if not (0.0 <= self.trend_strength <= 1.0):
            raise ValueError(
                f"trend_strength must be in [0.0, 1.0], got {self.trend_strength}"
            )
        if self.horizon_bars <= 0:
            raise ValueError(f"horizon_bars must be > 0, got {self.horizon_bars}")


@dataclass(frozen=True)
class ClarityScore:
    timeframe: str
    indicator_agreement: float
    pattern_confidence: float
    data_completeness: float
    composite: float = 0.0

    def __post_init__(self):
        valid_timeframes = ("5m", "15m", "1h", "4h")
        if self.timeframe not in valid_timeframes:
            raise ValueError(
                f"timeframe must be one of {valid_timeframes}, got {self.timeframe}"
            )
        for name in ("indicator_agreement", "pattern_confidence", "data_completeness"):
            val = getattr(self, name)
            if not (0.0 <= val <= 1.0):
                raise ValueError(f"{name} must be in [0.0, 1.0], got {val}")
        computed = (
            0.5 * self.indicator_agreement
            + 0.3 * self.pattern_confidence
            + 0.2 * self.data_completeness
        )
        object.__setattr__(self, "composite", computed)
        if not (0.0 <= self.composite <= 1.0):
            raise ValueError(f"composite must be in [0.0, 1.0], got {self.composite}")


@dataclass
class TimeframeAnalysis:
    timeframe: str
    indicators: IndicatorResult
    patterns: PatternDetectionResult
    clarity: ClarityScore
    bars: list[OHLCBar]
    timestamp: datetime

    def __post_init__(self):
        valid_timeframes = ("5m", "15m", "1h", "4h")
        if self.timeframe not in valid_timeframes:
            raise ValueError(
                f"timeframe must be one of {valid_timeframes}, got {self.timeframe}"
            )
        if not self.bars:
            raise ValueError("bars must be non-empty")


@dataclass
class FeatureVector:
    indicator_features: dict[str, float] = field(default_factory=dict)
    pattern_features: dict[str, float] = field(default_factory=dict)
    sentiment_features: dict[str, float] = field(default_factory=dict)
    prediction_features: dict[str, float] = field(default_factory=dict)
    derived_features: dict[str, float] = field(default_factory=dict)

    def to_array(self) -> list[float]:
        result: list[float] = []
        for key in self.feature_names():
            result.append(self._get_feature(key))
        return result

    def feature_names(self) -> list[str]:
        names: list[str] = []
        names.extend(sorted(self.indicator_features.keys()))
        names.extend(sorted(self.pattern_features.keys()))
        names.extend(sorted(self.sentiment_features.keys()))
        names.extend(sorted(self.prediction_features.keys()))
        names.extend(sorted(self.derived_features.keys()))
        return names

    def _get_feature(self, key: str) -> float:
        for d in (
            self.indicator_features,
            self.pattern_features,
            self.sentiment_features,
            self.prediction_features,
            self.derived_features,
        ):
            if key in d:
                return d[key]
        return 0.0


@dataclass(frozen=True)
class SignalDecision:
    probability: float
    direction: str
    explanation: str
    scoring_method: str
    feature_vector: FeatureVector
    timeframe: str
    clarity_score: float

    def __post_init__(self):
        if not (0.0 <= self.probability <= 1.0):
            raise ValueError(
                f"probability must be in [0.0, 1.0], got {self.probability}"
            )
        if self.direction not in ("BUY", "SELL", "NO_TRADE"):
            raise ValueError(
                f"direction must be BUY/SELL/NO_TRADE, got {self.direction}"
            )
        if self.scoring_method not in ("xgboost", "fallback"):
            raise ValueError(
                f"scoring_method must be xgboost/fallback, got {self.scoring_method}"
            )
        valid_timeframes = ("5m", "15m", "1h", "4h")
        if self.timeframe not in valid_timeframes:
            raise ValueError(
                f"timeframe must be one of {valid_timeframes}, got {self.timeframe}"
            )
        if not (0.0 <= self.clarity_score <= 1.0):
            raise ValueError(
                f"clarity_score must be in [0.0, 1.0], got {self.clarity_score}"
            )
        if self.direction != "NO_TRADE" and not self.explanation.strip():
            raise ValueError("explanation must be non-empty when direction != NO_TRADE")

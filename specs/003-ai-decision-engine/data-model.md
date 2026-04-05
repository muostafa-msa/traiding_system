# Data Model: AI Decision Engine (003)

**Date**: 2026-03-30 | **Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

## New Dataclasses (core/types.py)

### PatternResult

Represents a single detected chart pattern.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| pattern_type | str | One of: breakout, triangle, double_top, double_bottom, head_shoulders, range | Pattern identifier |
| confidence | float | 0.0 - 1.0 | Detection confidence |
| direction | str | BUY, SELL, or NEUTRAL | Implied trade direction |
| price_level | float | > 0 | Key price level associated with pattern (e.g., breakout level) |

Frozen dataclass with post_init validation (consistent with existing types).

### PatternDetectionResult

Aggregated result from all pattern detectors on a single timeframe.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| patterns | list[PatternResult] | May be empty | All detected patterns |
| strongest_confidence | float | 0.0 - 1.0 | Max confidence among detected patterns (0.0 if none) |
| strongest_direction | str | BUY, SELL, or NEUTRAL | Direction of highest-confidence pattern |

Non-frozen dataclass (contains mutable list). Computed fields derived from patterns list.

### PricePrediction

Output of the LSTM prediction model.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| direction | str | BUY, SELL, or NEUTRAL | Predicted price direction |
| confidence | float | 0.0 - 1.0 | Prediction confidence |
| volatility | float | >= 0.0 | Predicted volatility (normalized) |
| trend_strength | float | 0.0 - 1.0 | Strength of detected trend |
| horizon_bars | int | > 0 | Number of bars ahead this prediction covers |

Frozen dataclass with post_init validation.

### ClarityScore

Timeframe quality assessment for multi-timeframe selection.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| timeframe | str | 5m, 15m, 1h, 4h | Timeframe identifier |
| indicator_agreement | float | 0.0 - 1.0 | Fraction of indicators agreeing on direction |
| pattern_confidence | float | 0.0 - 1.0 | Strongest pattern confidence for this timeframe |
| data_completeness | float | 0.0 - 1.0 | 1.0 minus ratio of missing bars |
| composite | float | 0.0 - 1.0 | Weighted composite: 0.5*agreement + 0.3*pattern + 0.2*completeness |

Frozen dataclass with post_init validation. `composite` is computed at construction.

### TimeframeAnalysis

Complete analysis result for a single timeframe, cached by the chart agent.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| timeframe | str | 5m, 15m, 1h, 4h | Timeframe identifier |
| indicators | IndicatorResult | Not None | Technical indicator values |
| patterns | PatternDetectionResult | Not None | Detected patterns |
| clarity | ClarityScore | Not None | Quality assessment |
| bars | list[OHLCBar] | Non-empty | Raw price data used |
| timestamp | datetime | Not None | When this analysis was produced |

Non-frozen dataclass (contains mutable lists).

### FeatureVector

Assembled features for XGBoost scoring.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| indicator_features | dict[str, float] | Non-empty | RSI, MACD components, EMA ratios, BB position, ATR |
| pattern_features | dict[str, float] | May have zero values | Confidence per pattern type |
| sentiment_features | dict[str, float] | May have zero values | macro_score, headline_count, is_blackout |
| prediction_features | dict[str, float] | May have zero values | direction_encoded, confidence, volatility, trend_strength |
| derived_features | dict[str, float] | May have zero values | indicator_agreement, trend_encoded, price_vs_support/resistance |

Non-frozen dataclass. Methods: `to_array() -> list[float]` for model input, `feature_names() -> list[str]` for column ordering.

### SignalDecision

Output of the signal agent combining probability, direction, and explanation.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| probability | float | 0.0 - 1.0 | Combined probability score |
| direction | str | BUY, SELL, or NO_TRADE | Determined trade direction |
| explanation | str | Non-empty if direction != NO_TRADE | Human-readable reasoning |
| scoring_method | str | xgboost or fallback | Which scoring method was used |
| feature_vector | FeatureVector | Not None | The input features used |
| timeframe | str | 5m, 15m, 1h, 4h | Selected timeframe |
| clarity_score | float | 0.0 - 1.0 | Clarity score of selected timeframe |

Frozen dataclass with post_init validation.

## Extended Existing Types

### AppConfig (core/config.py) — New Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| lstm_model_path | str | "models/lstm" | Directory for LSTM weights |
| xgboost_model_path | str | "models/xgboost" | Directory for XGBoost model file |
| ollama_base_url | str | "http://localhost:11434" | Ollama API base URL |
| ollama_model | str | "gpt-oss:20b" | Ollama model name for explanation generation |
| signal_threshold | float | 0.68 | Probability threshold for signal generation (already exists) |
| fallback_weight_indicators | float | 0.30 | Weighted formula: indicator weight |
| fallback_weight_patterns | float | 0.20 | Weighted formula: pattern weight |
| fallback_weight_sentiment | float | 0.25 | Weighted formula: sentiment weight |
| fallback_weight_prediction | float | 0.25 | Weighted formula: prediction weight |
| explanation_max_tokens | int | 150 | Max tokens for explanation generation |
| explanation_temperature | float | 0.7 | Generation temperature |
| lstm_sequence_length | int | 60 | Input sequence length for LSTM |
| decision_window_minutes | int | 15 | Window for best-signal-wins deduplication |

## Entity Relationships

```text
OHLCBar[]──→ compute_indicators() ──→ IndicatorResult
OHLCBar[]──→ detect_patterns()    ──→ PatternDetectionResult
                                            │
IndicatorResult + PatternDetectionResult ──→ ClarityScore
                                            │
ClarityScore + IndicatorResult + PatternDetectionResult + OHLCBar[] ──→ TimeframeAnalysis
                                            │
                                    (best timeframe selected)
                                            │
OHLCBar[] + IndicatorResult ──→ LSTM ──→ PricePrediction
                                            │
IndicatorResult + PatternDetectionResult + MacroSentiment + PricePrediction ──→ FeatureVector
                                            │
FeatureVector ──→ XGBoost (or fallback) ──→ SignalDecision
                                            │
                              if probability >= threshold:
                                            │
SignalDecision ──→ GPT-2B (or template) ──→ TradeSignal (with explanation)
                                            │
TradeSignal ──→ RiskAgent ──→ RiskVerdict ──→ FinalSignal ──→ Telegram
```

## State Transitions

### Model Lifecycle

```text
NOT_LOADED ──(lazy load on first use)──→ LOADED ──(inference)──→ LOADED
     ↑                                                              │
     └─────────────────(unload for memory)──────────────────────────┘
```

### Signal Decision Flow

```text
ANALYZING ──(all features assembled)──→ SCORING
SCORING ──(probability >= 0.68)──→ SIGNAL_GENERATED
SCORING ──(probability < 0.68)──→ NO_TRADE
SIGNAL_GENERATED ──(risk approved)──→ DELIVERED
SIGNAL_GENERATED ──(risk rejected)──→ REJECTED
```

### Multi-Timeframe Window

```text
IDLE ──(timeframe cycle fires)──→ ANALYSIS_COMPLETE
ANALYSIS_COMPLETE ──(within decision window)──→ PENDING_COMPARISON
PENDING_COMPARISON ──(window expires or all timeframes reported)──→ BEST_SELECTED
BEST_SELECTED ──→ scoring pipeline
```

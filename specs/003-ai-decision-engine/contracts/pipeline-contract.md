# Pipeline Contract: AI Decision Engine

**Date**: 2026-03-30 | **Feature**: 003-ai-decision-engine

This document defines the inter-agent data contracts for the Phase 3 pipeline. All data flows through frozen/non-frozen dataclasses defined in `core/types.py`. No agent imports another agent's internals — all communication is via these shared types.

## Pipeline Stage Contracts

### Stage 1: Chart Analysis

**Agent**: `chart_agent.py`
**Input**: `list[OHLCBar]` (per timeframe, minimum 200 bars)
**Output**: `TimeframeAnalysis`
**Dependencies**: `analysis/indicators.py`, `analysis/pattern_detection.py`

```
chart_agent.analyze(bars: list[OHLCBar], timeframe: str) -> TimeframeAnalysis
chart_agent.select_best_timeframe(analyses: list[TimeframeAnalysis]) -> TimeframeAnalysis
```

**Guarantees**:
- Returns a valid `TimeframeAnalysis` for any input with >= 200 bars
- Clarity score composite is always in [0.0, 1.0]
- If fewer than 200 bars, raises `ValueError`

### Stage 2: Pattern Detection

**Module**: `analysis/pattern_detection.py`
**Input**: `list[OHLCBar]` (minimum 50 bars)
**Output**: `PatternDetectionResult`

```
detect_patterns(bars: list[OHLCBar]) -> PatternDetectionResult
```

**Per-pattern detectors** (all return `PatternResult | None`):
```
detect_breakout(bars, support, resistance, atr) -> PatternResult | None
detect_triangle(bars) -> PatternResult | None
detect_double_top(bars) -> PatternResult | None
detect_double_bottom(bars) -> PatternResult | None
detect_head_shoulders(bars) -> PatternResult | None
detect_range(bars, support, resistance) -> PatternResult | None
```

**Guarantees**:
- Every returned `PatternResult` has confidence in [0.0, 1.0]
- If no patterns detected, returns `PatternDetectionResult(patterns=[], strongest_confidence=0.0, strongest_direction="NEUTRAL")`

### Stage 3: Price Prediction

**Agent**: `prediction_agent.py`
**Input**: `list[OHLCBar]`, `IndicatorResult`
**Output**: `PricePrediction`

```
prediction_agent.predict(bars: list[OHLCBar], indicators: IndicatorResult) -> PricePrediction
```

**Guarantees**:
- Always returns a valid `PricePrediction` (falls back to NEUTRAL with 0.0 confidence if model unavailable or data insufficient)
- Never raises exceptions that halt the pipeline — errors are logged and fallback returned

### Stage 4: Signal Decision (Probability Scoring)

**Agent**: `signal_agent.py`
**Input**: `TimeframeAnalysis`, `MacroSentiment`, `PricePrediction`
**Output**: `SignalDecision`

```
signal_agent.decide(
    analysis: TimeframeAnalysis,
    sentiment: MacroSentiment,
    prediction: PricePrediction
) -> SignalDecision
```

**Guarantees**:
- Probability is always in [0.0, 1.0]
- `scoring_method` accurately reflects whether XGBoost or fallback was used
- If probability < threshold: `direction = "NO_TRADE"`, `explanation = ""`
- If probability >= threshold: `explanation` is non-empty (GPT-2B or template)

### Stage 5: Signal Construction

When `SignalDecision.direction != "NO_TRADE"`:

```
TradeSignal(
    asset=config.asset,
    direction=decision.direction,
    entry_price=current_price,
    stop_loss=computed_from_atr,
    take_profit=computed_from_atr,
    probability=decision.probability,
    reasoning=decision.explanation,
    timeframe=decision.timeframe,
    timestamp=now
)
```

Then passed to existing `risk_agent.evaluate(signal) -> RiskVerdict`.

## Model Wrapper Contracts

### LSTMWrapper (models/lstm_model.py)

```
class LSTMWrapper:
    def __init__(self, config: AppConfig, model_manager: ModelManager)
    def predict(self, bars: list[OHLCBar], indicators: IndicatorResult) -> PricePrediction
    def train(self, bars: list[OHLCBar], indicators_fn: Callable) -> dict  # returns metrics
    def is_trained(self) -> bool
```

### XGBoostWrapper (models/xgboost_model.py)

```
class XGBoostWrapper:
    def __init__(self, config: AppConfig)
    def predict(self, features: FeatureVector) -> float  # returns probability 0.0-1.0
    def train(self, feature_vectors: list[FeatureVector], labels: list[int]) -> dict
    def is_trained(self) -> bool
```

### ExplanationModel (models/explanation_model.py)

```
class ExplanationModel:
    def __init__(self, config: AppConfig)
    def explain(self, decision: SignalDecision, indicators: IndicatorResult, sentiment: MacroSentiment) -> str | None
```

Uses Ollama API (`/api/generate`) to call GPT-OSS-20B for explanation generation. Returns `None` if Ollama is unavailable or generation fails.

## Fallback Contracts

All fallbacks are transparent — the caller receives the same type regardless of which path was taken.

| Component | Primary | Fallback | Distinction |
|-----------|---------|----------|-------------|
| Probability scoring | XGBoost.predict() | weighted_formula() | `SignalDecision.scoring_method` field |
| Explanation | ExplanationModel.explain() via Ollama | template_explain() | No explicit flag — both produce str |
| Prediction | LSTMWrapper.predict() | neutral_prediction() | `PricePrediction.confidence == 0.0` |

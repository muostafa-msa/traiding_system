# Data Model: Signal Quality Filtering Improvements

**Feature**: 006-signal-quality-filters
**Date**: 2026-04-07

## New Entities

### OpportunityScore

A composite quality metric that evaluates overall trade setup quality before a signal is sent.

| Field | Type | Range | Description |
|-------|------|-------|-------------|
| trend_strength | float | [0.0, 1.0] | From LSTM PricePrediction.trend_strength |
| volatility_regime | float | [0.0, 1.0] | ATR-normalized volatility favorability |
| pattern_confidence | float | [0.0, 1.0] | Strongest detected pattern's confidence |
| prediction_confidence | float | [0.0, 1.0] | LSTM prediction confidence |
| sentiment_alignment | float | [0.0, 1.0] | 1.0 if sentiment agrees with direction, 0.0 if opposes |
| indicator_agreement | float | [0.0, 1.0] | From ClarityScore.indicator_agreement |
| mtf_agreement | float | [0.0, 1.0] | Fraction of timeframes agreeing on trend |
| composite | float | [0.0, 1.0] | Weighted sum of all components |

**Weights** (summing to 1.0):

| Component | Weight |
|-----------|--------|
| trend_strength | 0.20 |
| volatility_regime | 0.15 |
| pattern_confidence | 0.15 |
| prediction_confidence | 0.15 |
| sentiment_alignment | 0.10 |
| indicator_agreement | 0.15 |
| mtf_agreement | 0.10 |

**Validation**: All fields in [0.0, 1.0]. Composite auto-computed in `__post_init__`.

**Location**: `core/types.py` (new frozen dataclass)

---

## Modified Entities

### PatternDetectionResult (existing)

**Current definition** (`core/types.py:197-215`): Mutable dataclass with `patterns: list[PatternResult]`, `strongest_confidence: float`, `strongest_direction: str`.

**Modification**: No schema change. Behavior change only:
- After all 6 detectors run, a new `_filter_contradictory_patterns()` function removes patterns whose direction opposes the strongest pattern's direction.
- NEUTRAL-direction patterns are always preserved.
- `strongest_confidence` and `strongest_direction` are recomputed from filtered results.

### AppConfig (existing)

**Current definition** (`core/config.py:9-44`): Frozen dataclass with 33 fields.

**New fields**:

| Field | Type | Default | Env Variable |
|-------|------|---------|-------------|
| prediction_agreement_enabled | bool | True | PREDICTION_AGREEMENT_ENABLED |
| mtf_confirmation_enabled | bool | True | MTF_CONFIRMATION_ENABLED |
| mtf_min_agreeing_timeframes | int | 2 | MTF_MIN_AGREEING_TIMEFRAMES |
| opportunity_score_enabled | bool | True | OPPORTUNITY_SCORE_ENABLED |
| opportunity_score_threshold | float | 0.55 | OPPORTUNITY_SCORE_THRESHOLD |

---

## Unchanged Entities (referenced but not modified)

| Entity | Location | Role in Feature |
|--------|----------|-----------------|
| PricePrediction | types.py:219-240 | Source of trend_strength, confidence, direction for agreement check and opportunity score |
| ClarityScore | types.py:243-268 | Source of indicator_agreement for opportunity score |
| TimeframeAnalysis | types.py:271-287 | Contains indicators.trend_direction for MTF consensus |
| IndicatorResult | types.py:30-57 | Source of trend_direction, RSI, MACD for message format |
| TradeSignal | types.py:61-87 | Carries signal data for S/R warning and message formatting |
| SignalDecision | types.py:326-359 | Decision output, no schema change |
| MacroSentiment | types.py:158-164 | Source of macro_score for sentiment_alignment |

---

## Entity Relationships

```
PricePrediction.direction ──┐
                             ├── Prediction Agreement Gate (signal_agent.py)
SignalDecision.direction  ──┘

PatternDetectionResult.patterns ──── Filter Contradictory (pattern_detection.py)

ChartAgent._analyses[*].indicators.trend_direction ──── MTF Consensus (chart_agent.py)

PricePrediction ──────┐
ClarityScore ─────────┤
MacroSentiment ───────┤
PatternDetectionResult┼── OpportunityScore (signal_agent.py)
TimeframeAnalysis ────┤
IndicatorResult ──────┘

TradeSignal + RiskVerdict + IndicatorResult + PatternDetectionResult ──── Telegram Format (signal_generator.py)
```

# Contract: Signal Quality Gates

**Feature**: 006-signal-quality-filters
**Date**: 2026-04-07

## Overview

Defines the signal quality gates applied sequentially in the signal pipeline. Each gate is independently configurable.

## Gate Execution Order

```
Signal Direction Determined
    │
    ├── Gate 1: Prediction Agreement (if enabled)
    │   └── LSTM direction must match signal direction
    │
    ├── Gate 2: Multi-Timeframe Confirmation (if enabled)
    │   └── At least N timeframes must agree on trend direction
    │
    ├── Gate 3: Opportunity Score (if enabled)
    │   └── Composite score must exceed threshold
    │
    └── Existing Gates (unchanged)
        ├── Probability threshold
        ├── Best signal dedup window
        └── Risk management
```

## Gate 1: Prediction Agreement

| Property | Value |
|----------|-------|
| Config | `PREDICTION_AGREEMENT_ENABLED` |
| Default | `true` |
| Location | `signal_agent.py:decide()` |
| Input | `PricePrediction.direction`, signal direction |
| Rule | prediction.direction must equal signal direction (BUY==BUY, SELL==SELL) |
| NEUTRAL handling | Treated as disagreement (rejects signal) |
| Bypass | When LSTM is unavailable (failed to load) |
| Output | NO_TRADE if disagreement |

## Gate 2: Multi-Timeframe Confirmation

| Property | Value |
|----------|-------|
| Config | `MTF_CONFIRMATION_ENABLED`, `MTF_MIN_AGREEING_TIMEFRAMES` |
| Defaults | `true`, `2` |
| Location | `scheduler.py:_evaluate_signal_if_present()` |
| Input | `ChartAgent._analyses` dict |
| Rule | Count timeframes with trend_direction matching signal direction >= threshold |
| Cold start | If total analyzed timeframes < min_agreeing, allow signal through |
| Direction mapping | bullish→BUY, bearish→SELL |
| Output | Skip `process_signal()` if insufficient agreement |

## Gate 3: Opportunity Score

| Property | Value |
|----------|-------|
| Config | `OPPORTUNITY_SCORE_ENABLED`, `OPPORTUNITY_SCORE_THRESHOLD` |
| Defaults | `true`, `0.55` |
| Location | `signal_agent.py:decide()` |
| Input | 7 weighted components (see data-model.md) |
| Rule | composite score >= threshold |
| Missing data | Components default to 0.0 |
| Output | NO_TRADE if below threshold |

## Configuration Parameters

| Parameter | Type | Default | Env Variable |
|-----------|------|---------|-------------|
| prediction_agreement_enabled | bool | true | PREDICTION_AGREEMENT_ENABLED |
| mtf_confirmation_enabled | bool | true | MTF_CONFIRMATION_ENABLED |
| mtf_min_agreeing_timeframes | int | 2 | MTF_MIN_AGREEING_TIMEFRAMES |
| opportunity_score_enabled | bool | true | OPPORTUNITY_SCORE_ENABLED |
| opportunity_score_threshold | float | 0.55 | OPPORTUNITY_SCORE_THRESHOLD |

## All-Gates-Disabled Behavior

When all 3 new gates are disabled, the system behaves identically to the pre-feature version. No regressions.

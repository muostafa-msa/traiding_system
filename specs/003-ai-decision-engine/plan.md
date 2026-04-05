# Implementation Plan: AI Decision Engine (LSTM + XGBoost + GPT-2B)

**Branch**: `003-ai-decision-engine` | **Date**: 2026-03-30 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/003-ai-decision-engine/spec.md`

## Summary

Implement the full AI decision engine pipeline for Phase 3: chart pattern detection, LSTM price prediction, XGBoost probability scoring, GPT-2B signal explanation, multi-timeframe signal selection with clarity scoring, and full pipeline orchestration. The system must fall back to weighted-formula scoring and template-based explanations when trained models are unavailable, and must operate locally on CPU with optional GPU.

## Technical Context

**Language/Version**: Python 3.12
**Primary Dependencies**: torch (>=2.0), transformers (>=4.30), scikit-learn, xgboost, pandas, numpy, ta
**Storage**: SQLite (existing — `storage/database.py`)
**Testing**: pytest, pytest-asyncio, unittest.mock
**Target Platform**: Linux/macOS local machine (CPU default, optional CUDA/MPS GPU)
**Project Type**: Standalone application (scheduled trading signal system)
**Performance Goals**: Full analysis cycle < 30 seconds per timeframe on CPU
**Constraints**: <8 GB RAM (models loaded sequentially, not simultaneously), offline inference after setup
**Scale/Scope**: Single asset (XAU/USD), 4 timeframes (5m/15m/1h/4h), 1 operator

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| §2 Local-First Architecture | PASS | All models run locally; CPU default with optional GPU via ModelManager |
| §4 AI Model Architecture (FinBERT, LSTM, XGBoost, GPT-2B) | PASS | All four models implemented in this phase (FinBERT exists from Phase 2) |
| §5 Model Responsibilities | PASS | LSTM→prediction, XGBoost→probability, GPT-2B→explanation per constitution |
| §6 Model Pipeline | PASS | Pipeline flow matches constitution: indicators→patterns→LSTM→XGBoost→GPT-2B→risk→signal |
| §7 Technical Analysis Engine | PASS | Indicators exist from Phase 1; pattern detection added in this phase |
| §8 Pattern Detection | PASS | 6 rule-based patterns as specified: breakout, triangle, double top/bottom, H&S, range |
| §9 Risk Management | PASS | Existing risk_agent.py enforced on every signal — no changes needed |
| §10 Safety Controls | PASS | Kill switch, position limits, blackout — all existing |
| §11 Signal Delivery | PASS | Telegram delivery exists; explanation field added to signal messages |
| §15 Execution Loop | PASS | Per-timeframe scheduling exists; pipeline extended with new agents |
| §16 Quality Gates | PASS | Unit tests for each new agent; integration test for pipeline |
| §18.3 All decisions explainable | PASS | GPT-2B explanation + template fallback ensures every signal has reasoning |
| §18.7 Traceability raw→signal | PASS | FR-012 requires logging all predictions and scores |

**Gate result**: PASS — no violations.

## Project Structure

### Documentation (this feature)

```text
specs/003-ai-decision-engine/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   └── pipeline-contract.md
└── tasks.md             # Phase 2 output (via /speckit.tasks)
```

### Source Code (repository root)

```text
analysis/
├── __init__.py              # existing
├── indicators.py            # existing — no changes
└── pattern_detection.py     # NEW — 6 rule-based pattern detectors

models/
├── __init__.py              # existing
├── model_manager.py         # existing — extend with LSTM/XGBoost/GPT-2 loading
├── finbert.py               # existing — no changes
├── lstm_model.py            # NEW — LSTM architecture, training, inference
├── xgboost_model.py         # NEW — XGBoost feature engineering, training, inference
└── explanation_model.py      # NEW — GPT-OSS-20B explanation via Ollama

agents/
├── __init__.py              # existing
├── chart_agent.py           # NEW — multi-timeframe orchestration + clarity scoring
├── prediction_agent.py      # NEW — wraps LSTM model
├── signal_agent.py          # NEW — feature vector assembly, XGBoost scoring, Ollama explanation
├── sentiment_agent.py       # existing — no changes
├── news_agent.py            # existing — no changes
└── risk_agent.py            # existing — no changes

core/
├── types.py                 # existing — extend with new dataclasses
├── config.py                # existing — extend with new config fields
├── scheduler.py             # existing — extend pipeline with new agents
└── logger.py                # existing — no changes

tests/
├── conftest.py              # existing — extend with new fixtures
├── test_patterns.py         # NEW
├── test_lstm.py             # NEW
├── test_xgboost.py          # NEW
├── test_explanation_model.py # NEW
├── test_chart_agent.py      # NEW
├── test_prediction_agent.py # NEW
├── test_signal_agent.py     # NEW
└── test_signal_scoring.py   # NEW — integration: full pipeline scoring
```

**Structure Decision**: Follows existing project layout. New files slot into existing packages (`models/`, `agents/`, `analysis/`, `tests/`). No new top-level packages needed.

## Implementation Strategy

### Dependency Order

```text
1. core/types.py          — new dataclasses (no deps)
2. analysis/pattern_detection.py — depends on types.py only
3. agents/chart_agent.py  — depends on indicators.py + pattern_detection.py + types.py
4. models/lstm_model.py   — depends on torch + types.py
5. agents/prediction_agent.py — depends on lstm_model.py + types.py
6. models/xgboost_model.py — depends on xgboost + sklearn + types.py
7. models/explanation_model.py — depends on requests + types.py (Ollama HTTP API)
8. agents/signal_agent.py — depends on xgboost_model.py + explanation_model.py + all agents
9. core/config.py         — extend with new fields
10. models/model_manager.py — extend with new model types
11. core/scheduler.py      — extend pipeline to wire all agents
```

### Fallback Strategy

The system must operate at three capability levels:

| Level | Models Available | Scoring | Explanation |
|-------|-----------------|---------|-------------|
| Full | All trained + Ollama running | XGBoost probability | GPT-OSS-20B via Ollama |
| Partial | Some trained, Ollama may be down | Weighted formula for missing; XGBoost if available | Template if Ollama unavailable |
| Minimal | None trained | Weighted formula only | Template only |

**Weighted formula fallback**: `probability = w1*indicator_score + w2*pattern_confidence + w3*sentiment_score + w4*prediction_confidence` with configurable weights (defaults: 0.30, 0.20, 0.25, 0.25).

### Multi-Timeframe Signal Selection

- Each timeframe runs independently on its own schedule
- Chart agent computes clarity score per timeframe: `clarity = (indicator_agreement * 0.5) + (pattern_confidence * 0.3) + (data_completeness * 0.2)`
- Signal agent maintains a sliding window of recent timeframe results
- Best-signal-wins: only the highest-probability signal per decision window is emitted
- Conflicting signals (BUY vs SELL from different timeframes) → higher probability wins; loser is suppressed and logged

### Partial Feature Vector Handling

When a feature source is unavailable, substitute neutral defaults:
- Missing sentiment: `macro_score=0.0`
- Missing prediction: `direction=NEUTRAL, confidence=0.0, volatility=0.0, trend_strength=0.0`
- Missing patterns: `all_confidences=0.0`
- Missing indicators: Skip cycle (indicators are the minimum required input)

## Complexity Tracking

No constitution violations — this section is not applicable.

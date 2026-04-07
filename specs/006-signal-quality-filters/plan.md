# Implementation Plan: Signal Quality Filtering Improvements

**Branch**: `006-signal-quality-filters` | **Date**: 2026-04-07 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/006-signal-quality-filters/spec.md`

## Summary

Improve signal quality by reducing Telegram noise (~17 analysis messages/hour to signal-only), filtering contradictory patterns, enforcing LSTM prediction agreement, adding multi-timeframe trend confirmation, implementing an opportunity score gate (7-component weighted composite, threshold 0.55), improving signal message format, and logging S/R proximity warnings. All new gates are independently configurable.

## Technical Context

**Language/Version**: Python 3.12 (matching existing codebase)
**Primary Dependencies**: apscheduler, python-telegram-bot, torch, xgboost, numpy (all existing)
**Storage**: SQLite (existing `storage/database.py` -- no schema changes needed)
**Testing**: pytest (existing `tests/` suite)
**Target Platform**: Linux (local machine, CPU default, optional GPU)
**Project Type**: CLI trading signal system
**Performance Goals**: Signal pipeline completes within existing cycle intervals (5min minimum)
**Constraints**: All gates must be independently toggleable via env vars; no breaking changes to existing behavior when all gates disabled
**Scale/Scope**: Single asset (XAU/USD), 4 timeframes (5m, 15m, 1h, 4h), 5 new config parameters

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| S1: Signal quality > signal frequency | PASS | Core purpose of this feature -- every gate reduces frequency to improve quality |
| S2: Local-first architecture | PASS | No new external dependencies; all computation local |
| S3: Core system objectives | PASS | Items 2-7 enhanced (analyze, predict, generate, risk, deliver, track) |
| S4: AI model architecture | PASS | Uses existing FinBERT, LSTM, XGBoost, GPT-OSS-20B; no new models |
| S7: Technical analysis engine | PASS | Pattern detection improved (contradictory filtering) |
| S8: Pattern detection | PASS | Rule-based filtering of contradictory patterns |
| S9: Risk management mandatory | PASS | All existing risk rules preserved; new gates add filtering before risk agent |
| S10: Safety controls | PASS | Kill switch, position limits unchanged |
| S11: Signal delivery | PASS | Telegram format improved; commands unaffected |
| S14: Technology stack | PASS | Python, existing libraries only |
| S16: Quality gates / unit tests | PASS | Each new gate gets unit tests |
| S18: Signal quality > frequency | PASS | Directly aligned with feature purpose |

**Post-design re-check**: PASS. No constitution violations.

## Project Structure

### Documentation (this feature)

```text
specs/006-signal-quality-filters/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   ├── quality-gates.md       # Gate execution order and config
│   └── telegram-signal-format.md  # New message format contract
├── checklists/
│   └── requirements.md  # Spec validation checklist
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
core/
├── config.py            # +5 new config fields
├── types.py             # +OpportunityScore dataclass
├── scheduler.py         # Remove broadcast, add S/R warning, MTF check
└── logger.py            # (unchanged)

analysis/
└── pattern_detection.py # +_filter_contradictory_patterns()

agents/
├── chart_agent.py       # +get_trend_consensus() method
├── signal_agent.py      # +prediction agreement, +opportunity score gate
└── risk_agent.py        # (unchanged)

execution/
├── signal_generator.py  # Redesigned format_trade_signal()
└── telegram_bot.py      # (unchanged)

tests/
├── test_patterns.py     # +TestContradictoryPatternFiltering
├── test_signal_agent.py # +TestPredictionAgreement, +TestOpportunityScore
├── test_integration.py  # Updated broadcast assertion
└── conftest.py          # +new config fixture fields
```

**Structure Decision**: Single project (existing). No new packages or directories needed. All changes are modifications to existing files plus one new dataclass.

## Complexity Tracking

No constitution violations to justify. All changes fit within existing architecture.

## Phase Summary

| Phase | Description | Files Changed | Priority |
|-------|-------------|--------------|----------|
| 1 | Stop indicator broadcasts | scheduler.py, test_integration.py | P1 |
| 2 | Filter contradictory patterns | pattern_detection.py, test_patterns.py | P1 |
| 3 | Prediction agreement gate | config.py, signal_agent.py, .env.example, conftest.py, test_signal_agent.py | P1 |
| 4 | Entry vs S/R warning | scheduler.py | P3 |
| 5 | Multi-timeframe confirmation | config.py, chart_agent.py, scheduler.py, .env.example, conftest.py, tests | P2 |
| 6 | Opportunity score gate | config.py, types.py, signal_agent.py, .env.example, conftest.py, test_signal_agent.py | P2 |
| 7 | Improved Telegram format | signal_generator.py, scheduler.py | P3 |

## New Config Parameters

| Parameter | Type | Default | Phase |
|-----------|------|---------|-------|
| PREDICTION_AGREEMENT_ENABLED | bool | true | 3 |
| MTF_CONFIRMATION_ENABLED | bool | true | 5 |
| MTF_MIN_AGREEING_TIMEFRAMES | int | 2 | 5 |
| OPPORTUNITY_SCORE_ENABLED | bool | true | 6 |
| OPPORTUNITY_SCORE_THRESHOLD | float | 0.55 | 6 |

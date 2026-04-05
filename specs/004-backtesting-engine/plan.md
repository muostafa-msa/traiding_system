# Implementation Plan: Backtesting Engine

**Branch**: `004-backtesting-engine` | **Date**: 2026-04-05 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/004-backtesting-engine/spec.md`

## Summary

Build a backtesting engine that replays historical OHLCV data (loaded from CSV) bar-by-bar through the existing trading pipeline (ChartAgent, PredictionAgent, SignalAgent, RiskAgent) with simulated account state, producing performance metrics (win rate, profit factor, Sharpe ratio, drawdown) persisted to SQLite. Includes walk-forward optimization for XGBoost hyperparameters.

## Technical Context

**Language/Version**: Python 3.12 (matching existing codebase)
**Primary Dependencies**: pandas (CSV parsing), numpy (metrics), existing pipeline agents (ChartAgent, SignalAgent, PredictionAgent, RiskAgent), existing models (LSTM, XGBoost), vectorbt (optional strategy wrapper)
**Storage**: SQLite (existing `storage/database.py` — extend with backtest tables)
**Testing**: pytest (existing test suite in `tests/`)
**Target Platform**: Local machine (Linux/macOS/Windows), CPU default, optional GPU
**Project Type**: CLI extension to existing trading system
**Performance Goals**: 1 year of hourly data (~6,500 bars) processed within 5 minutes
**Constraints**: Offline-capable, no network required, reproducible results
**Scale/Scope**: Single asset (XAU/USD), up to 50,000 bars per CSV file

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| Signal quality over frequency | PASS | Backtesting validates signal quality on historical data |
| Risk management mandatory | PASS | FR-005 enforces identical risk rules during backtesting |
| All decisions explainable | PASS | Explanation generation skipped in backtest (perf), but signal reasoning is preserved |
| Modular and extensible | PASS | New `backtesting/` package follows existing agent architecture |
| Local execution supported | PASS | Offline, no external APIs needed |
| Spec-driven development | PASS | Full spec → plan → tasks workflow |
| Traceability from data to signal | PASS | Each simulated trade links to its signal decision, bar data, and metrics |
| Local-first architecture | PASS | CSV input, local models, SQLite persistence |
| Backtesting support (Section 13) | PASS | This feature directly implements constitution Section 13 |

**Gate result**: ALL PASS — proceed to Phase 0.

## Project Structure

### Documentation (this feature)

```text
specs/004-backtesting-engine/
├── plan.md              # This file
├── spec.md              # Feature specification
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (CLI interface)
│   └── cli.md           # CLI command contract
├── checklists/
│   └── requirements.md  # Spec quality checklist
└── tasks.md             # Phase 2 output (created by /speckit.tasks)
```

### Source Code (repository root)

```text
backtesting/
├── __init__.py          # Package init
├── __main__.py          # python -m backtesting entry point
├── engine.py            # Bar-by-bar replay engine with account simulation
├── metrics.py           # Performance metrics calculator
├── walk_forward.py      # Walk-forward optimization orchestrator
└── cli.py               # CLI entry point (argparse)

data/
└── csv_loader.py        # Multi-format CSV parser (MT4, TradingView, generic)

storage/
└── database.py          # EXTEND: add backtest_runs, backtest_trades tables

tests/
├── test_csv_loader.py   # CSV parsing tests (MT4, TV, generic, edge cases)
├── test_backtest_engine.py  # Engine replay + trade lifecycle tests
├── test_metrics.py      # Metrics calculation verification
└── test_walk_forward.py # Walk-forward window splitting tests
```

**Structure Decision**: The backtesting engine lives in a new `backtesting/` package at the repo root, consistent with the existing project structure (`agents/`, `models/`, `analysis/`). CSV loading goes in `data/csv_loader.py` per the implementation plan's original placement. The backtest engine reuses existing agents directly — no wrappers or adapters needed since ChartAgent, PredictionAgent, SignalAgent, and RiskAgent all accept data via their method parameters.

## Complexity Tracking

No constitution violations — no complexity justifications needed.

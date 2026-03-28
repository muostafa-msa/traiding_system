# Implementation Plan: Core System + Risk Management

**Branch**: `001-core-system-risk` | **Date**: 2026-03-26 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/001-core-system-risk/spec.md`

## Summary

Build the foundational trading system pipeline: market data collection for XAU/USD via a swappable provider abstraction, technical indicator computation (RSI, MACD, EMA, BB, ATR, support/resistance, trend), a risk management agent enforcing all constitutional risk rules (1% per trade, 3% daily, 2 max positions, kill switch at 5%, SL/TP via ATR), signal formatting, Telegram delivery with chat-ID-restricted commands, SQLite persistence, and per-timeframe scheduled execution. All agents communicate via frozen dataclass contracts with no circular dependencies.

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: pandas, numpy, ta, requests, python-dotenv, apscheduler, python-telegram-bot, feedparser
**Storage**: SQLite (stdlib sqlite3)
**Testing**: pytest, pytest-asyncio
**Target Platform**: Linux (local machine, single user)
**Project Type**: Long-running scheduled service (daemon)
**Performance Goals**: Full cycle < 60 seconds; Telegram delivery < 5 seconds
**Constraints**: Single asset (XAU/USD), single machine, no broker connection, ~288 cycles/day at 5-min intervals
**Scale/Scope**: 1 asset, 4 timeframes, ~100K DB rows/year

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Evidence |
|-----------|--------|----------|
| I. Signal Quality Over Frequency | PASS | Phase 1 sends indicator summaries only; full scoring with threshold (0.68) is Phase 3. No low-quality signals possible since Phase 1 doesn't generate trade signals autonomously. |
| II. Modular Multi-Agent Architecture | PASS | Separate modules: market_data.py (Market Data Agent), indicators.py (Chart Analysis Agent), risk_agent.py (Risk Management Agent), signal_generator.py (Signal Delivery Agent), database.py (Performance Tracking Agent). All communicate via core/types.py frozen dataclasses. No circular deps. Each independently testable. |
| III. Mandatory Risk Management | PASS | Risk agent built in Phase 1 (not deferred). Every signal passes through risk checks before delivery. All constitutional rules enforced: 1% trade, 3% daily, 2 positions, 1.8 RR, SL=1.5xATR, TP=3.0xATR. |
| IV. Safety Controls Always Active | PASS | Kill switch at 5% daily loss with UTC midnight reset. Position limits enforced. News blackout deferred to Phase 2 (news agent not yet built) — acceptable since Phase 1 doesn't have news input. |
| V. Traceability and Explainability | PASS | Every signal includes: asset, direction, entry, SL, TP, confidence, reasoning. All persisted in SQLite with full audit trail. |
| VI. Spec-Driven Development | PASS | This plan follows spec.md created via /speckit.specify and clarified via /speckit.clarify. |

**News blackout (Principle IV)**: Partially deferred — news agent is Phase 2. Phase 1 has no news input, so blackout suppression is not applicable yet. Will be enforced when news agent is added. This is acceptable per the constitution since the safety control cannot apply without the corresponding data source.

## Project Structure

### Documentation (this feature)

```text
specs/001-core-system-risk/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   └── agent-contracts.md
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (repository root)

```text
core/
├── __init__.py
├── types.py             # Frozen dataclass contracts (all inter-agent types)
├── config.py            # AppConfig from .env via python-dotenv
├── logger.py            # Rotating file + console logging
└── scheduler.py         # APScheduler per-timeframe jobs, pipeline orchestration

data/
├── __init__.py
└── market_data.py       # MarketDataProvider ABC + TwelveData/AlphaVantage/Polygon

analysis/
├── __init__.py
└── indicators.py        # RSI, MACD, EMA, BB, ATR, support/resistance, trend

agents/
├── __init__.py
└── risk_agent.py        # All risk rules, kill switch, position sizing

execution/
├── __init__.py
├── signal_generator.py  # Format TradeSignal + RiskVerdict into Telegram message
└── telegram_bot.py      # Bot commands + broadcast, chat ID restriction

storage/
├── __init__.py
└── database.py          # SQLite schema, CRUD for 5 tables, metric queries

tests/
├── __init__.py
├── conftest.py          # Shared fixtures
├── test_indicators.py   # Indicator computation validation
├── test_risk_agent.py   # All risk rules + boundary cases
└── test_database.py     # DB operations + metrics

main.py                  # Entry point: init, startup data fetch, scheduler, shutdown
requirements.txt         # Pinned dependencies
.env.example             # Config template
```

**Structure Decision**: Custom multi-package layout matching the agent architecture. Each package corresponds to a layer in the data pipeline: `data/` (collection) -> `analysis/` (computation) -> `agents/` (decision) -> `execution/` (delivery), with `core/` (shared infra) and `storage/` (persistence) as cross-cutting concerns.

## Complexity Tracking

No constitution violations requiring justification. All principles satisfied.

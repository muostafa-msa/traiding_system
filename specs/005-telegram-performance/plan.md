# Implementation Plan: Telegram Performance Dashboard

**Branch**: `005-telegram-performance` | **Date**: 2026-04-06 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/005-telegram-performance/spec.md`

## Summary

Enhance the existing `/performance` Telegram command with comprehensive trading metrics (win rate, profit factor, Sharpe ratio, max drawdown, total return) and multi-period rollups (daily, weekly, monthly, all-time). All metrics are computed on-demand from existing `trades` and `signals` tables — no schema changes required.

## Technical Context

**Language/Version**: Python 3.12 (matching existing codebase)  
**Primary Dependencies**: python-telegram-bot (existing), sqlite3 (stdlib), math (stdlib)  
**Storage**: SQLite (existing `storage/database.py` — read-only queries, no schema changes)  
**Testing**: pytest, pytest-asyncio (existing test infrastructure)  
**Target Platform**: Linux local machine  
**Project Type**: CLI / Telegram bot  
**Performance Goals**: `/performance` response within 3 seconds  
**Constraints**: Message width ≤40 characters for mobile Telegram readability  
**Scale/Scope**: Single user, <100 trades/day, <10,000 total trades

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| §1 Purpose: trading signals + monitoring | PASS | Performance tracking is §12 requirement |
| §2 Local-First Architecture | PASS | No new external dependencies; all computation local |
| §3 Core Objective #8: Track signal performance | PASS | This feature directly implements Objective #8 |
| §9 Risk Management mandatory | PASS | No impact on risk rules |
| §10 Safety Controls | PASS | No impact on kill switch or safety mechanisms |
| §11 Signal Delivery: `/performance` command | PASS | Enhancing the constitutionally required command |
| §12 Performance Tracking: metrics | PASS | Implements required metrics (win rate, profit factor, max drawdown) |
| §14 Technology Stack: Python + listed libs | PASS | No new libraries |
| §16 Development Workflow: spec-driven | PASS | Following spec → plan → tasks workflow |
| §16 Quality Gates: unit + integration tests | PASS | Tests planned for all new methods |
| §18 Guiding Principle #4: modular | PASS | Query logic in database.py, formatting in signal_generator.py, command handling in telegram_bot.py |

**Gate result**: PASS — no violations.

## Project Structure

### Documentation (this feature)

```text
specs/005-telegram-performance/
├── plan.md              # This file
├── research.md          # Phase 0: research decisions
├── data-model.md        # Phase 1: entity & query design
├── quickstart.md        # Phase 1: developer onboarding
├── contracts/
│   └── telegram-commands.md  # Phase 1: /performance command contract
├── checklists/
│   └── requirements.md  # Spec quality checklist
└── tasks.md             # Phase 2 output (created by /speckit.tasks)
```

### Source Code (repository root)

```text
storage/
└── database.py          # ADD: period-filtered rollup query methods

execution/
├── telegram_bot.py      # MODIFY: enhance _cmd_performance with period args
└── signal_generator.py  # ADD: format_performance_summary function

tests/
├── test_database.py     # ADD: tests for rollup query methods
└── test_telegram.py     # ADD: tests for enhanced /performance command
```

**Structure Decision**: No new files or directories. All changes fit within existing modules following the established separation: database queries in `storage/`, message formatting in `execution/signal_generator.py`, command handling in `execution/telegram_bot.py`.

## Complexity Tracking

No constitution violations to justify. Feature is a straightforward enhancement to existing infrastructure.

## Implementation Approach

### Layer 1: Database Query Methods (storage/database.py)

Add methods to `Database` class:

1. **`get_performance_summary(period: str) -> dict`** — Main rollup method. Accepts period string ("daily"/"weekly"/"monthly"/"all"), computes date cutoff, queries trades and signals, returns PerformanceSummary dict.

2. **`_compute_sharpe_ratio(returns: list[float]) -> float`** — Helper. Takes list of per-trade pnl_percent values, computes annualized Sharpe. Returns 0 if < 2 values.

3. **`_compute_max_drawdown(pnls: list[float], initial_capital: float) -> float`** — Helper. Takes ordered list of trade P&Ls, builds cumulative equity curve, returns max peak-to-trough drawdown as percentage.

### Layer 2: Message Formatting (execution/signal_generator.py)

Add function:

4. **`format_performance_summary(summary: dict) -> str`** — Formats PerformanceSummary dict into a plain-text Telegram message per the contract format. Handles zero-activity state.

### Layer 3: Command Handler (execution/telegram_bot.py)

Modify existing:

5. **`_cmd_performance`** — Parse period argument from command args (default "daily"), validate against allowed values, call `get_performance_summary`, format with `format_performance_summary`, reply. Show help message on invalid period.

### Layer 4: Tests

6. **Database tests** — Test rollup queries with various trade scenarios (empty, single trade, mixed wins/losses, multi-day). Verify Sharpe, drawdown, profit factor edge cases.

7. **Telegram command tests** — Test `/performance` with no args, each valid period, invalid period, zero-activity state, authorized/unauthorized access.

## Post-Design Constitution Re-Check

| Principle | Status |
|-----------|--------|
| §2 Local-First | PASS — no external APIs added |
| §11 `/performance` command | PASS — enhanced per constitution |
| §12 Performance metrics | PASS — all required metrics included |
| §16 Quality Gates | PASS — tests cover all new code |
| §18 Modular & extensible | PASS — clean layer separation |

**Final gate result**: PASS

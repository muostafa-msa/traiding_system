# Tasks: Telegram Performance Dashboard

**Input**: Design documents from `/specs/005-telegram-performance/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/

**Tests**: Included — constitution §16 requires unit tests for all new methods.

**Organization**: Tasks grouped by user story for independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup

**Purpose**: No setup required — no new dependencies, no schema changes, no new files to create. All work modifies existing modules.

**Checkpoint**: Ready to begin user story implementation immediately.

---

## Phase 2: Foundational

**Purpose**: No blocking prerequisites — User Story 1 builds the foundational query and formatting infrastructure that US2 and US3 extend.

**Checkpoint**: Proceed directly to User Story 1.

---

## Phase 3: User Story 1 - View Daily Performance Summary (Priority: P1) 🎯 MVP

**Goal**: Trader sends `/performance` in Telegram and receives a comprehensive daily performance report with signal count, trade metrics, win rate, profit factor, net P&L, and Sharpe ratio.

**Independent Test**: Send `/performance` with no arguments → verify formatted daily summary returned with accurate metrics computed from trade data.

### Implementation for User Story 1

- [X] T001 [US1] Add `_compute_sharpe_ratio(returns: list[float]) -> float` private method to Database class in storage/database.py — takes list of per-trade pnl_percent/100 values, returns `mean/std * sqrt(252)`, returns 0.0 if fewer than 2 values (per research.md R1)
- [X] T002 [US1] Add `get_performance_summary(period: str = "daily") -> dict` method to Database class in storage/database.py — for daily period: query signals count (created_at >= today UTC), closed trades count/wins(pnl>0)/losses(pnl<=0), gross_profit, gross_loss, open trades count, compute win_rate, profit_factor (float('inf') when gross_loss==0 per R4), net_pnl, sharpe_ratio via _compute_sharpe_ratio; return dict matching PerformanceSummary schema from data-model.md
- [X] T003 [P] [US1] Add `format_performance_summary(summary: dict) -> str` function in execution/signal_generator.py — format dict to plain-text Telegram message per contracts/telegram-commands.md response format; use period label "Today" for daily; handle zero-activity state (show "No trading activity." when total_trades==0 and total_signals==0); render profit_factor float('inf') as "∞" string; keep lines ≤40 chars
- [X] T004 [US1] Rewrite `_cmd_performance` method in execution/telegram_bot.py — replace current implementation (which reads from pre-aggregated performance table) with: call `self._db.get_performance_summary("daily")`, format with `format_performance_summary()` from signal_generator, reply with formatted message; import format_performance_summary at top of method
- [X] T005 [P] [US1] Add tests for `_compute_sharpe_ratio` and daily `get_performance_summary` in tests/test_database.py — test cases: empty trades (all zeros), single trade (sharpe=0), mixed wins/losses (verify win_rate, profit_factor, sharpe, net_pnl), all wins (profit_factor="∞"), break-even trade counted as loss (per R6)
- [X] T006 [P] [US1] Update TestPerformanceCommand in tests/test_telegram.py — replace existing `test_performance_returns_daily_stats` and `test_performance_with_data` with tests that: verify formatted message from get_performance_summary (not pre-aggregated table), test zero-activity state, test with inserted trades (save_signal + open_trade + close_trade), verify message contains "PERFORMANCE (Today)" header

**Checkpoint**: `/performance` returns comprehensive daily metrics computed from raw trades. All existing tests pass. MVP complete.

---

## Phase 4: User Story 2 - View Multi-Period Performance Rollups (Priority: P2)

**Goal**: Trader can send `/performance weekly`, `/performance monthly`, or `/performance all` to view aggregated metrics for different time periods.

**Independent Test**: Send `/performance weekly` with trade data spanning 10+ days → verify summary covers last 7 days only. Send `/performance invalid` → verify help message returned.

### Implementation for User Story 2

- [X] T007 [US2] Extend `get_performance_summary` in storage/database.py to support period parameter — add date cutoff logic: "daily" → today 00:00 UTC, "weekly" → now - 7 days, "monthly" → now - 30 days, "all" → no date filter; apply cutoff to both signals (created_at) and trades (closed_at) queries
- [X] T008 [US2] Update `format_performance_summary` in execution/signal_generator.py to map period to display label — "daily"→"Today", "weekly"→"Last 7 Days", "monthly"→"Last 30 Days", "all"→"All Time"; use label in message header `PERFORMANCE ({label})`
- [X] T009 [US2] Update `_cmd_performance` in execution/telegram_bot.py to parse period argument — extract period from `context.args[0]` if present (default "daily"); validate against allowed values ["daily", "weekly", "monthly", "all"]; on invalid argument, reply with help message per contract: "Usage: /performance [period]\nPeriods: daily, weekly, monthly, all\nDefault: daily"
- [X] T010 [P] [US2] Add tests for multi-period queries in tests/test_database.py — insert trades with varying closed_at timestamps (today, 3 days ago, 15 days ago, 45 days ago); verify daily returns only today's trades, weekly returns last 7 days, monthly returns last 30 days, all returns everything
- [X] T011 [P] [US2] Add tests for period argument handling in tests/test_telegram.py — test `/performance weekly` returns "Last 7 Days" header, test `/performance all` returns "All Time" header, test `/performance invalid` returns help message with valid options, test `/performance daily` same as no argument

**Checkpoint**: All period variants work. Invalid arguments show help. Existing daily tests still pass.

---

## Phase 5: User Story 3 - View Formatted Equity and Drawdown Metrics (Priority: P3)

**Goal**: Performance reports include maximum drawdown percentage and total return percentage, giving the trader risk exposure and capital trajectory visibility.

**Independent Test**: With trade data showing varying P&L, verify performance message includes max drawdown % and total return % with correct values.

### Implementation for User Story 3

- [X] T012 [US3] Add `_compute_max_drawdown(pnls: list[float], initial_capital: float) -> float` private method to Database class in storage/database.py — build cumulative equity curve from ordered P&L list, track running peak, compute peak-to-trough drawdown as percentage, return max drawdown (0.0 if no trades or no drawdown; per research.md R2 algorithm)
- [X] T013 [US3] Extend `get_performance_summary` in storage/database.py to include max_drawdown and total_return fields — call _compute_max_drawdown with ordered pnl list and initial_capital from account_state; compute total_return as (net_pnl / initial_capital * 100); add both to returned dict
- [X] T014 [US3] Update `format_performance_summary` in execution/signal_generator.py to display max_drawdown and total_return — add "Max Drawdown: {x}%" (1 decimal) and "Total Return: {±x}%" (1 decimal with sign) lines to message per contract format
- [X] T015 [P] [US3] Add tests for drawdown and return computations in tests/test_database.py — test cases: no trades (drawdown=0, return=0), steady wins (drawdown=0, positive return), win-then-loss sequence (verify drawdown matches peak-to-trough), all losses (drawdown equals total loss %), verify total_return = net_pnl/initial_capital*100
- [X] T016 [P] [US3] Add tests for drawdown/return display in tests/test_telegram.py — verify performance message contains "Max Drawdown:" and "Total Return:" lines, verify sign formatting ("+1.5%" for positive, "-2.0%" for negative)

**Checkpoint**: All performance reports now include drawdown and return. All three user stories independently functional.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final validation across all stories

- [X] T017 Run full test suite `pytest tests/ -v` and fix any regressions in existing tests
- [X] T018 Validate all performance message formats against contracts/telegram-commands.md — verify line widths ≤40 characters, verify zero-activity format matches contract, verify help message format matches contract

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Skipped — nothing to do
- **Foundational (Phase 2)**: Skipped — US1 is the foundation
- **User Story 1 (Phase 3)**: Can start immediately — no prerequisites
- **User Story 2 (Phase 4)**: Depends on US1 completion (extends get_performance_summary and _cmd_performance)
- **User Story 3 (Phase 5)**: Depends on US1 completion (extends get_performance_summary and format_performance_summary); independent of US2
- **Polish (Phase 6)**: Depends on all user stories being complete

### User Story Dependencies

```
US1 (P1) ─┬─→ US2 (P2)
           └─→ US3 (P3)

US2 and US3 are independent of each other and can run in parallel after US1.
```

### Within Each User Story

- Database methods before formatter (formatter depends on dict shape)
- Formatter before command handler (handler calls formatter)
- Tests are [P] and can run in parallel with each other within a story

### Parallel Opportunities

- T003 (formatter) can run in parallel with T001+T002 (database) since they touch different files — formatter only needs the dict schema from data-model.md
- T005 and T006 can run in parallel (different test files)
- After US1 is complete, US2 and US3 can run in parallel (US2 touches command parsing, US3 touches drawdown computation — minimal overlap in storage/database.py)
- T010 and T011 can run in parallel (different test files)
- T015 and T016 can run in parallel (different test files)

---

## Parallel Example: User Story 1

```bash
# Launch database + formatter in parallel (different files):
Task T001: "_compute_sharpe_ratio in storage/database.py"
Task T003: "format_performance_summary in execution/signal_generator.py"

# After T001, T002 can proceed (same file, depends on T001):
Task T002: "get_performance_summary in storage/database.py"

# After T002 + T003, command handler can proceed:
Task T004: "_cmd_performance in execution/telegram_bot.py"

# Tests can run in parallel (different files):
Task T005: "Database performance tests in tests/test_database.py"
Task T006: "Telegram command tests in tests/test_telegram.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Implement T001–T006 (Phase 3)
2. **STOP and VALIDATE**: `pytest tests/test_database.py tests/test_telegram.py -v`
3. Send `/performance` → verify daily summary with real metrics
4. MVP complete — trader has comprehensive daily performance visibility

### Incremental Delivery

1. Complete US1 → Daily performance works → Test independently (MVP!)
2. Add US2 → Period arguments work → Test `/performance weekly` independently
3. Add US3 → Drawdown + return visible → Test independently
4. Polish → Full regression pass
5. Each story adds value without breaking previous stories

### Parallel Team Strategy

With two developers after US1 is complete:
- Developer A: US2 (command argument parsing + period labels)
- Developer B: US3 (drawdown + return computations)
- Both merge independently into the US1 foundation

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Existing `_cmd_performance` and its tests must be replaced, not appended to (current implementation reads from pre-aggregated `performance` table; new implementation computes from raw `trades`)
- All metrics formulas documented in research.md (R1–R6)
- Message format contract in contracts/telegram-commands.md
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently

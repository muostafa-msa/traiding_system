# Tasks: Backtesting Engine

**Input**: Design documents from `/specs/004-backtesting-engine/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/cli.md

**Tests**: Not explicitly requested in spec. Test tasks omitted.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create the backtesting package skeleton and initialize modules

- [x] T001 Create backtesting package with `backtesting/__init__.py`, `backtesting/__main__.py` (with `from backtesting.cli import main; main()`), `backtesting/engine.py`, `backtesting/metrics.py`, `backtesting/walk_forward.py`, `backtesting/cli.py` as empty modules
- [x] T002 Create `data/csv_loader.py` as empty module for CSV parsing

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can begin

**CRITICAL**: No user story work can begin until this phase is complete

- [x] T003 Extend `storage/database.py` — add `backtest_runs` and `backtest_trades` tables per data-model.md. Add methods: `save_backtest_run(run) -> int`, `save_backtest_trade(trade) -> int`, `get_backtest_run(run_id) -> dict`, `list_backtest_runs() -> list[dict]`, `get_backtest_trades(run_id) -> list[dict]`. Create tables in the existing `_create_tables()` method. Add indexes on `backtest_trades(run_id)`, `backtest_runs(created_at)`, and `backtest_runs(asset, timeframe)` per data-model.md
- [x] T004 [P] Add `account_override` parameter to `RiskAgent.evaluate()` in `agents/risk_agent.py` — when provided (a dict with keys: capital, open_positions, daily_pnl, kill_switch_active), use these values instead of querying the database via `get_account_state()`. This must be fully backward-compatible: when `account_override=None` (default), existing behavior is unchanged
- [x] T005 [P] Create `SimulatedAccount` dataclass in `backtesting/engine.py` with fields: capital (float), open_positions (int), daily_pnl (float), kill_switch_active (bool), open_trades (list). Add methods: `to_risk_override() -> dict` (returns dict for RiskAgent account_override), `update_daily_reset(current_date)` (resets daily_pnl when date changes), `open_trade(trade)`, `close_trade(trade, exit_price, pnl)`

**Checkpoint**: Foundation ready — user story implementation can now begin

---

## Phase 3: User Story 1 — Run a Backtest on Historical Data (Priority: P1) MVP

**Goal**: Load a CSV file, replay bars through the full pipeline, simulate trades with SL/TP exits, and output basic performance metrics to the terminal.

**Independent Test**: Run `python -m backtesting.cli data/test.csv` with a sample CSV and verify that a performance summary is printed with correct metrics.

### Implementation for User Story 1

- [x] T006 [US1] Implement generic CSV parser in `data/csv_loader.py` — function `load_csv(path: str, format: str = "auto") -> list[OHLCBar]`. For US1, support only the generic format (columns: datetime, open, high, low, close, volume). Validate each row (skip invalid, log warnings). Deduplicate by timestamp (keep latest). Sort by timestamp ascending. Raise `ValueError` if fewer than 200 valid bars
- [x] T007 [US1] Implement the core `BacktestEngine` class in `backtesting/engine.py`. Constructor takes: `config: AppConfig`, `database: Database`, `bars: list[OHLCBar]`, `timeframe: str`, `initial_capital: float`, `sentiment_score: float = 0.0`. Key method: `run() -> BacktestResult` that performs bar-by-bar replay. For each bar (starting at index 200 to satisfy indicator lookback): (1) slice the last 200+ bars as lookback window, (2) call `ChartAgent.analyze(window, timeframe)`, (3) create neutral `MacroSentiment` with configured sentiment_score, (4) call `PredictionAgent.predict(window, indicators)`, (5) call `SignalAgent.decide(analysis, sentiment, prediction)`, (6) if signal generated: calculate SL/TP using ATR multipliers from config, create `TradeSignal`, call `RiskAgent.evaluate(signal, account_override=sim_account.to_risk_override())`, (7) if approved: open trade in SimulatedAccount. Before processing signals each bar: check all open trades for SL/TP hits — pessimistic resolution (check SL first, if both SL and TP hit, use SL). Handle daily P&L reset when date changes. Close remaining trades at end-of-data at last bar's close price
- [x] T008 [US1] Create `BacktestResult` dataclass in `backtesting/engine.py` — fields: trades (list of dicts), initial_capital (float), final_capital (float), total_bars (int), start_date (datetime), end_date (datetime), rejected_signals (int), scoring_method (str). This is the return value of `BacktestEngine.run()`
- [x] T009 [US1] Implement metrics calculation in `backtesting/metrics.py` — function `compute_metrics(result: BacktestResult) -> dict` returning: total_trades, wins, losses, win_rate, profit_factor (gross_profit / gross_loss, handle zero-loss case), sharpe_ratio (annualized, daily returns, risk-free=0, sqrt(252)), max_drawdown (peak-to-trough on equity curve), avg_reward_risk, total_return ((final-initial)/initial). Handle zero-trade edge case: return all metrics as 0.0 with a flag `no_trades=True`
- [x] T010 [US1] Implement CLI entry point in `backtesting/cli.py` — use argparse per contracts/cli.md. Arguments: csv_file (positional), --capital, --timeframe, --sentiment-score, --verbose, --walk-forward, --train-months, --test-months. For US1: load CSV via `load_csv()`, create `BacktestEngine`, call `run()`, compute metrics via `compute_metrics()`, print basic results to stdout. DB persistence and formatted output are handled in US4 (T015-T016)
- [x] T011 [US1] Handle gap detection in `backtesting/engine.py` — before processing each bar, check if the time gap from the previous bar exceeds 2x the expected timeframe interval (e.g., >2h gap for 1h bars). If gap detected: reset indicator warmup state by ensuring the lookback window only uses contiguous bars. Do NOT generate signals on the first bar after a gap. Log a debug message noting the gap

**Checkpoint**: At this point, User Story 1 should be fully functional — `python -m backtesting.cli sample.csv` produces a performance report

---

## Phase 4: User Story 2 — Multi-Format CSV Loading (Priority: P2)

**Goal**: Auto-detect and parse CSV files exported from MetaTrader 4, TradingView, and generic OHLCV formats.

**Independent Test**: Load sample CSV files in each of the 3 formats and verify all produce identical `list[OHLCBar]` output for the same data.

### Implementation for User Story 2

- [x] T012 [P] [US2] Add MT4 format parser to `data/csv_loader.py` — detect MT4 by headers containing `<DATE>` or separate Date/Time columns. Parse MT4 date format (`YYYY.MM.DD`) and time (`HH:MM`). Handle both tab and comma delimiters. Map columns to OHLCBar fields
- [x] T013 [P] [US2] Add TradingView format parser to `data/csv_loader.py` — detect TradingView by lowercase `time` header with ISO 8601 timestamps. Parse timezone-aware timestamps (convert to UTC). Handle the TradingView-specific `Volume` capitalization
- [x] T014 [US2] Implement format auto-detection in `data/csv_loader.py` — function `detect_format(header_row: list[str]) -> str` returning "mt4", "tradingview", or "generic". Detection order: (1) check for angle-bracket headers (`<DATE>`) -> MT4, (2) check for lowercase `time` as first column → TradingView, (3) check for `datetime`/`date` column → generic, (4) if none match: raise `ValueError` with descriptive error message listing supported formats. Update `load_csv()` to call `detect_format()` when format="auto"

**Checkpoint**: CSV loading now supports 3 formats with auto-detection. US1 still works unchanged.

---

## Phase 5: User Story 4 — Performance Metrics Display (Priority: P2)

**Goal**: Present backtest results in a detailed, well-formatted terminal report and persist all results to the database for historical comparison.

**Independent Test**: Run a backtest and verify metrics displayed in terminal match values stored in the database.

### Implementation for User Story 4

- [x] T015 [US4] Create formatted report output function in `backtesting/metrics.py` — function `format_report(result: BacktestResult, metrics: dict, run_id: int) -> str` that produces the terminal-formatted output per contracts/cli.md (box-drawn borders, aligned columns, color-coded return). Handle zero-trade case with "No trades generated" message and hint to lower signal threshold
- [x] T016 [US4] Ensure DB persistence in `backtesting/cli.py` — after computing metrics, call `Database.save_backtest_run()` with all fields from data-model.md (including parameters as JSON: sentiment_score, signal_threshold, timeframe). Save each trade via `Database.save_backtest_trade()` with all trade details (entry/exit bars, prices, SL/TP, P&L, exit_reason, probability). Print the run_id in the output so users can reference it

**Checkpoint**: Backtest results are now formatted, displayed, and persisted. Previous stories still work.

---

## Phase 6: User Story 3 — Walk-Forward Optimization (Priority: P3)

**Goal**: Split historical data into sequential train/test windows, retrain XGBoost on each training window, and report out-of-sample performance per window.

**Independent Test**: Run `python -m backtesting.cli data.csv --walk-forward` and verify that separate in-sample and out-of-sample metrics are produced for each window.

### Implementation for User Story 3

- [x] T017 [US3] Implement window splitting in `backtesting/walk_forward.py` — function `create_windows(bars: list[OHLCBar], train_months: int = 3, test_months: int = 1) -> list[dict]` returning list of `{"train_bars": list[OHLCBar], "test_bars": list[OHLCBar], "train_period": str, "test_period": str}`. Use rolling window approach: slide forward by `test_months` each step. Validate: minimum 2 windows required (raise `ValueError` if insufficient data). Each train window must have >= 200 bars
- [x] T018 [US3] Implement walk-forward orchestrator in `backtesting/walk_forward.py` — class `WalkForwardOptimizer` with constructor taking `config`, `database`, `bars`, `timeframe`, `initial_capital`, `sentiment_score`. Method `run(train_months, test_months) -> WalkForwardResult`. For each window: (1) collect training labels from train_bars (use the labeling logic from `LSTMWrapper.train()` — direction based on price change over 12 bars), (2) build `FeatureVector` for each training bar using `ChartAgent` + `SignalAgent.assemble_features()`, (3) retrain XGBoost via `XGBoostWrapper.train(features, labels)`, (4) run `BacktestEngine` on test_bars, (5) compute in-sample metrics on train_bars and out-of-sample metrics on test_bars. Aggregate all out-of-sample results
- [x] T019 [US3] Create `WalkForwardResult` dataclass in `backtesting/walk_forward.py` — fields: windows (list of per-window results with train_period, test_period, is_metrics, oos_metrics), aggregate_oos_return (float), aggregate_oos_win_rate (float), is_vs_oos_divergence (float, computed as abs(avg_is_return - avg_oos_return))
- [x] T020 [US3] Add walk-forward formatted output in `backtesting/metrics.py` — function `format_walk_forward_report(wf_result: WalkForwardResult, run_id: int) -> str` producing the table output per contracts/cli.md (window number, train period, test period, OOS return, OOS win rate, aggregate row, divergence assessment)
- [x] T021 [US3] Integrate walk-forward into CLI in `backtesting/cli.py` — when `--walk-forward` flag is set: call `WalkForwardOptimizer.run()` instead of `BacktestEngine.run()`. Pass `--train-months` and `--test-months`. Save results to database with walk_forward parameters in the `parameters` JSON field. Print walk-forward formatted report

**Checkpoint**: Walk-forward optimization now works. All previous stories still function independently.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Edge case handling, validation, and cleanup across all modules

- [x] T022 [P] Add model fallback handling in `backtesting/engine.py` — if XGBoost or LSTM model files are not found at configured paths, log a warning and continue with fallback scoring method. Do not crash. Set `scoring_method="fallback"` in the BacktestResult
- [x] T023 [P] Add verbose mode to `backtesting/engine.py` — when verbose=True (passed from CLI), print per-trade open/close details during replay per contracts/cli.md verbose output format
- [x] T024 [P] Verify `python -m backtesting` invocation works end-to-end (uses `__main__.py` created in T001). Fix any import issues
- [x] T025 Validate end-to-end flow per quickstart.md — run a basic backtest, walk-forward, and multi-format CSV load using the commands in quickstart.md. Verify all exit codes per contracts/cli.md

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion — BLOCKS all user stories
- **US1 (Phase 3)**: Depends on Foundational (Phase 2)
- **US2 (Phase 4)**: Depends on Phase 1 only (T006 creates csv_loader.py). Can start after Setup, but T014 auto-detect extends T006's `load_csv()`
- **US4 (Phase 5)**: Depends on US1 (uses BacktestResult from T008, metrics from T009)
- **US3 (Phase 6)**: Depends on US1 (uses BacktestEngine) and Foundational (uses XGBoostWrapper.train())
- **Polish (Phase 7)**: Depends on all user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Depends only on Foundational (Phase 2). No dependencies on other stories. This IS the MVP.
- **User Story 2 (P2)**: Extends `data/csv_loader.py` created in US1. Can be implemented independently once T006 exists.
- **User Story 4 (P2)**: Depends on US1 result types (BacktestResult, metrics dict). Enhances existing CLI output.
- **User Story 3 (P3)**: Depends on US1 (BacktestEngine) for running sub-backtests per window. Can be tested independently with its own data splits.

### Within Each User Story

- Models/dataclasses before services/logic
- Core logic before CLI integration
- Formatting/display last

### Parallel Opportunities

- **Phase 2**: T003 runs alone (DB schema), but T004 and T005 can run in parallel with each other (different files)
- **Phase 4**: T012 and T013 can run in parallel (independent format parsers), then T014 integrates them
- **Phase 7**: T022, T023, T024 can all run in parallel (different files/concerns)
- **Cross-story**: US2 (Phase 4) can start in parallel with US1 (Phase 3) after Setup, since they touch different parts of csv_loader.py initially

---

## Parallel Example: User Story 1

```bash
# T006 must complete first (creates csv_loader and data types)
# Then these can run in parallel:
Task T007: "Implement BacktestEngine in backtesting/engine.py"
Task T008: "Create BacktestResult dataclass in backtesting/engine.py"
# Note: T007 and T008 are in the same file, so they should be done together

# After T007+T008, these can run in parallel:
Task T009: "Implement metrics calculation in backtesting/metrics.py"
Task T011: "Handle gap detection in backtesting/engine.py"

# T010 (CLI) depends on T009 (metrics) — must wait
```

## Parallel Example: User Story 2

```bash
# These format parsers can run in parallel (independent functions):
Task T012: "Add MT4 format parser to data/csv_loader.py"
Task T013: "Add TradingView format parser to data/csv_loader.py"

# T014 (auto-detect) integrates both — must wait for T012 + T013
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001-T002)
2. Complete Phase 2: Foundational (T003-T005)
3. Complete Phase 3: User Story 1 (T006-T011)
4. **STOP and VALIDATE**: Run `python -m backtesting.cli sample.csv` — verify performance report
5. This is a fully functional backtesting engine with generic CSV support

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. Add User Story 1 → MVP backtest with generic CSV + basic metrics
3. Add User Story 2 → Multi-format CSV support (MT4, TradingView)
4. Add User Story 4 → Enhanced metrics display + DB persistence
5. Add User Story 3 → Walk-forward optimization
6. Polish → Edge cases, fallbacks, verbose mode

Each story adds value without breaking previous stories.

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story is independently completable and testable
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- The backtesting engine reuses existing agents (ChartAgent, SignalAgent, PredictionAgent, RiskAgent) directly — no wrappers needed
- RiskAgent.evaluate() gets a backward-compatible `account_override` parameter (T004) — this is the only change to existing code

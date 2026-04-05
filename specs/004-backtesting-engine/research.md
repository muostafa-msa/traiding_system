# Research: Backtesting Engine

**Feature**: 004-backtesting-engine | **Date**: 2026-04-05

## R1: CSV Format Auto-Detection Strategy

**Decision**: Header-based detection with fallback to column count heuristic.

**Rationale**: Each target format (MT4, TradingView, generic) has distinct header patterns:
- MT4: `<DATE>`, `<TIME>`, `<OPEN>` (angle-bracket headers) OR `Date`, `Time` as separate columns (6-7 columns)
- TradingView: `time`, `open`, `high`, `low`, `close` (lowercase headers, ISO timestamps)
- Generic: `datetime`/`date`, `open`, `high`, `low`, `close`, `volume` (standard column names)

Detection order: read first row, normalize to lowercase, match against known header sets. If no header match, try parsing first data row to detect column count and date format.

**Alternatives considered**:
- User-specified format flag: rejected — adds friction, auto-detect is reliable for 3 formats
- MIME type / file extension: rejected — all are `.csv`, no differentiation

## R2: Bar-by-Bar Replay vs. Vectorized Backtesting

**Decision**: Bar-by-bar replay for the core engine; vectorbt integration deferred.

**Rationale**: The spec requires replaying through the *full pipeline* (indicators, patterns, LSTM, XGBoost, risk management). The existing agents are designed for sequential processing — `compute_indicators()` requires 200 bars of lookback, `PredictionAgent.predict()` uses 60-bar LSTM sequences. A vectorized approach would require rewriting the entire pipeline. Bar-by-bar replay reuses agents as-is.

**Performance mitigation**: Pre-compute all indicators once over the full dataset using pandas, then slice per-bar windows during replay. This avoids recomputing indicators from scratch at each bar. Expected: 6,500 bars in ~2-3 minutes.

**Alternatives considered**:
- Full vectorbt wrapper: deferred to future iteration — requires indicator/agent rewrites
- Hybrid (vectorbt for exits, sequential for entries): adds complexity without clear benefit for v1

## R3: Account State Simulation Approach

**Decision**: In-memory `SimulatedAccount` dataclass tracking capital, positions, daily P&L.

**Rationale**: The existing `RiskAgent.evaluate()` reads account state from the database via `Database.get_account_state()`. For backtesting, we need to either: (a) write simulated state to DB at each bar, or (b) inject simulated state into RiskAgent. Option (b) is cleaner — the backtesting engine maintains an in-memory `SimulatedAccount` and passes it to RiskAgent methods, avoiding thousands of DB writes during replay.

This requires adding an optional `account_override` parameter to `RiskAgent.evaluate()` so it can use injected state instead of querying the database. The override is a minimal, backward-compatible change.

**Alternatives considered**:
- Write to DB at each bar: rejected — ~6,500 DB writes per backtest, slow, pollutes live data
- Separate in-memory DB: rejected — overengineered for a simulation

## R4: Sentiment Placeholder During Backtesting

**Decision**: Use a configurable neutral `MacroSentiment` with `macro_score=0.0`, `is_blackout=False`.

**Rationale**: Historical news data is unavailable for replay. A neutral sentiment score means the backtesting engine evaluates purely technical + prediction signals. This is documented as an explicit assumption (spec FR-013). The score is configurable so users can test sensitivity to sentiment (e.g., set macro_score=0.3 to simulate mildly bullish sentiment).

**Alternatives considered**:
- Skip sentiment entirely: rejected — `SignalAgent.decide()` requires a `MacroSentiment` parameter
- Historical news API: rejected — adds external dependency, violates offline constraint

## R5: Pessimistic Intra-Bar Exit Resolution

**Decision**: When a bar's high-low range encompasses both SL and TP, assume SL is hit.

**Rationale**: Clarified in spec session (2026-04-05). This is the most conservative approach in quantitative backtesting. It prevents overfitting to favorable assumptions and produces more realistic (lower) performance metrics. Most professional backtesting frameworks (e.g., Backtrader, Zipline) offer this as a configuration option.

**Implementation**: During bar replay, check exits in order: (1) check if SL is hit (low <= SL for BUY, high >= SL for SELL), (2) check if TP is hit. If both are hit, SL takes priority.

**Alternatives considered**:
- Proximity to open: rejected per clarification — less conservative
- Direction-based: rejected per clarification — inconsistent with pessimistic philosophy

## R6: Walk-Forward Window Strategy

**Decision**: Anchored walk-forward with configurable train/test ratio, default 3:1 (75% train / 25% test).

**Rationale**: Anchored walk-forward (expanding training window) vs. rolling (fixed training window) — use rolling window as default since it better captures regime changes in financial data. Default: 3-month train / 1-month test, sliding forward by 1 month.

Minimum data: 1 year → produces 9 windows (months 1-3 train → month 4 test, months 2-4 train → month 5 test, etc.).

XGBoost is retrained on each training window using `XGBoostWrapper.train()`. LSTM weights are frozen (spec assumption).

**Alternatives considered**:
- Expanding window: available as option but not default — slower, biased toward older data
- K-fold cross-validation: rejected — not valid for time series (leaks future data)

## R7: Sharpe Ratio Calculation

**Decision**: Annualized Sharpe ratio using daily returns, risk-free rate = 0.

**Rationale**: Standard in quantitative finance. Formula: `Sharpe = mean(daily_returns) / std(daily_returns) * sqrt(252)`. Using 252 trading days per year. Risk-free rate assumed zero for simplicity (can be parameterized later).

Daily returns computed from equity curve (end-of-day capital / start-of-day capital - 1).

## R8: Database Schema Extension

**Decision**: Two new tables: `backtest_runs` and `backtest_trades`. No modification to existing tables.

**Rationale**: Backtest data must be kept separate from live trading data. A `backtest_runs` table stores run metadata, and `backtest_trades` stores individual simulated trades linked to their run. This avoids polluting the `signals` and `trades` tables used for live operations.

Walk-forward results are stored as JSON in the `backtest_runs.parameters` column rather than a separate table, since they're read-only metadata tied to the run.

**Alternatives considered**:
- Reuse existing `trades` table with a `is_backtest` flag: rejected — mixes live and simulated data
- Separate SQLite database file: rejected — complicates queries that compare backtest vs. live performance

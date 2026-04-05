# Feature Specification: Backtesting Engine

**Feature Branch**: `004-backtesting-engine`  
**Created**: 2026-04-05  
**Status**: Draft  
**Input**: User description: "Backtesting engine for historical validation and strategy optimization using bar-by-bar replay through the full trading pipeline with CSV data loading, vectorbt-compatible strategy wrapper, walk-forward optimization, and comprehensive performance metrics output"

## Clarifications

### Session 2026-04-05

- Q: When both stop-loss and take-profit are hit within a single bar's range, which exit is used? → A: Pessimistic — assume the worst-case exit (stop-loss) to avoid inflating performance metrics.
- Q: Where should backtest results be persisted? → A: SQLite — stored in the existing database to enable run comparison and feed retraining workflows.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Run a Backtest on Historical Data (Priority: P1)

A trader wants to evaluate how the trading system's signals would have performed on past market data. They load a CSV file containing historical XAU/USD candlestick data (e.g., 1 year of 1-hour bars), run the backtesting engine, and receive a comprehensive performance report showing profitability, win rate, drawdown, and risk-adjusted returns.

**Why this priority**: Without the ability to replay historical data through the pipeline and see results, no other backtesting functionality has value. This is the core capability that validates signal quality.

**Independent Test**: Can be fully tested by loading a sample CSV file, running the backtest, and verifying that performance metrics (win rate, profit factor, max drawdown) are produced and mathematically correct.

**Acceptance Scenarios**:

1. **Given** a CSV file with at least 6 months of hourly OHLCV data, **When** the user runs the backtesting engine, **Then** the system replays each bar through the full signal pipeline and produces a performance summary including total trades, win rate, profit factor, maximum drawdown, and total return.
2. **Given** a CSV file with known signal opportunities (e.g., clear trends), **When** the backtest completes, **Then** every generated signal respects the system's risk management rules (1% max risk per trade, 3% daily limit, risk-reward >= 1.8).
3. **Given** a CSV file with insufficient data (fewer than 200 bars), **When** the user attempts to run the backtest, **Then** the system reports a clear error indicating minimum data requirements.

---

### User Story 2 - Load Data from Multiple CSV Formats (Priority: P2)

A trader has historical data exported from different platforms (MetaTrader 4, TradingView, or a generic OHLCV format). They want to load any of these into the backtesting engine without manual reformatting.

**Why this priority**: Data loading is a prerequisite for backtesting, but a single-format loader is sufficient for P1. Multi-format support removes friction and makes the system usable with real-world data exports.

**Independent Test**: Can be tested by providing sample CSV files in MT4, TradingView, and generic formats and verifying each is correctly parsed into the system's internal bar representation.

**Acceptance Scenarios**:

1. **Given** a CSV file in MetaTrader 4 export format (Date, Time, Open, High, Low, Close, Volume), **When** the user loads it, **Then** the system correctly parses all rows into candlestick bars with proper timestamps.
2. **Given** a CSV file in TradingView export format (time, open, high, low, close, Volume), **When** the user loads it, **Then** the system correctly parses all rows with timezone-aware timestamps.
3. **Given** a CSV file with missing values or corrupted rows, **When** the user loads it, **Then** the system skips invalid rows, logs warnings, and continues with valid data.

---

### User Story 3 - Walk-Forward Optimization (Priority: P3)

A trader wants to optimize their model's parameters using walk-forward analysis to avoid overfitting. The system splits historical data into sequential training and testing windows, optimizes on each training window, and validates on the subsequent test window, producing out-of-sample performance metrics.

**Why this priority**: Walk-forward optimization prevents overfitting and produces realistic performance estimates, but it requires P1 (basic backtesting) and P2 (data loading) to function. It is the key feature that makes backtest results trustworthy.

**Independent Test**: Can be tested by running walk-forward analysis on a dataset with known characteristics and verifying that the system produces separate in-sample and out-of-sample metrics for each window.

**Acceptance Scenarios**:

1. **Given** at least 1 year of historical data, **When** the user runs walk-forward optimization, **Then** the system divides the data into sequential windows (e.g., 3-month train / 1-month test) and reports performance for each out-of-sample window.
2. **Given** walk-forward optimization results, **When** the user reviews the output, **Then** they can compare in-sample vs. out-of-sample performance to assess overfitting risk.
3. **Given** a dataset too small to create at least 2 train/test windows, **When** the user runs walk-forward, **Then** the system reports an error with the minimum data requirement.

---

### User Story 4 - View Backtest Performance Metrics (Priority: P2)

A trader wants a detailed performance report after a backtest completes. The report should include standard quantitative trading metrics that allow them to evaluate strategy viability and compare across different configurations.

**Why this priority**: Metrics are essential for interpreting backtest results and making informed decisions about strategy changes.

**Independent Test**: Can be tested by running a backtest on a dataset with known trades and verifying each metric matches expected calculations.

**Acceptance Scenarios**:

1. **Given** a completed backtest with at least 10 trades, **When** the user views the results, **Then** they see: total trades, win rate, profit factor, Sharpe ratio, maximum drawdown, average reward-to-risk ratio, and total return.
2. **Given** a completed backtest, **When** the user views the results, **Then** the metrics are displayed in a clear, formatted output suitable for terminal display.

---

### Edge Cases

- What happens when the CSV file contains gaps (weekends, holidays) in the price data? The system should handle non-contiguous timestamps gracefully without generating false signals at gap boundaries.
- What happens when the historical data has extreme price moves (e.g., flash crashes)? The risk management rules must still be enforced, and the backtest should not crash on outlier bars.
- What happens when the model files (XGBoost, LSTM) are not available during backtesting? The system should fall back to the fallback scoring method and warn the user.
- What happens when a backtest produces zero trades? The system should report this clearly rather than producing divide-by-zero errors in metrics.
- What happens when the CSV contains duplicate timestamps? The system should deduplicate and keep the latest entry for each timestamp.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST parse CSV files in at least three formats: MetaTrader 4, TradingView, and a generic OHLCV format (columns: datetime, open, high, low, close, volume).
- **FR-002**: System MUST auto-detect the CSV format based on header row content and column structure.
- **FR-003**: System MUST validate parsed data and skip rows with missing or invalid values, logging warnings for each skipped row.
- **FR-004**: System MUST replay historical bars sequentially through the full trading pipeline (indicators, patterns, LSTM prediction, sentiment placeholder, XGBoost scoring, risk management).
- **FR-005**: System MUST enforce all risk management rules during backtesting identically to live operation (1% per trade, 3% daily limit, 2 max positions, stop-loss = entry - 1.5 x ATR, risk-reward >= 1.8).
- **FR-006**: System MUST track simulated account state (capital, open positions, daily P&L) throughout the backtest.
- **FR-007**: System MUST detect when simulated trades hit their stop-loss or take-profit levels during bar replay and close them accordingly. When a single bar's range encompasses both levels, the system MUST use pessimistic resolution (assume stop-loss is hit) to avoid inflating performance metrics.
- **FR-008**: System MUST produce a performance report with: total trades, win rate, profit factor, Sharpe ratio, maximum drawdown, average reward-to-risk, total return, and number of rejected signals. Results MUST be displayed in the terminal AND persisted to the database to enable historical run comparison and model retraining workflows.
- **FR-009**: System MUST support walk-forward optimization by splitting data into sequential train/test windows and reporting per-window out-of-sample metrics.
- **FR-010**: System MUST require a minimum of 200 bars to run a backtest and a minimum of 1 year of data for walk-forward optimization.
- **FR-011**: System MUST provide a command-line interface to run backtests, accepting the CSV file path and optional parameters (initial capital, timeframe).
- **FR-012**: System MUST handle non-contiguous timestamps (gaps from weekends/holidays) without generating false signals at gap boundaries.
- **FR-013**: System MUST use the sentiment placeholder (neutral sentiment with configurable score) during backtesting since live news data is not available for historical periods.

### Key Entities

- **Backtest Run**: Represents a single execution of the backtesting engine on a dataset, persisted in the database. Attributes: run ID, start date, end date, initial capital, final capital, total bars processed, parameters used.
- **Simulated Trade**: A trade opened and closed during backtesting, persisted in the database and linked to its parent Backtest Run. Attributes: entry bar, exit bar, direction, entry price, exit price, stop-loss, take-profit, P&L, exit reason (stop-loss hit, take-profit hit, end-of-data).
- **Performance Report**: Aggregated metrics computed from all simulated trades in a backtest run.
- **Walk-Forward Window**: A train/test data split used in walk-forward optimization. Attributes: training period, testing period, in-sample metrics, out-of-sample metrics.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can run a complete backtest on 1 year of hourly data (approximately 6,500 bars) and receive results within 5 minutes on a standard local machine.
- **SC-002**: Backtest results are reproducible - running the same data with the same parameters produces identical metrics every time.
- **SC-003**: All performance metrics (win rate, profit factor, Sharpe ratio, drawdown) are mathematically verified against manual calculations on a test dataset with known outcomes.
- **SC-004**: Walk-forward optimization produces out-of-sample metrics that allow users to assess overfitting, with a clear comparison between in-sample and out-of-sample performance.
- **SC-005**: The backtesting engine correctly enforces all risk management rules, producing zero trades that violate the system's risk constraints.
- **SC-006**: CSV loading supports at least 3 export formats and correctly handles files with up to 50,000 rows without errors.

## Assumptions

- Historical CSV data is provided by the user; the system does not download historical data automatically.
- Sentiment analysis during backtesting uses a neutral placeholder since historical news data is not available for replay. This is acceptable because the primary goal is to validate technical signal quality.
- The XGBoost and LSTM models use their current trained weights during backtesting; walk-forward optimization retrains XGBoost hyperparameters only (not LSTM).
- Initial capital defaults to $10,000 unless specified by the user.
- Backtesting focuses on a single asset (XAU/USD) consistent with the current system scope.
- Slippage and commission costs are not modeled in this initial version. Metrics reflect idealized execution.
- The backtesting engine runs offline and does not require network connectivity.

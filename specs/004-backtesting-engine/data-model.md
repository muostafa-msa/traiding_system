# Data Model: Backtesting Engine

**Feature**: 004-backtesting-engine | **Date**: 2026-04-05

## New Entities

### BacktestRun

Represents a single execution of the backtesting engine on a dataset.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | integer | primary key, auto-increment | Unique run identifier |
| csv_file | text | not null | Path to the CSV file used |
| asset | text | not null | Asset symbol (e.g., "XAU/USD") |
| timeframe | text | not null, one of: 5min, 15min, 1h, 4h | Bar timeframe |
| start_date | timestamp | not null | First bar timestamp in dataset |
| end_date | timestamp | not null | Last bar timestamp in dataset |
| initial_capital | real | not null, > 0 | Starting capital |
| final_capital | real | not null | Capital after all trades closed |
| total_bars | integer | not null, > 0 | Number of bars processed |
| total_trades | integer | not null, >= 0 | Number of trades executed |
| win_rate | real | [0.0, 1.0] | Wins / total trades |
| profit_factor | real | >= 0 | Gross profit / gross loss |
| sharpe_ratio | real | nullable | Annualized Sharpe ratio |
| max_drawdown | real | [0.0, 1.0] | Maximum peak-to-trough decline |
| avg_reward_risk | real | >= 0 | Average reward-to-risk ratio |
| total_return | real | any | (final - initial) / initial |
| rejected_signals | integer | >= 0 | Signals rejected by risk management |
| parameters | text | nullable | JSON-encoded run parameters |
| scoring_method | text | not null, one of: xgboost, fallback | Which scoring was used |
| created_at | timestamp | not null, default now | When the run was created |

**Relationships**: One-to-many with BacktestTrade.

### BacktestTrade

A trade opened and closed during backtesting.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | integer | primary key, auto-increment | Unique trade identifier |
| run_id | integer | foreign key → backtest_runs.id, not null | Parent backtest run |
| direction | text | not null, one of: BUY, SELL | Trade direction |
| entry_bar_index | integer | not null, >= 0 | Index of the bar where trade was opened |
| exit_bar_index | integer | not null, >= entry_bar_index | Index of the bar where trade was closed |
| entry_timestamp | timestamp | not null | Timestamp of entry bar |
| exit_timestamp | timestamp | not null | Timestamp of exit bar |
| entry_price | real | not null, > 0 | Price at entry |
| exit_price | real | not null, > 0 | Price at exit |
| stop_loss | real | not null, > 0 | Stop-loss level |
| take_profit | real | not null, > 0 | Take-profit level |
| position_size | real | not null, > 0 | Position size from risk calculation |
| pnl | real | not null | Profit/loss in currency |
| pnl_percent | real | not null | Return as percentage |
| exit_reason | text | not null, one of: stop_loss, take_profit, end_of_data | Why trade was closed |
| probability | real | not null, [0.0, 1.0] | Signal probability at entry |
| created_at | timestamp | not null, default now | Record creation time |

**Relationships**: Many-to-one with BacktestRun.

## Existing Entities (referenced, not modified)

### AccountState (simulation only — not persisted during backtest)

The backtesting engine maintains a `SimulatedAccount` in memory that mirrors the `AccountState` structure:

| Field | Type | Description |
|-------|------|-------------|
| capital | real | Current simulated capital |
| open_positions | integer | Count of currently open trades |
| daily_pnl | real | P&L accumulated today |
| kill_switch_active | boolean | Whether kill switch has triggered |

This is passed to `RiskAgent.evaluate()` via an `account_override` parameter instead of querying the database.

## State Transitions

### BacktestRun Lifecycle

```
CREATED → RUNNING → COMPLETED
                  → FAILED (if error during replay)
```

No explicit status column — a run with `final_capital IS NULL` is incomplete/failed.

### SimulatedTrade Lifecycle (in-memory during replay)

```
OPENED (entry bar) → MONITORING (each subsequent bar)
                        → CLOSED:stop_loss   (low/high hits SL)
                        → CLOSED:take_profit (high/low hits TP)
                        → CLOSED:end_of_data (last bar reached)
```

When both SL and TP are hit within a single bar: pessimistic resolution → CLOSED:stop_loss.

## Entity Relationships

```
BacktestRun (1) ──── (N) BacktestTrade
     │
     └── parameters (JSON): {
           "sentiment_score": 0.0,
           "signal_threshold": 0.68,
           "walk_forward": {
             "enabled": false,
             "train_months": 3,
             "test_months": 1,
             "windows": [...]
           }
         }
```

## Validation Rules

- `BacktestRun.total_bars >= 200` (minimum bar requirement)
- `BacktestRun.initial_capital > 0`
- `BacktestRun.end_date > BacktestRun.start_date`
- `BacktestTrade.exit_bar_index >= BacktestTrade.entry_bar_index`
- `BacktestTrade.pnl` must match: `(exit_price - entry_price) * position_size` for BUY, inverse for SELL
- `BacktestTrade.exit_reason` must be consistent with price action (SL exit means price reached SL level)

## Indexes

- `backtest_trades(run_id)` — fast lookup of all trades in a run
- `backtest_runs(created_at)` — chronological run listing
- `backtest_runs(asset, timeframe)` — filter runs by asset/timeframe

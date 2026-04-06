# Data Model: 005-telegram-performance

**Date**: 2026-04-06  
**Feature**: Telegram Performance Dashboard

## Existing Entities (read-only for this feature)

### signals

Source of truth for signal activity counts.

| Field | Type | Usage |
|-------|------|-------|
| id | INTEGER PK | Identify signal |
| asset | TEXT | Filter by asset |
| direction | TEXT | BUY/SELL/NO_TRADE |
| created_at | TIMESTAMP | Date-range filtering for period rollups |
| status | TEXT | pending/approved/rejected |

**Query pattern**: `COUNT(*) WHERE created_at >= ?` for signal counts per period.

### trades

Source of truth for all P&L metrics.

| Field | Type | Usage |
|-------|------|-------|
| id | INTEGER PK | Identify trade |
| signal_id | INTEGER FK | Link to signal |
| position_size | REAL | Not used in performance metrics |
| entry_price | REAL | Used for return calculations |
| exit_price | REAL | Used for return calculations |
| pnl | REAL | Win/loss classification, profit factor, equity curve |
| pnl_percent | REAL | Sharpe ratio computation |
| opened_at | TIMESTAMP | Not used for performance (use closed_at) |
| closed_at | TIMESTAMP | Date-range filtering; NULL = open trade |
| close_reason | TEXT | Not used in performance metrics |

**Query patterns**:
- Closed trades in period: `WHERE closed_at IS NOT NULL AND closed_at >= ?`
- Open trades count: `WHERE closed_at IS NULL`
- Win count: `WHERE pnl > 0 AND closed_at IS NOT NULL AND closed_at >= ?`
- Loss count: `WHERE pnl <= 0 AND closed_at IS NOT NULL AND closed_at >= ?`
- Gross profit: `SUM(pnl) WHERE pnl > 0 AND ...`
- Gross loss: `SUM(ABS(pnl)) WHERE pnl <= 0 AND ...`

### account_state

| Field | Type | Usage |
|-------|------|-------|
| capital | REAL | Initial capital for total return % computation |
| daily_pnl | REAL | Displayed in daily performance summary |

## Computed Entity (not persisted)

### PerformanceSummary

Computed on-demand from `trades` and `signals` tables. Returned as a dict/dataclass.

| Field | Type | Derivation |
|-------|------|-----------|
| period | str | "daily" / "weekly" / "monthly" / "all" |
| total_signals | int | COUNT from signals in period |
| total_trades | int | COUNT closed trades in period |
| open_trades | int | COUNT trades WHERE closed_at IS NULL |
| wins | int | COUNT closed trades WHERE pnl > 0 |
| losses | int | COUNT closed trades WHERE pnl <= 0 |
| win_rate | float | wins / total_trades (0 if no trades) |
| gross_profit | float | SUM(pnl) WHERE pnl > 0 |
| gross_loss | float | SUM(ABS(pnl)) WHERE pnl <= 0 |
| profit_factor | float | gross_profit / gross_loss (float('inf') if gross_loss == 0 and gross_profit > 0; formatter renders as "∞") |
| net_pnl | float | gross_profit - gross_loss |
| sharpe_ratio | float | mean(returns) / std(returns) * √252 (0 if < 2 trades) |
| max_drawdown | float | Peak-to-trough % on cumulative equity curve |
| total_return | float | net_pnl / initial_capital * 100 |

## Schema Changes

**None required.** All data needed for performance computation already exists in the `signals`, `trades`, and `account_state` tables. No new tables, columns, or indexes are needed.

## Relationships

```
account_state (initial_capital)
       │
       ├── signals (created_at filter → signal counts)
       │
       └── trades (closed_at filter → P&L metrics)
              │
              └── PerformanceSummary (computed on-demand)
```

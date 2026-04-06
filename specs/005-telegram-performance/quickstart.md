# Quickstart: 005-telegram-performance

**Date**: 2026-04-06  
**Feature**: Telegram Performance Dashboard

## What This Feature Does

Enhances the existing `/performance` Telegram command to show comprehensive trading metrics with support for multiple time periods (daily, weekly, monthly, all-time). Adds Sharpe ratio, max drawdown, and total return computations.

## Files to Modify

| File | Change |
|------|--------|
| `storage/database.py` | Add performance rollup query methods (period-filtered aggregates, Sharpe, drawdown) |
| `execution/telegram_bot.py` | Enhance `/performance` handler to accept period arguments and display rich metrics |
| `execution/signal_generator.py` | Add performance dashboard formatter function |
| `tests/test_telegram.py` | Extend performance command tests for multi-period and edge cases |
| `tests/test_database.py` | Add tests for new query methods |

## Files NOT Modified

- `core/types.py` — no new dataclasses needed (performance summary is a dict)
- `core/config.py` — no new config options
- Schema (`_SCHEMA_SQL`) — no new tables or columns

## Key Design Decisions

1. **On-demand computation**: metrics computed from raw `trades`/`signals` tables on each command invocation (no pre-aggregation)
2. **No schema changes**: all data already exists in `trades`, `signals`, and `account_state`
3. **Plain text formatting**: consistent with existing bot commands (no Markdown/HTML parse mode)
4. **Sharpe from trade returns**: uses `pnl_percent` per trade, annualized by √252
5. **Max drawdown from cumulative equity curve**: closed trades ordered by `closed_at`

## Dependencies

- No new Python packages required
- All existing dependencies sufficient (sqlite3, datetime, math for √252)

## How to Test

```bash
# Run all tests
pytest tests/test_telegram.py tests/test_database.py -v

# Run only performance-related tests
pytest tests/test_telegram.py::TestPerformanceCommand -v
```

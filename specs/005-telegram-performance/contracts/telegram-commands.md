# Telegram Command Contract: /performance

**Date**: 2026-04-06  
**Feature**: 005-telegram-performance

## Command Signature

```
/performance [period]
```

**period** (optional): `daily` | `weekly` | `monthly` | `all`  
**default**: `daily` (when omitted)

## Input Validation

| Input | Behavior |
|-------|----------|
| `/performance` | Show daily summary |
| `/performance daily` | Show daily summary |
| `/performance weekly` | Show last 7 days summary |
| `/performance monthly` | Show last 30 days summary |
| `/performance all` | Show all-time summary |
| `/performance <invalid>` | Reply with help message listing valid options |

## Response Format: Performance Summary

```
PERFORMANCE ({PERIOD_LABEL})
─────────────────────
Signals: {total_signals}
Trades: {total_trades} ({open_trades} open)
Wins: {wins} | Losses: {losses}
Win Rate: {win_rate}%
Profit Factor: {profit_factor}
Net P&L: {net_pnl}
Sharpe Ratio: {sharpe_ratio}
Max Drawdown: {max_drawdown}%
Total Return: {total_return}%
```

**Field formatting**:
- `PERIOD_LABEL`: "Today" / "Last 7 Days" / "Last 30 Days" / "All Time"
- `win_rate`: 1 decimal, e.g., "66.7%"
- `profit_factor`: 2 decimals, e.g., "2.10" or "∞"
- `net_pnl`: 2 decimals with sign, e.g., "+150.00" or "-42.50"
- `sharpe_ratio`: 2 decimals, e.g., "1.45"
- `max_drawdown`: 1 decimal, e.g., "3.2%"
- `total_return`: 1 decimal with sign, e.g., "+1.5%"

## Response Format: Help (invalid argument)

```
Usage: /performance [period]
Periods: daily, weekly, monthly, all
Default: daily
```

## Response Format: Zero Activity

```
PERFORMANCE ({PERIOD_LABEL})
─────────────────────
No trading activity.
Signals: 0 | Trades: 0
```

## Authorization

All responses gated by existing `_check_chat_id()` — unauthorized requests receive no reply.

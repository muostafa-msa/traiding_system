# Research: 005-telegram-performance

**Date**: 2026-04-06  
**Feature**: Telegram Performance Dashboard

## R1: Sharpe Ratio Computation for Trade-Level Returns

**Decision**: Compute Sharpe ratio from per-trade percentage returns (P&L / entry_price), annualized by √252.

**Rationale**: Trade-level returns (not daily time-series returns) are the natural unit for a signal-based system where trades may span multiple days or occur multiple times per day. Using `pnl_percent` from the `trades` table directly avoids reconstructing a daily equity curve. Annualization factor √252 is the industry standard for trading-day-based Sharpe.

**Alternatives considered**:
- Daily equity curve Sharpe: requires reconstructing daily P&L series, more complex with no benefit given trade frequency (<100/day).
- Risk-free rate adjustment: omitted — the system targets absolute returns, and including a risk-free rate adds complexity without actionable value for the user.

**Formula**: `sharpe = mean(returns) / std(returns) * sqrt(252)` where `returns = [trade.pnl_percent / 100 for each closed trade]`. Returns 0 when fewer than 2 trades exist (std is undefined).

## R2: Maximum Drawdown Computation

**Decision**: Compute max drawdown from the cumulative P&L series of closed trades, ordered by close timestamp.

**Rationale**: Peak-to-trough drawdown on the cumulative equity curve is the standard measure. Using closed trades (ordered by `closed_at`) produces a clean sequence without intra-trade noise.

**Algorithm**:
1. Build cumulative P&L series: `equity[i] = initial_capital + sum(pnl[0..i])`
2. Track running peak: `peak = max(peak, equity[i])`
3. Track drawdown: `dd = (peak - equity[i]) / peak`
4. Max drawdown = `max(dd)`

**Alternatives considered**:
- Intra-trade drawdown (using unrealized P&L): not available — system only records entry/exit.
- Pre-aggregated drawdown from `performance` table: the existing `max_drawdown` column in the `performance` table is per-day only and not computed yet.

## R3: Multi-Period Query Strategy

**Decision**: Compute all metrics on-demand from raw `trades` and `signals` tables using date-range filters.

**Rationale**: Given expected volume (<100 trades/day), computing from raw data on each `/performance` invocation is fast enough (<100ms for thousands of rows in SQLite). This avoids maintaining pre-aggregated rollup tables and eliminates consistency issues between raw and aggregated data.

**Period definitions** (all UTC):
- `daily`: `closed_at >= today 00:00 UTC`
- `weekly`: `closed_at >= today - 7 days`
- `monthly`: `closed_at >= today - 30 days`
- `all`: no date filter

**Alternatives considered**:
- Materialized daily rollups: adds write-time overhead and sync complexity; not needed at this scale.
- Existing `performance` table: currently under-populated (only written by `update_daily_performance` which is not called automatically); raw `trades` is the source of truth.

## R4: Profit Factor Edge Case

**Decision**: When gross loss is zero, display profit factor as "∞" (infinity symbol).

**Rationale**: Profit factor = gross_profit / |gross_loss|. Division by zero when all trades are winners is a valid state. Displaying "∞" communicates the correct semantics to traders who understand the metric.

**Alternatives considered**:
- Display "N/A": less informative — the trader knows they've had only winners.
- Cap at 99.99: misleading — suggests a measurable ratio exists.

## R5: Telegram Message Formatting

**Decision**: Use plain text with Unicode line separators and aligned labels. No Markdown or HTML parse mode.

**Rationale**: The existing bot (`telegram_bot.py`) uses plain text for all commands (`/status`, `/last_signal`, `/kill`). Staying consistent avoids parse-mode mismatches and keeps messages readable across all Telegram clients (including Telegram Web). Line width target: ≤40 characters.

**Alternatives considered**:
- Telegram MarkdownV2: requires escaping special chars (`.`, `-`, `(`); error-prone.
- HTML parse mode: overkill for metric display; adds maintenance burden.

## R6: Win/Loss Classification

**Decision**: A trade is a "win" if `pnl > 0`, a "loss" if `pnl < 0`. Break-even trades (`pnl == 0`) are counted as losses.

**Rationale**: Standard convention in retail trading signal systems. Break-even trades represent opportunity cost (capital was locked, no return generated). This avoids a third category that would complicate win rate computation.

**Alternatives considered**:
- Three categories (win/loss/break-even): adds complexity to display and metric computation with minimal insight.
- Break-even as win: inflates win rate misleadingly.

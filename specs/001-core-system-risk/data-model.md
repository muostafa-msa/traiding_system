# Data Model: Core System + Risk Management

**Feature**: `001-core-system-risk`
**Date**: 2026-03-26

## Inter-Agent Data Contracts (core/types.py)

All agents communicate exclusively through these frozen dataclasses. No agent imports types from another agent. This is the sole dependency that prevents circular imports.

### OHLCBar

A single market candle — the fundamental unit of market data.

| Field | Type | Description |
|-------|------|-------------|
| timestamp | datetime | Candle open time (UTC) |
| open | float | Opening price |
| high | float | Highest price |
| low | float | Lowest price |
| close | float | Closing price |
| volume | float | Trading volume |

**Identity**: Unique by (asset, timeframe, timestamp).
**Validation**: open, high, low, close > 0; high >= max(open, close); low <= min(open, close); volume >= 0.

### IndicatorResult

Computed technical indicators for a set of candles.

| Field | Type | Description |
|-------|------|-------------|
| rsi | float | RSI (14-period), range 0-100 |
| macd_line | float | MACD line (12, 26) |
| macd_signal | float | MACD signal line (9) |
| macd_hist | float | MACD histogram (line - signal) |
| ema_20 | float | 20-period EMA |
| ema_50 | float | 50-period EMA |
| ema_200 | float | 200-period EMA |
| bb_upper | float | Bollinger upper band (20, 2) |
| bb_middle | float | Bollinger middle band (20-SMA) |
| bb_lower | float | Bollinger lower band (20, 2) |
| atr | float | ATR (14-period) |
| support | float | Nearest support level |
| resistance | float | Nearest resistance level |
| trend_direction | str | "bullish", "bearish", or "neutral" |
| breakout_probability | float | Breakout probability estimate (0.0-1.0) |

**Validation**: All float fields must be > 0 (prices are always positive for XAU/USD). RSI in [0, 100]. trend_direction in {"bullish", "bearish", "neutral"}. breakout_probability in [0.0, 1.0].

### TradeSignal

A proposed trade from the signal decision engine.

| Field | Type | Description |
|-------|------|-------------|
| asset | str | Trading pair, e.g. "XAU/USD" |
| direction | str | "BUY", "SELL", or "NO_TRADE" |
| entry_price | float | Proposed entry price |
| stop_loss | float | Calculated SL (entry - 1.5*ATR for BUY) |
| take_profit | float | Calculated TP (entry + 3.0*ATR for BUY) |
| probability | float | Confidence score, range 0.0-1.0 |
| reasoning | str | Human-readable explanation |
| timeframe | str | Timeframe used, e.g. "5min", "1h" |
| timestamp | datetime | Signal generation time (UTC) |

**Identity**: Unique by (asset, timeframe, timestamp).
**Validation**: direction in {"BUY", "SELL", "NO_TRADE"}. For BUY: stop_loss < entry_price < take_profit. For SELL: take_profit < entry_price < stop_loss. probability in [0.0, 1.0].

### RiskVerdict

The risk agent's decision on a trade signal.

| Field | Type | Description |
|-------|------|-------------|
| approved | bool | True if signal passes all risk checks |
| position_size | float | Calculated lot size (0 if rejected) |
| rejection_reason | str or None | Reason for rejection, None if approved |
| daily_risk_used | float | Current daily risk as fraction of capital |
| open_positions | int | Number of currently open positions |

**Validation**: If approved is True, position_size > 0 and rejection_reason is None. If approved is False, rejection_reason is not None.

### AccountState

Current account state for risk management decisions.

| Field | Type | Description |
|-------|------|-------------|
| capital | float | Current capital balance |
| open_positions | int | Number of open positions |
| daily_pnl | float | Today's profit/loss (resets at UTC midnight) |
| kill_switch_active | bool | True if kill switch has been triggered |
| updated_at | datetime | Last update time (UTC) |

**Identity**: Singleton — one row, updated in place.
**Lifecycle**: `daily_pnl` resets to 0.0 and `kill_switch_active` resets to False at midnight UTC (when `updated_at` date < current UTC date).

### FinalSignal

A complete signal ready for delivery, combining signal + risk verdict + formatted message.

| Field | Type | Description |
|-------|------|-------------|
| signal | TradeSignal | The original trade signal |
| risk | RiskVerdict | The risk evaluation result |
| formatted_message | str | Human-readable Telegram message |

## Persistence Schema (storage/database.py)

### signals table

Stores every signal generated (approved or rejected) for audit trail.

| Column | Type | Constraints |
|--------|------|-------------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT |
| asset | TEXT | NOT NULL |
| direction | TEXT | NOT NULL |
| entry_price | REAL | NOT NULL |
| stop_loss | REAL | NOT NULL |
| take_profit | REAL | NOT NULL |
| probability | REAL | NOT NULL |
| timeframe | TEXT | NOT NULL |
| reasoning | TEXT | |
| technical_score | REAL | |
| pattern_score | REAL | |
| sentiment_score | REAL | |
| volatility_factor | REAL | |
| created_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP |
| status | TEXT | DEFAULT 'pending' |

**Status lifecycle**: pending -> approved -> active -> closed OR pending -> rejected.

### trades table

Stores opened and closed trade records.

| Column | Type | Constraints |
|--------|------|-------------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT |
| signal_id | INTEGER | NOT NULL, REFERENCES signals(id) |
| position_size | REAL | NOT NULL |
| entry_price | REAL | NOT NULL |
| exit_price | REAL | |
| pnl | REAL | |
| pnl_percent | REAL | |
| opened_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP |
| closed_at | TIMESTAMP | |
| close_reason | TEXT | tp_hit, sl_hit, manual, kill_switch |

### performance table

Daily rollup of trading performance.

| Column | Type | Constraints |
|--------|------|-------------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT |
| date | TEXT | NOT NULL, UNIQUE |
| total_signals | INTEGER | DEFAULT 0 |
| trades_taken | INTEGER | DEFAULT 0 |
| wins | INTEGER | DEFAULT 0 |
| losses | INTEGER | DEFAULT 0 |
| gross_profit | REAL | DEFAULT 0.0 |
| gross_loss | REAL | DEFAULT 0.0 |
| net_pnl | REAL | DEFAULT 0.0 |
| win_rate | REAL | DEFAULT 0.0 |
| profit_factor | REAL | DEFAULT 0.0 |
| max_drawdown | REAL | DEFAULT 0.0 |
| sharpe_ratio | REAL | DEFAULT 0.0 |

### news table

Prepared for Phase 2. Schema created in Phase 1 to avoid migrations.

| Column | Type | Constraints |
|--------|------|-------------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT |
| source | TEXT | NOT NULL |
| headline | TEXT | NOT NULL |
| url | TEXT | |
| published_at | TIMESTAMP | |
| classification | TEXT | |
| confidence | REAL | |
| collected_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP |

### account_state table

Singleton row tracking current account state.

| Column | Type | Constraints |
|--------|------|-------------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT |
| capital | REAL | NOT NULL |
| open_positions | INTEGER | DEFAULT 0 |
| daily_pnl | REAL | DEFAULT 0.0 |
| kill_switch_active | INTEGER | DEFAULT 0 |
| updated_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP |

## Entity Relationships

```
AccountState (singleton)
    |
    v
TradeSignal ---> RiskVerdict ---> FinalSignal
    ^                                  |
    |                                  v
OHLCBar --> IndicatorResult       Telegram / DB
```

- OHLCBar is input to IndicatorResult computation
- IndicatorResult feeds into TradeSignal generation (Phase 3 scoring)
- TradeSignal is evaluated by RiskVerdict
- FinalSignal combines both for delivery and persistence
- AccountState is read by risk agent and updated after each trade

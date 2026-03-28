# Agent Contracts: Core System + Risk Management

**Feature**: `001-core-system-risk`
**Date**: 2026-03-26

## Overview

Each agent has a defined input/output contract. All types reference `core/types.py`. Agents receive dependencies via constructor injection (config, logger, database reference). No agent imports from another agent's module — only from `core/types.py`.

---

## Market Data Agent (`data/market_data.py`)

**Responsibility**: Fetch OHLC candle data from external API.

**Interface**:
```
class MarketDataProvider (ABC):
    get_ohlc(asset: str, timeframe: str, bars: int) -> list[OHLCBar]
```

**Input**: Asset string ("XAU/USD"), timeframe ("5min", "15min", "1h", "4h"), number of bars (default 250).
**Output**: List of OHLCBar, sorted by timestamp ascending.
**Errors**: Raises `MarketDataError` on API failure, rate limit, or invalid response. Caller handles retry logic.
**Implementations**: `TwelveDataProvider`, `AlphaVantageProvider`, `PolygonProvider`.

---

## Chart Analysis Agent (`analysis/indicators.py`)

**Responsibility**: Compute technical indicators from candle data.

**Interface**:
```
compute_indicators(bars: list[OHLCBar]) -> IndicatorResult
```

**Input**: List of OHLCBar (minimum 200 bars for valid EMA-200).
**Output**: Single IndicatorResult with all indicator values computed from the most recent bar.
**Errors**: Raises `ValueError` if fewer than 200 bars provided.
**Determinism**: Same input always produces same output. No external state.

---

## Risk Management Agent (`agents/risk_agent.py`)

**Responsibility**: Evaluate trade signals against risk rules. Approve or reject.

**Interface**:
```
class RiskAgent:
    __init__(config: AppConfig, database: Database)
    evaluate(signal: TradeSignal) -> RiskVerdict
```

**Input**: A TradeSignal to evaluate.
**Output**: RiskVerdict with approval status, position size, and rejection reason.
**State reads**: AccountState from database (capital, open positions, daily P&L, kill switch).
**State writes**: Updates kill_switch_active in account_state if daily loss exceeds threshold.
**Rules checked (in order)**:
1. Kill switch already active → REJECT
2. Daily loss > 5% → activate kill switch, REJECT
3. Daily risk + 1% > 3% → REJECT
4. Open positions >= 2 → REJECT
5. Risk-reward ratio < 1.8 → REJECT
6. All pass → APPROVE with calculated position size

---

## Signal Delivery Agent (`execution/signal_generator.py`)

**Responsibility**: Format signals into human-readable Telegram messages.

**Interface**:
```
format_signal(signal: TradeSignal, risk: RiskVerdict) -> str
```

**Input**: Approved TradeSignal + RiskVerdict.
**Output**: Formatted string ready for Telegram delivery.
**Format**:
```
GOLD SIGNAL
Asset: XAU/USD
Direction: BUY
Entry: 2335.00
Stop Loss: 2320.00
Take Profit: 2365.00
Confidence: 93%
Reason: [reasoning text]
```

---

## Telegram Bot (`execution/telegram_bot.py`)

**Responsibility**: Broadcast signals and handle commands.

**Interface**:
```
class TelegramBot:
    __init__(config: AppConfig, database: Database)
    start() -> None           # Start bot in background thread
    stop() -> None            # Graceful shutdown
    broadcast(message: str) -> None  # Send message to configured chat
```

**Commands** (restricted to configured chat ID):
- `/status` → Returns: uptime, last cycle time, open positions, kill switch status
- `/last_signal` → Returns: most recent signal details
- `/performance` → Returns: total signals, win rate, profit factor, daily P&L
- `/kill` → Activates kill switch, confirms to user

**No-op mode**: If `TELEGRAM_BOT_TOKEN` is empty/unset, all methods are silent no-ops. No exceptions raised.

---

## Database / Performance Tracker (`storage/database.py`)

**Responsibility**: Persist and query all system data.

**Interface**:
```
class Database:
    __init__(db_path: str)

    # Signals
    save_signal(signal: TradeSignal, status: str) -> int
    get_last_signal(asset: str) -> dict | None

    # Trades
    open_trade(signal_id: int, position_size: float, entry_price: float) -> int
    close_trade(trade_id: int, exit_price: float, reason: str) -> None

    # Account State
    get_account_state() -> AccountState
    update_account_state(**kwargs) -> None
    reset_daily_if_needed() -> None  # Check UTC date, reset if new day

    # Performance
    get_daily_performance(date: str) -> dict
    update_daily_performance(date: str, **kwargs) -> None

    # Queries
    get_open_positions_count() -> int
    get_daily_pnl() -> float
```

**Startup**: Creates all 5 tables if they don't exist. Initializes account_state row if empty (using `initial_capital` from config).

---

## Pipeline Orchestrator (`core/scheduler.py`)

**Responsibility**: Run the full pipeline on schedule per timeframe.

**Pipeline per cycle**:
```
1. market_data.get_ohlc(asset, timeframe, 250)
2. indicators.compute_indicators(bars)
3. signal_generator.format_summary(indicators)  # Phase 1: summary only
4. risk_agent.evaluate(signal)                   # Phase 3: full signals
5. telegram_bot.broadcast(message)
6. database.save_signal(...)
7. database.reset_daily_if_needed()
```

**Error handling**: Any exception in steps 1-6 logs the error and skips the cycle. The scheduler continues to the next interval.

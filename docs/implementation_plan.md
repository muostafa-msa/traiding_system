# AI Market Intelligence & Trading Signal System — Implementation Plan

**Version**: 1.1 | **Date**: 2026-03-26 | **Constitution**: `.specify/memory/constitution.md`

## Context

Build an AI-driven market analysis system (Quant AI Trading Research Engine) that monitors XAU/USD, analyzes charts + news sentiment, produces high-confidence BUY/SELL signals with strict risk management, and delivers them via Telegram. Later: 10 assets, semi-automatic trading, cloud deployment.

---

## High-Level Architecture

```
                    +---------------------+
                    |  Market Data Agent  |
                    |  (prices + candles) |
                    +----------+----------+
                               |
                               v
                     +------------------+
                     | Chart Analysis   |
                     | Technical Agent  |
                     +---------+--------+
                               |
                               v
        +------------------------------------+
        |         Signal Intelligence        |
        |                                    |
        |  News Agent      Sentiment Agent   |
        |       |                |           |
        |       +--------+------+           |
        |                v                   |
        |         Signal Decision AI         |
        +---------------+--------------------+
                        |
                        v
               Risk Management Agent
                        |
                        v
                Signal Generator
                        |
                        v
                 Telegram Bot
                        |
                        v
                Performance Tracker
```

## Data Pipeline

```
market data --> indicators --> pattern detection
                       |
                    scoring
                       |
news --> sentiment --> macro score
                       |
             signal decision engine
                       |
                 risk manager
                       |
               telegram signal
                       |
             performance tracker
```

---

## Design Decisions (from review)

These decisions override the original ChatGPT plan where they conflict:

| Decision | Original Plan | Revised |
|----------|--------------|---------|
| Risk Management | Phase 5 | **Phase 1** — constitution requires risk on every signal |
| Market Data Provider | TwelveData hardcoded | **Provider abstraction** (ABC) — swap providers via config |
| LLM for Sentiment | Unspecified | **LLM abstraction** — OpenAI, Claude, or keyword fallback via config |
| News Sources | Twitter/X + NewsAPI | **RSS feeds only** (free, no API cost) |
| Backtest Data | Same API provider | **CSV loader** as primary source |
| Execution Loop | Fixed 5 min | **Per-timeframe intervals** (5m/15m/1h/4h each on own schedule) |
| Starting Capital | $10,000 hardcoded | **Configurable** via `.env` |
| Telegram Bot | Assumed ready | **Built for deferred config** — runs without token in dev mode |
| Circular Deps | Not addressed | **`core/types.py`** as sole inter-agent contract layer |

---

## File Manifest

All files under project root.

### Root

| File | Purpose |
|------|---------|
| `main.py` | Entry point: init config, logger, DB, scheduler, Telegram bot, graceful shutdown |
| `requirements.txt` | Pinned dependencies |
| `.env.example` | Template for API keys, Telegram token, capital, thresholds |
| `.gitignore` | Python, .env, SQLite, logs, IDE files |

### `core/` — Shared Infrastructure

| File | Purpose |
|------|---------|
| `core/__init__.py` | Package |
| `core/types.py` | **All inter-agent data contracts** as frozen dataclasses — the ONLY module that every agent imports. No agent imports another agent's types. |
| `core/config.py` | Loads `.env` via python-dotenv, exposes `AppConfig` dataclass (API keys, risk params, scoring weights, intervals, capital) |
| `core/logger.py` | Rotating file handler + console via `get_logger(name)` factory |
| `core/scheduler.py` | APScheduler wrapper with per-timeframe job scheduling. Orchestrates: data -> analysis -> signal -> risk -> delivery -> log |

### `data/` — Data Collection

| File | Purpose |
|------|---------|
| `data/__init__.py` | Package |
| `data/market_data.py` | **Market Data Agent**: `MarketDataProvider` ABC + concrete implementations (`TwelveDataProvider`, `AlphaVantageProvider`, `PolygonProvider`). Factory function selects via config. Handles rate limiting, retries. |
| `data/news_data.py` | **News Agent**: RSS feed collector via `feedparser`. Filters by keywords (gold, inflation, fed, interest rate, usd, war, oil, cpi, nfp). Dedup cache by headline hash. |
| `data/csv_loader.py` | Loads historical OHLC data from CSV files for backtesting. Supports multiple CSV formats (MT4, TradingView, generic). |

### `analysis/` — Technical Analysis

| File | Purpose |
|------|---------|
| `analysis/__init__.py` | Package |
| `analysis/indicators.py` | **Chart Analysis Agent**: RSI(14), MACD(12,26,9), EMA(20,50,200), Bollinger Bands(20,2), ATR(14), support/resistance via swing high/low pivot points, trend direction via EMA alignment. Returns `IndicatorResult`. |
| `analysis/pattern_detection.py` | **Pattern Detection Agent**: rule-based detectors — breakout, triangle, double top/bottom, head & shoulders, trading range. Each pattern function returns confidence 0.0-1.0. |

### `agents/` — Intelligence Agents

| File | Purpose |
|------|---------|
| `agents/__init__.py` | Package |
| `agents/chart_agent.py` | Multi-timeframe orchestrator: runs indicators + patterns on 5m/15m/1h/4h, selects best timeframe by clarity score. |
| `agents/sentiment_agent.py` | **LLM abstraction**: `SentimentProvider` ABC with `OpenAIProvider`, `ClaudeProvider`, `KeywordProvider` implementations. Classifies Bullish/Bearish/Neutral with confidence. Config selects provider. |
| `agents/news_agent.py` | Wraps `news_data.py` + `sentiment_agent.py`. Checks news blackout (Fed, NFP, CPI) via keyword matching on collected headlines. Returns `{news_items, sentiments, macro_score, is_blackout}`. |
| `agents/signal_agent.py` | **Signal Decision Agent**: implements scoring algorithm (see below). Combines technical + pattern + sentiment + volatility into probability via sigmoid. Threshold: 0.68. |
| `agents/risk_agent.py` | **Risk Management Agent**: 1% risk/trade, 3% daily, 2 max positions, kill switch at 5% daily loss, SL/TP via ATR, news blackout gate. |

### `execution/` — Signal Delivery

| File | Purpose |
|------|---------|
| `execution/__init__.py` | Package |
| `execution/signal_generator.py` | Formats `TradeSignal` + `RiskVerdict` into human-readable Telegram message with all required fields. |
| `execution/telegram_bot.py` | `python-telegram-bot` async bot. Commands: `/status`, `/last_signal`, `/performance`, `/kill`. Auto-broadcast on signal. Graceful no-op if token not configured (dev mode). |

### `storage/` — Persistence

| File | Purpose |
|------|---------|
| `storage/__init__.py` | Package |
| `storage/database.py` | SQLite wrapper. Schema auto-creation. CRUD for 5 tables (signals, trades, performance, news, account_state). Metric computation (win rate, profit factor, drawdown, Sharpe). `get_account_state()` for risk agent. |

### `backtesting/` — Historical Testing

| File | Purpose |
|------|---------|
| `backtesting/__init__.py` | Package |
| `backtesting/backtester.py` | Loads CSV data via `csv_loader.py`. Replays bar-by-bar through the full pipeline. Records signals and simulated outcomes. Outputs metrics via vectorbt. |
| `backtesting/strategy.py` | Wraps scoring algorithm into vectorbt-compatible strategy. Supports parameter sweeps for weight optimization. |

### `tests/`

| File | Purpose |
|------|---------|
| `tests/__init__.py` | Package |
| `tests/conftest.py` | Shared fixtures: sample OHLC data, test config, in-memory SQLite, mock providers |
| `tests/test_indicators.py` | Unit tests for all indicator computations against known values |
| `tests/test_patterns.py` | Unit tests for pattern detection with synthetic candle data |
| `tests/test_signal_scoring.py` | Unit tests for scoring algorithm with fixed inputs -> expected outputs |
| `tests/test_risk_agent.py` | All risk rules, kill switch, position limits, edge cases |
| `tests/test_sentiment.py` | Sentiment classification with mocked LLM responses |
| `tests/test_database.py` | DB operations and metric calculations |
| `tests/test_integration.py` | End-to-end: synthetic market data through full pipeline to final signal |

---

## Core Data Contracts (`core/types.py`)

All inter-agent communication uses these frozen dataclasses. No agent imports types from another agent.

```python
OHLCBar: timestamp, open, high, low, close, volume
IndicatorResult: rsi, macd_line, macd_signal, macd_hist, ema_20, ema_50, ema_200,
                 bb_upper, bb_middle, bb_lower, atr, support, resistance, trend_direction
PatternResult: pattern_name, direction (+1/-1), confidence (0.0-1.0), description
NewsItem: source, headline, url, published_at, raw_text
SentimentResult: classification (Bullish/Bearish/Neutral), confidence, reasoning
TechnicalScore: score (-1.0 to +1.0), components (dict of sub-scores)
TradeSignal: asset, direction (BUY/SELL/NO_TRADE), entry_price, stop_loss, take_profit,
             probability, reasoning, timestamp, timeframe
RiskVerdict: approved (bool), position_size, rejection_reason, daily_risk_used, open_positions
FinalSignal: signal (TradeSignal), risk (RiskVerdict), formatted_message
```

---

## Signal Scoring Algorithm

### Input Dimensions

**A. Technical Score (weight: 0.40)**

| Indicator | Bullish | Bearish | Sub-weight |
|-----------|---------|---------|------------|
| RSI(14) | < 30 -> +1.0; 30-45 -> +0.5 | > 70 -> -1.0; 55-70 -> -0.5 | 0.15 |
| MACD | Histogram positive + rising -> +1.0; crossover -> +0.8 | Negative + falling -> -1.0 | 0.20 |
| EMA alignment | Price > EMA20 > EMA50 > EMA200 -> +1.0 | Inverse -> -1.0 | 0.25 |
| Bollinger Bands | Near lower band + squeeze -> +0.8 | Near upper + expansion -> -0.8 | 0.15 |
| Support/Resistance | Bounce off support -> +0.7 | Rejected at resistance -> -0.7 | 0.15 |
| Breakout | Breaking resistance with volume -> +1.0 | Breaking support -> -1.0 | 0.10 |

```
technical_score = sum(sub_score_i * sub_weight_i)  # range [-1.0, +1.0]
```

**B. Pattern Score (weight: 0.20)**

```
pattern_score = mean(direction_i * confidence_i)  # across all detected patterns
# 0.0 if no patterns detected (neutral, does not penalize)
```

**C. Sentiment Score (weight: 0.25)**

Aggregate `macro_score` from sentiment agent, range [-1.0, +1.0].

**D. Volatility Adjustment (weight: 0.15)**

```
vol_ratio = current_atr / avg_atr_20

if vol_ratio > 1.5:   factor = 0.7   # high vol = dampen (less predictable)
elif vol_ratio < 0.8:  factor = 1.1   # squeeze = boost (breakout potential)
else:                   factor = 1.0   # normal
```

### Combination Formula

```python
raw_score = (0.40 * technical_score +
             0.20 * pattern_score +
             0.25 * sentiment_score +
             0.15 * trend_strength)

adjusted = raw_score * volatility_factor

# Sigmoid maps [-1, +1] to [0, 1] probability space
probability = 1.0 / (1.0 + math.exp(-4.0 * adjusted))

if adjusted > 0:
    direction = "BUY"
elif adjusted < 0:
    direction = "SELL"
    probability = 1.0 - probability  # flip for sell confidence
else:
    direction = "NO_TRADE"

# ONLY generate signal if probability >= 0.68
```

Sigmoid with steepness 4.0 maps:
- adjusted +0.50 -> probability ~0.88
- adjusted +0.30 -> probability ~0.77
- adjusted +0.15 -> probability ~0.65 (below threshold, NO_TRADE)
- adjusted  0.00 -> probability  0.50 (NO_TRADE)

### Multi-Timeframe Selection

```python
# For each timeframe (5m, 15m, 1h, 4h):
clarity = abs(technical_score) * trend_strength * (1.0 / vol_ratio)

# Select timeframe with highest clarity score
# This favors: strong trend + decisive signal + moderate volatility
```

---

## Risk Model Math

### Stop Loss / Take Profit

```
BUY:  SL = entry - 1.5 * ATR    TP = entry + 3.0 * ATR
SELL: SL = entry + 1.5 * ATR    TP = entry - 3.0 * ATR

# Guaranteed Risk-Reward = 3.0 / 1.5 = 2.0  (exceeds 1.8 minimum)
```

### Position Sizing

```
risk_amount = max_risk_per_trade * capital    # default 0.01 * capital
price_risk  = abs(entry - stop_loss)          # = 1.5 * ATR
position_size = risk_amount / price_risk

# For XAU/USD: 1 lot = 100 oz
position_lots = position_size / 100
```

### Safety Gates (checked in order)

```
1. kill_switch_active == True        -> REJECT ("Kill switch active")
2. daily_loss > 5% of capital        -> ACTIVATE KILL SWITCH, REJECT
3. daily_risk_used + 1% > 3%         -> REJECT ("Daily risk limit reached")
4. open_positions >= 2               -> REJECT ("Max positions reached")
5. news_blackout active              -> REJECT ("News blackout period")
6. risk_reward_ratio < 1.8           -> REJECT ("Insufficient risk-reward")
```

---

## Database Schema

### signals
```sql
CREATE TABLE signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset TEXT NOT NULL,
    direction TEXT NOT NULL,
    entry_price REAL NOT NULL,
    stop_loss REAL NOT NULL,
    take_profit REAL NOT NULL,
    probability REAL NOT NULL,
    timeframe TEXT NOT NULL,
    reasoning TEXT,
    technical_score REAL,
    pattern_score REAL,
    sentiment_score REAL,
    volatility_factor REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'pending'
);
```

### trades
```sql
CREATE TABLE trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    signal_id INTEGER NOT NULL REFERENCES signals(id),
    position_size REAL NOT NULL,
    entry_price REAL NOT NULL,
    exit_price REAL,
    pnl REAL,
    pnl_percent REAL,
    opened_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    closed_at TIMESTAMP,
    close_reason TEXT
);
```

### performance
```sql
CREATE TABLE performance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL UNIQUE,
    total_signals INTEGER DEFAULT 0,
    trades_taken INTEGER DEFAULT 0,
    wins INTEGER DEFAULT 0,
    losses INTEGER DEFAULT 0,
    gross_profit REAL DEFAULT 0.0,
    gross_loss REAL DEFAULT 0.0,
    net_pnl REAL DEFAULT 0.0,
    win_rate REAL DEFAULT 0.0,
    profit_factor REAL DEFAULT 0.0,
    max_drawdown REAL DEFAULT 0.0,
    sharpe_ratio REAL DEFAULT 0.0
);
```

### news
```sql
CREATE TABLE news (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    headline TEXT NOT NULL,
    url TEXT,
    published_at TIMESTAMP,
    classification TEXT,
    confidence REAL,
    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### account_state
```sql
CREATE TABLE account_state (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    capital REAL NOT NULL,
    open_positions INTEGER DEFAULT 0,
    daily_pnl REAL DEFAULT 0.0,
    kill_switch_active INTEGER DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## Dependency Graph (no circular deps)

```
core/types.py              <-- imported by everything, imports nothing from project
core/config.py             <-- imported by everything, imports nothing from project
core/logger.py             <-- imported by everything, imports nothing from project
storage/database.py        <-- types, config
data/market_data.py        <-- types, config, logger
data/news_data.py          <-- types, config, logger
data/csv_loader.py         <-- types
analysis/indicators.py     <-- types
analysis/pattern_detection.py <-- types
agents/chart_agent.py      <-- market_data, indicators, pattern_detection, types
agents/sentiment_agent.py  <-- types, config
agents/news_agent.py       <-- news_data, sentiment_agent, types
agents/signal_agent.py     <-- types, config
agents/risk_agent.py       <-- types, config, database
execution/signal_generator.py <-- types
execution/telegram_bot.py  <-- types, config, database
core/scheduler.py          <-- ALL agents, database (orchestrator)
main.py                    <-- config, scheduler, telegram_bot, database, logger
```

Direction: `main -> scheduler -> agents -> data/analysis -> core/types`. No cycles.

---

## Configuration (`core/config.py`)

All magic numbers live here. Agents receive config via constructor injection.

```python
@dataclass
class AppConfig:
    # API Keys (all optional — system degrades gracefully)
    market_data_provider: str    # "twelvedata" | "alphavantage" | "polygon"
    market_data_api_key: str
    sentiment_provider: str      # "openai" | "claude" | "keyword"
    sentiment_api_key: str
    telegram_bot_token: str
    telegram_chat_id: str

    # Asset
    asset: str = "XAU/USD"

    # Timeframes + intervals
    timeframes: tuple = ("5min", "15min", "1h", "4h")
    interval_5min: int = 5       # minutes between runs
    interval_15min: int = 15
    interval_1h: int = 60
    interval_4h: int = 240

    # Signal threshold
    signal_threshold: float = 0.68

    # Scoring weights
    weight_technical: float = 0.40
    weight_pattern: float = 0.20
    weight_sentiment: float = 0.25
    weight_volatility: float = 0.15

    # Risk parameters
    initial_capital: float       # from .env, no default
    max_risk_per_trade: float = 0.01
    max_daily_risk: float = 0.03
    max_open_positions: int = 2
    kill_switch_threshold: float = 0.05
    sl_atr_multiplier: float = 1.5
    tp_atr_multiplier: float = 3.0
    min_risk_reward: float = 1.8

    # Infrastructure
    db_path: str = "storage/trading.db"
    log_level: str = "INFO"
    log_file: str = "logs/trading.log"
    csv_data_dir: str = "data/historical/"
```

---

## Development Phases

### Phase 1 — Core System + Risk (REVISED)

**Goal**: Market data -> indicators -> signal summary -> risk check -> Telegram

This phase includes risk management from day one (constitution requirement).

Build in order:
1. `core/__init__.py`, `core/types.py` — all data contracts
2. `core/config.py` — configuration loading from `.env`
3. `core/logger.py` — logging infrastructure
4. `storage/__init__.py`, `storage/database.py` — schema + CRUD (all 5 tables)
5. `data/__init__.py`, `data/market_data.py` — provider abstraction + first implementation
6. `analysis/__init__.py`, `analysis/indicators.py` — RSI, MACD, EMA, BB, ATR, support/resistance
7. `agents/__init__.py`, `agents/risk_agent.py` — all risk rules, kill switch, position sizing
8. `execution/__init__.py`, `execution/signal_generator.py` — message formatting
9. `execution/telegram_bot.py` — bot with /status, /last_signal, /kill + broadcast (graceful no-op without token)
10. `core/scheduler.py` — per-timeframe scheduling, basic pipeline
11. `main.py` — wire everything, graceful shutdown
12. `requirements.txt`, `.env.example`, `.gitignore`

Tests: `tests/conftest.py`, `tests/test_indicators.py`, `tests/test_risk_agent.py`, `tests/test_database.py`

**Phase 1 delivers**: A running system that fetches XAU/USD data, computes indicators, applies risk rules to any manual signal, and sends summaries to Telegram.

### Phase 2 — Sentiment Intelligence

**Goal**: RSS news collection + sentiment scoring

1. `data/news_data.py` — RSS feed collector via feedparser
2. `agents/sentiment_agent.py` — provider abstraction (OpenAI/Claude/keyword), keyword fallback as default
3. `agents/news_agent.py` — orchestration + news blackout detection
4. Update `storage/database.py` — news table operations (schema already exists from Phase 1)

Tests: `tests/test_sentiment.py`

**Phase 2 delivers**: News sentiment flowing into the pipeline, blackout detection active.

### Phase 3 — AI Decision Engine

**Goal**: Full probability-based signal generation with scoring algorithm

1. `analysis/pattern_detection.py` — 6 rule-based pattern detectors
2. `agents/chart_agent.py` — multi-timeframe analysis + timeframe selection
3. `agents/signal_agent.py` — scoring algorithm + sigmoid probability + 0.68 threshold
4. Update `core/scheduler.py` — full pipeline: chart_agent -> news_agent -> signal_agent -> risk_agent -> delivery

Tests: `tests/test_patterns.py`, `tests/test_signal_scoring.py`

**Phase 3 delivers**: Complete autonomous signal generation. The system now produces probability-scored BUY/SELL/NO_TRADE decisions with reasoning, risk-checked before delivery.

### Phase 4 — Backtesting Engine

**Goal**: Historical validation + strategy optimization

1. `data/csv_loader.py` — CSV parser for MT4/TradingView/generic formats
2. `backtesting/__init__.py`, `backtesting/strategy.py` — vectorbt-compatible strategy wrapper
3. `backtesting/backtester.py` — bar-by-bar replay through full pipeline, metrics output

**Phase 4 delivers**: Ability to evaluate signal quality on 1 year of historical data. Results inform weight tuning.

### Phase 5 — Polish + Telegram Commands

**Goal**: Full Telegram interface + performance reporting

1. Update `execution/telegram_bot.py` — add /performance command with formatted metrics
2. Update `storage/database.py` — performance rollup queries, Sharpe ratio computation
3. Add performance dashboard formatting to signal_generator.py

**Phase 5 delivers**: Complete monitoring and control via Telegram.

### Phase 6 — Multi-Asset Support

**Goal**: 10 assets in parallel

1. Update `core/config.py` — `assets: list[str]` with per-asset overrides
2. Update `core/scheduler.py` — `concurrent.futures.ThreadPoolExecutor` per asset
3. Update all agents — accept `asset` parameter, no hardcoded XAU/USD
4. Update `storage/database.py` — all queries filtered by asset

**Phase 6 delivers**: System monitoring up to 10 assets with independent signal generation and risk tracking per asset.

---

## Per-Timeframe Scheduling

Instead of a single 5-minute loop, the scheduler runs independent jobs:

| Timeframe | Interval | What runs |
|-----------|----------|-----------|
| 5min | Every 5 minutes | Full pipeline: data -> indicators -> patterns -> signal -> risk -> delivery |
| 15min | Every 15 minutes | Same pipeline, 15min candles |
| 1h | Every 60 minutes | Same pipeline, 1h candles |
| 4h | Every 240 minutes | Same pipeline, 4h candles |

The Signal Decision Agent receives results from all recently-run timeframes and uses the **clarity score** to weight them. A signal is only generated when the best timeframe crosses the 0.68 probability threshold.

---

## Technology Stack

| Category | Choice |
|----------|--------|
| Language | Python 3.11 |
| Data | pandas, numpy |
| Indicators | ta (technical analysis library) |
| HTTP | requests |
| RSS | feedparser |
| Scheduling | APScheduler |
| Telegram | python-telegram-bot |
| Backtesting | vectorbt |
| Storage | SQLite (stdlib sqlite3) |
| Config | python-dotenv |
| Testing | pytest, pytest-asyncio |
| LLM (optional) | openai / anthropic SDK |

---

## Example Signal Flow

```
1. Market Data Agent fetches XAU/USD 1h candles from TwelveData
2. Chart Analysis Agent computes indicators:
   - Trend: bullish (EMA aligned)
   - RSI: 63 (neutral-bullish)
   - MACD: bullish crossover
   - Support: 2320, Resistance: 2350

3. Pattern Detection Agent finds: breakout above 2350 (confidence: 0.70)

4. News Agent collects RSS headlines, Sentiment Agent classifies:
   - "FED signals rate cuts" -> Bullish, confidence 0.78
   - macro_score: +0.55

5. Signal Decision Agent scores:
   - technical: 0.65, pattern: 0.70, sentiment: 0.55, trend: 0.80
   - raw = 0.40*0.65 + 0.20*0.70 + 0.25*0.55 + 0.15*0.80 = 0.657
   - volatility factor: 1.0 (normal ATR)
   - probability = sigmoid(4.0 * 0.657) = 0.93
   - Direction: BUY, Probability: 93%

6. Risk Management Agent checks:
   - Daily risk used: 0% (first trade) -> OK
   - Open positions: 0 -> OK
   - Kill switch: inactive -> OK
   - News blackout: none -> OK
   - SL = 2335 - 1.5 * 10 = 2320
   - TP = 2335 + 3.0 * 10 = 2365
   - Position size = (0.01 * capital) / 15 = ...
   - APPROVED

7. Signal Generator formats message:

   GOLD SIGNAL
   Asset: XAU/USD
   Direction: BUY
   Entry: 2335
   Stop Loss: 2320
   Take Profit: 2365
   Confidence: 93%
   Reason: Bullish breakout + positive macro sentiment

8. Telegram Bot sends to channel
9. Performance Tracker logs signal to SQLite
```

---

## Future Features (post Phase 6)

- Reinforcement learning for strategy optimization
- Portfolio optimization for multi-asset allocation
- Semi-automatic trading via broker API integration
- Cloud deployment (Docker + scheduling service)
- CNN-based pattern detection on chart images
- Economic calendar API for smarter news blackout

---

## Verification Plan

| Phase | How to verify |
|-------|--------------|
| Phase 1 | `python main.py` -> Telegram receives indicator summaries; risk agent rejects signals missing SL/TP |
| Phase 2 | RSS feeds collected, sentiment scores appear in news table |
| Phase 3 | Signals include probability; NO_TRADE when below 0.68; full reasoning |
| Phase 4 | `python -m backtesting.backtester --csv data/historical/xauusd_1h.csv` -> metrics output |
| Phase 5 | `/performance` Telegram command returns formatted metrics |
| Phase 6 | Configure 3 assets, verify independent signals per asset |
| All | `pytest tests/ -v` after each phase |
| Integration | `pytest tests/test_integration.py` — synthetic data through full pipeline |

---

## Coding Workflow

| Role | Responsibility |
|------|---------------|
| Claude | Architecture design, planning, code review |
| GLM5 | Implementation of specifications |

Process:
1. Specification created per feature/phase
2. Implementation tasks generated
3. GLM5 writes code against spec
4. Claude reviews architecture and logic
5. Tests validate the implementation
6. Iterate until passing

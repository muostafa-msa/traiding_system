# AI Market Intelligence & Trading Signal System — Implementation Plan

**Version**: 2.0 | **Date**: 2026-03-28 | **Constitution**: `.specify/memory/constitution.md` (v1.1.0)

## Context

Build an AI-driven market analysis system that monitors XAU/USD, analyzes charts + news sentiment via ML models (FinBERT, LSTM, XGBoost, GPT-2B OSS), produces high-confidence BUY/SELL signals with strict risk management, and delivers them via Telegram. Later: 10 assets, semi-automatic trading, cloud deployment.

All ML models run **locally** (CPU with optional GPU). External APIs are used only for market data and news retrieval.

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
        |  News Agent  →  FinBERT Sentiment  |
        |  Market Data →  LSTM Prediction    |
        |                                    |
        |  All features → XGBoost Scoring    |
        |                                    |
        |  If threshold → GPT-2B Reasoning   |
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
market data --> indicators --> pattern detection ─┐
                                                  │
market data --> LSTM prediction ──────────────────┤
                                                  ├─> XGBoost probability
news ──────--> FinBERT sentiment ─────────────────┤
                                                  │
                volatility metrics ───────────────┘
                       |
                 if >= threshold
                       |
                 GPT-2B reasoning
                       |
                 risk manager
                       |
               telegram signal
                       |
             performance tracker
```

---

## Local-First Architecture

Per constitution v1.1, the system must operate fully locally:

| Constraint | Implementation |
|-----------|---------------|
| CPU execution | All models support CPU inference; torch with `device="cpu"` default |
| Optional GPU | Auto-detect CUDA/MPS via `torch.cuda.is_available()`; config override |
| Offline after install | All model weights downloaded once at setup; no runtime cloud deps for inference |
| Low memory | Batch inference, model unloading between cycles, quantized models where possible |
| External APIs | Market data (TwelveData/AlphaVantage/Polygon) and news RSS only |

Model sizes (approximate):

| Model | Size | RAM | Notes |
|-------|------|-----|-------|
| FinBERT | ~440 MB | ~1 GB | `ProsusAI/finbert` via transformers |
| LSTM | ~5-50 MB | ~200 MB | Custom trained, lightweight |
| XGBoost | ~1-10 MB | ~100 MB | Trained on tabular features |
| GPT-2B OSS | ~500 MB–6 GB | ~2-8 GB | Size depends on chosen variant; quantized recommended |

---

## Design Decisions (from review)

These decisions override the original ChatGPT plan where they conflict:

| Decision | Original Plan | Revised |
|----------|--------------|---------|
| Risk Management | Phase 5 | **Phase 1** — constitution requires risk on every signal |
| Market Data Provider | TwelveData hardcoded | **Provider abstraction** (ABC) — swap providers via config |
| Sentiment Analysis | Unspecified LLM | **FinBERT** — local financial sentiment model, no API dependency |
| Time Series Prediction | None | **LSTM** — local model for price direction and volatility prediction |
| Signal Probability | Weighted formula | **XGBoost** — trained model combining all features into probability |
| Signal Explanation | Template strings | **GPT-2B OSS** — local LLM for human-readable reasoning |
| News Sources | Twitter/X + NewsAPI | **RSS feeds only** (free, no API cost) |
| Backtest Data | Same API provider | **CSV loader** as primary source |
| Execution Loop | Fixed 5 min | **Per-timeframe intervals** (5m/15m/1h/4h each on own schedule) |
| Starting Capital | $10,000 hardcoded | **Configurable** via `.env` |
| Telegram Bot | Assumed ready | **Built for deferred config** — runs without token in dev mode |
| Circular Deps | Not addressed | **`core/types.py`** as sole inter-agent contract layer |
| Deployment | Cloud assumed | **Local-first** — CPU default, optional GPU, offline inference |

---

## File Manifest

All files under project root.

### Root

| File | Purpose |
|------|---------|
| `main.py` | Entry point: init config, logger, DB, scheduler, Telegram bot, graceful shutdown |
| `requirements.txt` | Pinned dependencies |
| `.env.example` | Template for API keys, Telegram token, capital, thresholds |
| `.gitignore` | Python, .env, SQLite, logs, IDE files, model weights |
| `setup_models.py` | One-time script: download FinBERT + GPT-2B weights, create LSTM/XGBoost placeholders |

### `core/` — Shared Infrastructure

| File | Purpose |
|------|---------|
| `core/__init__.py` | Package |
| `core/types.py` | **All inter-agent data contracts** as frozen dataclasses — the ONLY module that every agent imports. No agent imports another agent's types. |
| `core/config.py` | Loads `.env` via python-dotenv, exposes `AppConfig` dataclass (API keys, risk params, model paths, intervals, capital) |
| `core/logger.py` | Rotating file handler + console via `get_logger(name)` factory |
| `core/scheduler.py` | APScheduler wrapper with per-timeframe job scheduling. Orchestrates full pipeline. |

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

### `models/` — ML Model Management

| File | Purpose |
|------|---------|
| `models/__init__.py` | Package |
| `models/finbert.py` | **FinBERT wrapper**: loads `ProsusAI/finbert` via transformers, classifies financial text as Bullish/Bearish/Neutral with confidence. Batch inference support. CPU/GPU auto-detection. |
| `models/lstm_model.py` | **LSTM wrapper**: PyTorch LSTM for price direction prediction. Accepts OHLC + indicator features. Returns predicted direction, volatility, trend strength. Includes training and inference modes. |
| `models/xgboost_model.py` | **XGBoost wrapper**: trained model combining all features (indicators, patterns, sentiment, LSTM prediction, volatility) into a single probability score. Includes training, inference, and feature engineering. |
| `models/gpt2_reasoning.py` | **GPT-2B wrapper**: local transformer for generating trade explanations from structured signal data. Prompt template formats indicator + sentiment + probability context. |
| `models/model_manager.py` | **Model lifecycle**: lazy loading, device selection (CPU/CUDA/MPS), model caching, memory management (unload between cycles if low RAM). |

### `agents/` — Intelligence Agents

| File | Purpose |
|------|---------|
| `agents/__init__.py` | Package |
| `agents/chart_agent.py` | Multi-timeframe orchestrator: runs indicators + patterns on 5m/15m/1h/4h, selects best timeframe by clarity score. |
| `agents/sentiment_agent.py` | **FinBERT integration**: wraps `models/finbert.py`. Classifies news headlines, returns per-headline and aggregate sentiment. No external API dependency. |
| `agents/news_agent.py` | Wraps `news_data.py` + `sentiment_agent.py`. Checks news blackout (Fed, NFP, CPI) via keyword matching on collected headlines. Returns `{news_items, sentiments, macro_score, is_blackout}`. |
| `agents/prediction_agent.py` | **LSTM integration**: wraps `models/lstm_model.py`. Prepares features from OHLC + indicators, returns predicted direction and confidence. |
| `agents/signal_agent.py` | **XGBoost integration**: wraps `models/xgboost_model.py`. Assembles feature vector from all agents, gets probability from XGBoost, generates explanation via GPT-2B if threshold met. |
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
| `backtesting/strategy.py` | Wraps XGBoost model into vectorbt-compatible strategy. Supports parameter sweeps and walk-forward optimization. |

### `tests/`

| File | Purpose |
|------|---------|
| `tests/__init__.py` | Package |
| `tests/conftest.py` | Shared fixtures: sample OHLC data, test config, in-memory SQLite, mock providers |
| `tests/test_indicators.py` | Unit tests for all indicator computations against known values |
| `tests/test_patterns.py` | Unit tests for pattern detection with synthetic candle data |
| `tests/test_finbert.py` | FinBERT sentiment classification tests with known financial text |
| `tests/test_lstm.py` | LSTM prediction tests with synthetic time series |
| `tests/test_xgboost.py` | XGBoost probability model tests with known feature vectors |
| `tests/test_signal_scoring.py` | End-to-end signal agent tests: features in -> probability + reasoning out |
| `tests/test_risk_agent.py` | All risk rules, kill switch, position limits, edge cases |
| `tests/test_sentiment.py` | Sentiment agent tests with mocked FinBERT responses |
| `tests/test_database.py` | DB operations and metric calculations |
| `tests/test_integration.py` | End-to-end: synthetic market data through full pipeline to final signal |

---

## Core Data Contracts (`core/types.py`)

All inter-agent communication uses these frozen dataclasses. No agent imports types from another agent.

```python
OHLCBar: timestamp, open, high, low, close, volume
IndicatorResult: rsi, macd_line, macd_signal, macd_hist, ema_20, ema_50, ema_200,
                 bb_upper, bb_middle, bb_lower, atr, support, resistance, trend_direction,
                 breakout_probability
PatternResult: pattern_name, direction (+1/-1), confidence (0.0-1.0), description
NewsItem: source, headline, url, published_at, raw_text
SentimentResult: classification (Bullish/Bearish/Neutral), confidence, reasoning
LSTMPrediction: predicted_direction (+1/-1/0), predicted_volatility, trend_strength, confidence
TradeSignal: asset, direction (BUY/SELL/NO_TRADE), entry_price, stop_loss, take_profit,
             probability, reasoning, timestamp, timeframe
RiskVerdict: approved (bool), position_size, rejection_reason, daily_risk_used, open_positions
FinalSignal: signal (TradeSignal), risk (RiskVerdict), formatted_message
AccountState: capital, open_positions, daily_pnl, kill_switch_active, updated_at
```

---

## Signal Scoring — XGBoost Model

### Previous Approach (v1.x plan)

The original plan used a hand-tuned weighted formula with sigmoid mapping.
This is replaced by a trained XGBoost model per constitution v1.1.

### New Approach — XGBoost Probability Model

XGBoost receives a structured feature vector and outputs a probability.

#### Feature Vector (input to XGBoost)

| Feature Group | Features | Source |
|--------------|----------|--------|
| Technical Indicators | RSI, MACD line/signal/hist, EMA 20/50/200, BB upper/middle/lower, ATR | `analysis/indicators.py` |
| Derived Technical | EMA alignment score, BB squeeze ratio, ATR volatility ratio, support/resistance distance | `analysis/indicators.py` |
| Pattern Detection | Pattern direction, confidence (per pattern type) | `analysis/pattern_detection.py` |
| Sentiment | FinBERT macro score, sentiment confidence, headline count | `agents/sentiment_agent.py` |
| LSTM Prediction | Predicted direction, predicted volatility, trend strength, LSTM confidence | `agents/prediction_agent.py` |
| Volatility | Current ATR / 20-period avg ATR, BB width | Computed from indicators |

Total: ~25-35 features.

#### Training Pipeline

```
Historical OHLC data (CSV)
  → compute indicators + patterns
  → compute LSTM predictions
  → label: future price movement (up/down/flat over N candles)
  → train XGBoost classifier
  → save model to models/weights/xgboost_model.json
```

Training uses walk-forward cross-validation to prevent look-ahead bias.

#### Inference

```python
features = assemble_feature_vector(indicators, patterns, sentiment, lstm_pred, volatility)
probability = xgboost_model.predict_proba(features)  # P(BUY) or P(SELL)

if probability >= 0.68:
    direction = "BUY" if buy_prob > sell_prob else "SELL"
    reasoning = gpt2_model.generate_explanation(features, direction, probability)
    signal = TradeSignal(direction=direction, probability=probability, reasoning=reasoning, ...)
else:
    direction = "NO_TRADE"
```

#### Fallback

If XGBoost model is not yet trained (early development), fall back to the
weighted formula from the original plan. This ensures Phase 1 can operate
without trained models.

### Weighted Formula Fallback

```python
raw_score = (0.40 * technical_score +
             0.20 * pattern_score +
             0.25 * sentiment_score +
             0.15 * trend_strength)

adjusted = raw_score * volatility_factor
probability = 1.0 / (1.0 + math.exp(-4.0 * adjusted))

# ONLY generate signal if probability >= 0.68
```

This fallback is used during Phase 1 and Phase 2 before XGBoost is trained.

---

## LSTM Time Series Model

### Architecture

```
Input: [OHLC + indicators] × N candles (lookback window)
  → Feature normalization (StandardScaler)
  → LSTM layers (2 layers, 64 hidden units)
  → Fully connected output
  → Predicted direction (+1 BUY / -1 SELL / 0 FLAT)
  → Predicted volatility (normalized ATR)
  → Trend strength (0.0-1.0)
```

### Training

```
Historical data → sliding window sequences → train/val split (80/20, time-ordered)
Loss: CrossEntropyLoss for direction + MSELoss for volatility
Optimizer: Adam, lr=0.001
Epochs: 50-100 with early stopping
```

Model weights saved to `models/weights/lstm_model.pt`.

### Prediction Horizon

5–30 candles ahead (configurable per timeframe).

---

## FinBERT Sentiment Model

### Usage

```python
from transformers import AutoTokenizer, AutoModelForSequenceClassification

model = AutoModelForSequenceClassification.from_pretrained("ProsusAI/finbert")
tokenizer = AutoTokenizer.from_pretrained("ProsusAI/finbert")

# Input: financial headline text
# Output: {positive, negative, neutral} probabilities
# Mapped to: Bullish (positive), Bearish (negative), Neutral
```

### Aggregation

```python
macro_score = mean(
    sentiment_direction * confidence
    for headline in recent_headlines
)
# sentiment_direction: +1 (Bullish), -1 (Bearish), 0 (Neutral)
# macro_score range: [-1.0, +1.0]
```

---

## GPT-2B Reasoning Model

### Purpose

Generate human-readable trade explanations. NOT used for prediction.

### Prompt Template

```
Given the following market analysis for {asset}:
- Technical: RSI={rsi}, MACD={macd_status}, Trend={trend}
- Sentiment: {sentiment} (confidence: {confidence})
- ML Prediction: {direction} with {probability}% confidence

Explain why this is a {direction} signal in 2-3 sentences.
```

### Model Options (local, ranked by size)

1. `gpt2` (124M) — fastest, minimal RAM
2. `gpt2-medium` (355M) — better quality
3. `gpt2-large` (774M) — good quality, ~3 GB RAM
4. `microsoft/phi-2` (2.7B) — best quality, ~6 GB RAM

Default: `gpt2-medium` (balance of quality and resource usage).

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
    lstm_prediction REAL,
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
models/model_manager.py    <-- config, logger
models/finbert.py          <-- model_manager, types
models/lstm_model.py       <-- model_manager, types
models/xgboost_model.py    <-- model_manager, types
models/gpt2_reasoning.py   <-- model_manager, types
storage/database.py        <-- types, config
data/market_data.py        <-- types, config, logger
data/news_data.py          <-- types, config, logger
data/csv_loader.py         <-- types
analysis/indicators.py     <-- types
analysis/pattern_detection.py <-- types
agents/chart_agent.py      <-- market_data, indicators, pattern_detection, types
agents/sentiment_agent.py  <-- finbert, types
agents/prediction_agent.py <-- lstm_model, types
agents/news_agent.py       <-- news_data, sentiment_agent, types
agents/signal_agent.py     <-- xgboost_model, gpt2_reasoning, types, config
agents/risk_agent.py       <-- types, config, database
execution/signal_generator.py <-- types
execution/telegram_bot.py  <-- types, config, database
core/scheduler.py          <-- ALL agents, database (orchestrator)
main.py                    <-- config, scheduler, telegram_bot, database, logger
```

Direction: `main -> scheduler -> agents -> models/data/analysis -> core/types`. No cycles.

---

## Configuration (`core/config.py`)

All magic numbers live here. Agents receive config via constructor injection.

```python
@dataclass
class AppConfig:
    # API Keys (all optional — system degrades gracefully)
    market_data_provider: str    # "twelvedata" | "alphavantage" | "polygon"
    market_data_api_key: str
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

    # Risk parameters
    initial_capital: float       # from .env, no default
    max_risk_per_trade: float = 0.01
    max_daily_risk: float = 0.03
    max_open_positions: int = 2
    kill_switch_threshold: float = 0.05
    sl_atr_multiplier: float = 1.5
    tp_atr_multiplier: float = 3.0
    min_risk_reward: float = 1.8

    # ML Model paths
    finbert_model: str = "ProsusAI/finbert"
    lstm_model_path: str = "models/weights/lstm_model.pt"
    xgboost_model_path: str = "models/weights/xgboost_model.json"
    gpt2_model: str = "gpt2-medium"
    model_device: str = "auto"   # "auto" | "cpu" | "cuda" | "mps"

    # Infrastructure
    db_path: str = "storage/trading.db"
    log_level: str = "INFO"
    log_file: str = "logs/trading.log"
    csv_data_dir: str = "data/historical/"
```

---

## Development Phases

### Phase 1 — Core System + Risk ✅ COMPLETED

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

### Phase 2 — Sentiment Intelligence (FinBERT)

**Goal**: RSS news collection + FinBERT local sentiment scoring + news blackout

**Constitution alignment**: FinBERT replaces the generic LLM abstraction. Runs locally, no external API needed for inference.

1. `models/__init__.py`, `models/model_manager.py` — model lifecycle (device detection, lazy loading, memory management)
2. `models/finbert.py` — load `ProsusAI/finbert` via transformers, batch inference, CPU/GPU auto-detect
3. `data/news_data.py` — RSS feed collector via feedparser, keyword filtering, dedup
4. `agents/sentiment_agent.py` — wraps FinBERT model, per-headline and aggregate scoring
5. `agents/news_agent.py` — orchestration: collect news → classify sentiment → detect blackout → return macro score
6. Update `storage/database.py` — news table operations (schema already exists from Phase 1)
7. `setup_models.py` — download FinBERT weights on first run

Tests: `tests/test_finbert.py`, `tests/test_sentiment.py`

New dependencies: `torch`, `transformers`

**Phase 2 delivers**: Local FinBERT sentiment analysis on financial news, blackout detection active. No external API costs for sentiment.

### Phase 3 — AI Decision Engine (LSTM + XGBoost + GPT-2B)

**Goal**: Full probability-based signal generation with ML models

**Constitution alignment**: XGBoost combines all features into probability. LSTM provides time series prediction. GPT-2B generates explanations.

1. `analysis/pattern_detection.py` — 6 rule-based pattern detectors (breakout, triangle, double top/bottom, head & shoulders, range)
2. `agents/chart_agent.py` — multi-timeframe analysis + timeframe selection by clarity score
3. `models/lstm_model.py` — LSTM architecture, training loop, inference, feature preparation
4. `agents/prediction_agent.py` — wraps LSTM, prepares OHLC + indicator features, returns prediction
5. `models/xgboost_model.py` — feature engineering, training pipeline (walk-forward CV), inference
6. `models/gpt2_reasoning.py` — load GPT-2 variant, prompt template, generate explanation text
7. `agents/signal_agent.py` — assemble feature vector → XGBoost probability → GPT-2B reasoning if threshold met
8. Update `core/scheduler.py` — full pipeline: chart_agent → news_agent → prediction_agent → signal_agent → risk_agent → delivery
9. Training scripts for LSTM and XGBoost using historical CSV data

Tests: `tests/test_patterns.py`, `tests/test_lstm.py`, `tests/test_xgboost.py`, `tests/test_signal_scoring.py`

New dependencies: `scikit-learn`, `xgboost`

**Phase 3 delivers**: Complete autonomous signal generation. XGBoost probability scoring, LSTM predictions, GPT-2B explanations. Falls back to weighted formula if models not yet trained.

### Phase 4 — Backtesting Engine

**Goal**: Historical validation + strategy optimization

1. `data/csv_loader.py` — CSV parser for MT4/TradingView/generic formats
2. `backtesting/__init__.py`, `backtesting/strategy.py` — vectorbt-compatible strategy wrapper using XGBoost model
3. `backtesting/backtester.py` — bar-by-bar replay through full pipeline, metrics output
4. Walk-forward optimization for XGBoost hyperparameters

New dependencies: `vectorbt`

**Phase 4 delivers**: Ability to evaluate signal quality on 1+ years of historical data. Results inform model retraining.

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
5. Per-asset model instances (XGBoost trained per asset)

**Phase 6 delivers**: System monitoring up to 10 assets with independent signal generation and risk tracking per asset.

---

## Per-Timeframe Scheduling

Instead of a single 5-minute loop, the scheduler runs independent jobs:

| Timeframe | Interval | What runs |
|-----------|----------|-----------|
| 5min | Every 5 minutes | Full pipeline: data → indicators → patterns → LSTM → sentiment → XGBoost → risk → delivery |
| 15min | Every 15 minutes | Same pipeline, 15min candles |
| 1h | Every 60 minutes | Same pipeline, 1h candles |
| 4h | Every 240 minutes | Same pipeline, 4h candles |

The Signal Decision Agent receives results from all recently-run timeframes and uses the best timeframe to generate a signal. A signal is only generated when the XGBoost probability crosses the 0.68 threshold.

---

## Technology Stack

| Category | Choice |
|----------|--------|
| Language | Python 3.11 |
| Data | pandas, numpy |
| Indicators | ta (technical analysis library) |
| ML - Gradient Boosting | scikit-learn, xgboost |
| ML - Deep Learning | torch, transformers (FinBERT, LSTM, GPT-2B) |
| HTTP | requests |
| RSS | feedparser |
| Scheduling | APScheduler |
| Telegram | python-telegram-bot |
| Backtesting | vectorbt |
| Storage | SQLite (stdlib sqlite3) |
| Config | python-dotenv |
| Testing | pytest, pytest-asyncio |

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

4. LSTM Prediction Agent predicts:
   - Direction: +1 (BUY), confidence: 0.72
   - Volatility: moderate
   - Trend strength: 0.80

5. News Agent collects RSS headlines, FinBERT classifies:
   - "FED signals rate cuts" -> Bullish, confidence 0.82
   - "Gold demand rises in Asia" -> Bullish, confidence 0.75
   - macro_score: +0.60

6. Signal Decision Agent (XGBoost) scores:
   - Feature vector assembled: [RSI=63, MACD=+, EMA_aligned=1, ...]
   - XGBoost probability: 0.89 (BUY)
   - Exceeds threshold (0.68) -> generate signal

7. GPT-2B generates explanation:
   "Gold shows bullish momentum with MACD crossover and aligned EMAs.
    FinBERT detects positive macro sentiment from Fed rate cut signals.
    LSTM confirms upward trend. Breakout above 2350 resistance adds confidence."

8. Risk Management Agent checks:
   - Daily risk used: 0% (first trade) -> OK
   - Open positions: 0 -> OK
   - Kill switch: inactive -> OK
   - News blackout: none -> OK
   - SL = 2335 - 1.5 * 10 = 2320
   - TP = 2335 + 3.0 * 10 = 2365
   - Position size = (0.01 * capital) / 15 = ...
   - APPROVED

9. Signal Generator formats message:

   🟢 GOLD SIGNAL
   Asset: XAU/USD
   Direction: BUY
   Entry: 2335
   Stop Loss: 2320
   Take Profit: 2365
   Confidence: 89%
   Reason: Bullish breakout + positive macro sentiment + LSTM confirmation

10. Telegram Bot sends to channel
11. Performance Tracker logs signal to SQLite
```

---

## Model Setup Procedure

First-time setup (run once after install):

```bash
python setup_models.py
```

This script:
1. Downloads FinBERT weights from HuggingFace (`ProsusAI/finbert`)
2. Downloads GPT-2 variant weights (default: `gpt2-medium`)
3. Creates empty LSTM and XGBoost model directories
4. Verifies torch installation (CPU or CUDA)

LSTM and XGBoost models require training on historical data:

```bash
# After loading historical CSV data:
python -m models.lstm_model --train --data data/historical/xauusd_1h.csv
python -m models.xgboost_model --train --data data/historical/xauusd_1h.csv
```

---

## Future Features (post Phase 6)

- Reinforcement learning for strategy optimization
- Portfolio optimization for multi-asset allocation
- Semi-automatic trading via broker API integration
- Cloud deployment (Docker + scheduling service)
- CNN-based pattern detection on chart images
- Economic calendar API for smarter news blackout
- Model retraining automation on new data

---

## Verification Plan

| Phase | How to verify |
|-------|--------------|
| Phase 1 | `python main.py` -> Telegram receives indicator summaries; risk agent rejects signals missing SL/TP |
| Phase 2 | RSS feeds collected, FinBERT sentiment scores appear in news table; news blackout triggers |
| Phase 3 | Signals include XGBoost probability; GPT-2B reasoning in messages; NO_TRADE when below 0.68 |
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

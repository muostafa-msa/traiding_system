# traiding_system Development Guidelines

Auto-generated from all feature plans. Last updated: 2026-04-06

## Active Technologies
- Python 3.12 + torch (>=2.0), transformers (>=4.30), feedparser (6.0.11, already installed) (002-finbert-sentiment)
- SQLite (existing — add `content_hash` column to news table, `blackout_until` to account_state) (002-finbert-sentiment)
- Python 3.12 + torch (>=2.0), transformers (>=4.30), scikit-learn, xgboost, pandas, numpy, ta (003-ai-decision-engine)
- SQLite (existing — `storage/database.py`) (003-ai-decision-engine)
- Python 3.12 (matching existing codebase) + pandas (CSV parsing), numpy (metrics), existing pipeline agents (ChartAgent, SignalAgent, PredictionAgent, RiskAgent), existing models (LSTM, XGBoost), vectorbt (optional strategy wrapper) (004-backtesting-engine)
- SQLite (existing `storage/database.py` — extend with backtest tables) (004-backtesting-engine)
- Python 3.12 (matching existing codebase) + python-telegram-bot (existing), sqlite3 (stdlib), math (stdlib) (005-telegram-performance)
- SQLite (existing `storage/database.py` — read-only queries, no schema changes) (005-telegram-performance)

- Python 3.11 + pandas, numpy, ta, requests, python-dotenv, apscheduler, python-telegram-bot, feedparser (Phase 1: core-system-risk)
- torch, transformers (Phase 2: FinBERT sentiment)
- scikit-learn, xgboost (Phase 3: LSTM + XGBoost decision engine)
- vectorbt (Phase 4: backtesting)

## Project Structure

```text
core/          # Shared infrastructure (types, config, logger, scheduler)
data/          # Data collection (market data providers, news RSS, CSV loader)
analysis/      # Technical analysis (indicators, pattern detection)
models/        # ML models (FinBERT, LSTM, XGBoost) + Ollama integration (GPT-OSS-20B)
agents/        # Intelligence agents (chart, sentiment, prediction, signal, risk)
execution/     # Signal delivery (formatter, Telegram bot)
storage/       # Persistence (SQLite database)
backtesting/   # Historical testing (vectorbt strategy wrapper)
tests/         # Test suite
```

## Commands

```bash
pytest tests/ -v          # Run test suite
ruff check .              # Lint
python main.py            # Run the system
python setup_models.py    # Download ML model weights (one-time)
```

## Code Style

Python 3.11: Follow standard conventions

## Architecture

- All inter-agent data flows through frozen dataclasses in `core/types.py`
- No circular dependencies between packages
- Local-first: all ML models run locally (CPU default, optional GPU)
- GPT-OSS-20B served via Ollama (`ollama run gpt-oss:20b`) — explanation generation uses Ollama HTTP API
- External APIs only for market data (TwelveData/AlphaVantage/Polygon), news (RSS), and Ollama (localhost)

## ML Models (constitution v1.1)

- **FinBERT** (`ProsusAI/finbert`) — financial sentiment classification
- **LSTM** (custom PyTorch) — time series prediction
- **XGBoost** — signal probability scoring
- **GPT-OSS-20B** (`openai/gpt-oss-20b` via Ollama) — trade reasoning/explanation

## Recent Changes
- 005-telegram-performance: Added Python 3.12 (matching existing codebase) + python-telegram-bot (existing), sqlite3 (stdlib), math (stdlib)
- 004-backtesting-engine: Added Python 3.12 (matching existing codebase) + pandas (CSV parsing), numpy (metrics), existing pipeline agents (ChartAgent, SignalAgent, PredictionAgent, RiskAgent), existing models (LSTM, XGBoost), vectorbt (optional strategy wrapper)
- 003-ai-decision-engine: Added Python 3.12 + torch (>=2.0), transformers (>=4.30), scikit-learn, xgboost, pandas, numpy, ta


<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->

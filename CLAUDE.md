# traiding_system Development Guidelines

Auto-generated from all feature plans. Last updated: 2026-03-28

## Active Technologies

- Python 3.11 + pandas, numpy, ta, requests, python-dotenv, apscheduler, python-telegram-bot, feedparser (Phase 1: core-system-risk)
- torch, transformers (Phase 2: FinBERT sentiment)
- scikit-learn, xgboost (Phase 3: LSTM + XGBoost decision engine)
- vectorbt (Phase 4: backtesting)

## Project Structure

```text
core/          # Shared infrastructure (types, config, logger, scheduler)
data/          # Data collection (market data providers, news RSS, CSV loader)
analysis/      # Technical analysis (indicators, pattern detection)
models/        # ML models (FinBERT, LSTM, XGBoost, GPT-2B)
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
- External APIs only for market data (TwelveData/AlphaVantage/Polygon) and news (RSS)

## ML Models (constitution v1.1)

- **FinBERT** (`ProsusAI/finbert`) — financial sentiment classification
- **LSTM** (custom PyTorch) — time series prediction
- **XGBoost** — signal probability scoring
- **GPT-2B OSS** (`gpt2-medium`) — trade reasoning/explanation

## Recent Changes

- 001-core-system-risk Phase 1: Core infrastructure, types, config, logger (COMPLETED)
- Constitution updated to v1.1: Added FinBERT, LSTM, XGBoost, GPT-2B, local-first architecture

<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->

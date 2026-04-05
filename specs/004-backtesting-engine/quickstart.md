# Quickstart: Backtesting Engine

**Feature**: 004-backtesting-engine | **Date**: 2026-04-05

## Prerequisites

- Python 3.12 with existing project dependencies installed
- Trading system codebase with Phases 1-3 completed (core, sentiment, decision engine)
- Historical OHLCV data in CSV format (MT4, TradingView, or generic)

## New Dependencies

```bash
pip install vectorbt  # Optional: for future vectorized strategy wrappers
```

No other new dependencies required — the backtesting engine reuses existing pandas, numpy, and ML libraries.

## Quick Run

### 1. Basic Backtest

```bash
python -m backtesting.cli data/historical/xauusd_1h.csv
```

This loads the CSV, replays ~6,500 bars through the trading pipeline, and prints a performance report.

### 2. Walk-Forward Optimization

```bash
python -m backtesting.cli data/historical/xauusd_1h.csv --walk-forward
```

Splits data into 3-month train / 1-month test windows, retrains XGBoost per window, and reports out-of-sample metrics.

### 3. Custom Parameters

```bash
python -m backtesting.cli data/xau_4h.csv \
  --capital 50000 \
  --timeframe 4h \
  --sentiment-score 0.2 \
  --verbose
```

## CSV Data Format

The system auto-detects three formats:

**Generic OHLCV** (recommended):
```csv
datetime,open,high,low,close,volume
2025-01-02 09:00:00,2635.50,2638.20,2633.10,2637.80,1250
```

**MetaTrader 4**:
```csv
<DATE>,<TIME>,<OPEN>,<HIGH>,<LOW>,<CLOSE>,<VOL>
2025.01.02,09:00,2635.50,2638.20,2633.10,2637.80,1250
```

**TradingView**:
```csv
time,open,high,low,close,Volume
2025-01-02T09:00:00Z,2635.50,2638.20,2633.10,2637.80,1250
```

## Key Design Decisions

- **Sentiment**: Uses neutral placeholder (score=0.0) since historical news is unavailable. Override with `--sentiment-score`.
- **Intra-bar exits**: Pessimistic — when both SL and TP are hit in one bar, SL is assumed.
- **Risk rules**: Identical to live system (1% per trade, 3% daily, 2 max positions, RR >= 1.8).
- **Results**: Printed to terminal AND saved to SQLite database for comparison.

## Development

### Running Tests

```bash
pytest tests/test_csv_loader.py tests/test_backtest_engine.py tests/test_metrics.py tests/test_walk_forward.py -v
```

### Module Structure

```
backtesting/
├── __init__.py          # Package init
├── engine.py            # Core replay engine
├── metrics.py           # Performance calculations
├── walk_forward.py      # Walk-forward optimizer
└── cli.py               # CLI entry point

data/
└── csv_loader.py        # CSV parsing (auto-detect + validation)
```

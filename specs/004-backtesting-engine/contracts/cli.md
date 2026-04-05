# CLI Contract: Backtesting Engine

**Feature**: 004-backtesting-engine | **Date**: 2026-04-05

## Command: `python -m backtesting.cli`

### Synopsis

```
python -m backtesting.cli <csv_file> [options]
python -m backtesting.cli --walk-forward <csv_file> [options]
```

### Arguments

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `csv_file` | Yes | — | Path to CSV file with historical OHLCV data |

### Options

| Option | Short | Type | Default | Description |
|--------|-------|------|---------|-------------|
| `--capital` | `-c` | float | 10000.0 | Initial trading capital in USD |
| `--timeframe` | `-t` | string | 1h | Bar timeframe: 5min, 15min, 1h, 4h |
| `--sentiment-score` | `-s` | float | 0.0 | Placeholder sentiment score [-1.0, 1.0] |
| `--walk-forward` | `-w` | flag | false | Enable walk-forward optimization |
| `--train-months` | | int | 3 | Training window size (walk-forward only) |
| `--test-months` | | int | 1 | Testing window size (walk-forward only) |
| `--verbose` | `-v` | flag | false | Show per-trade details during replay |

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Backtest completed successfully |
| 1 | Invalid arguments or missing CSV file |
| 2 | CSV parsing error (format unrecognized or too few valid rows) |
| 3 | Insufficient data (fewer than 200 bars after validation) |
| 4 | Model loading error (non-fatal warning printed, falls back to fallback scoring) |

### Output Format

#### Standard Backtest (stdout)

```
═══════════════════════════════════════════
  BACKTEST RESULTS: XAU/USD (1h)
  Period: 2025-01-01 → 2025-12-31
═══════════════════════════════════════════

  Initial Capital:    $10,000.00
  Final Capital:      $11,245.30
  Total Return:       +12.45%

  Total Trades:       47
  Wins:               28 (59.6%)
  Losses:             19 (40.4%)

  Profit Factor:      1.82
  Sharpe Ratio:       1.34
  Max Drawdown:       -4.2%
  Avg Reward/Risk:    2.1

  Rejected Signals:   12
  Scoring Method:     fallback

  Run ID: 5 (saved to database)
═══════════════════════════════════════════
```

#### Walk-Forward Output (stdout)

```
═══════════════════════════════════════════
  WALK-FORWARD OPTIMIZATION: XAU/USD (1h)
  Windows: 9 (3-month train / 1-month test)
═══════════════════════════════════════════

  Window  Train Period          Test Period          OOS Return  OOS Win Rate
  ──────  ────────────────────  ────────────────────  ──────────  ────────────
  1       2025-01 → 2025-03    2025-04               +3.2%       62.5%
  2       2025-02 → 2025-04    2025-05               +1.1%       55.0%
  ...
  9       2025-09 → 2025-11    2025-12               -0.8%       45.0%

  Aggregate OOS Return:    +8.7%
  Aggregate OOS Win Rate:  56.2%
  IS vs OOS Divergence:    12.3% (moderate overfitting risk)

  Run ID: 6 (saved to database)
═══════════════════════════════════════════
```

#### Verbose Mode (additional per-trade output)

```
  [BAR 1234] BUY @ 2345.50 | SL: 2330.20 | TP: 2368.35 | Prob: 0.72
  [BAR 1267] CLOSED:take_profit @ 2368.35 | P&L: +$152.30 (+1.5%)
```

### Examples

```bash
# Basic backtest with defaults
python -m backtesting.cli data/historical/xauusd_1h.csv

# Custom capital and timeframe
python -m backtesting.cli data/xau_5min.csv --capital 50000 --timeframe 5min

# Walk-forward optimization
python -m backtesting.cli data/xauusd_1h.csv --walk-forward --train-months 3 --test-months 1

# Verbose output with sentiment override
python -m backtesting.cli data/xauusd_1h.csv --sentiment-score 0.3 --verbose
```

### Error Messages

| Scenario | Message |
|----------|---------|
| File not found | `Error: CSV file not found: {path}` |
| Unrecognized format | `Error: Cannot detect CSV format. Expected MT4, TradingView, or generic OHLCV headers.` |
| Too few bars | `Error: Only {n} valid bars found. Minimum 200 required for backtesting.` |
| Walk-forward data insufficient | `Error: {n} months of data found. Walk-forward requires at least {min} months (2 full train+test windows).` |
| Model not found | `Warning: {model} model not found at {path}. Using fallback scoring method.` |

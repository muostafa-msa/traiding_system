# Quickstart: Signal Quality Filtering Improvements

**Feature**: 006-signal-quality-filters
**Date**: 2026-04-07

## Prerequisites

- Python 3.12, all existing dependencies installed
- `.env` configured with Telegram bot token + chat ID
- Existing test suite passes: `pytest tests/ -v`

## Implementation Order

Each phase is independently deployable and testable:

1. **Stop indicator broadcasts** -- `scheduler.py` (1 line removed)
2. **Filter contradictory patterns** -- `pattern_detection.py` (new function)
3. **Prediction agreement gate** -- `config.py`, `signal_agent.py`
4. **Entry vs S/R warning** -- `scheduler.py` (new log method)
5. **Multi-timeframe confirmation** -- `config.py`, `chart_agent.py`, `scheduler.py`
6. **Opportunity score gate** -- `config.py`, `types.py`, `signal_agent.py`
7. **Improved Telegram format** -- `signal_generator.py`, `scheduler.py`

## Quick Verification

### Phase 1 (Telegram Noise)
```bash
# Run system, check logs for indicator summaries (should still appear)
grep "Indicator summary" logs/trading.log
# Check Telegram -- should receive zero indicator analysis messages
# Trade signals should still come through
```

### Phase 2 (Pattern Filtering)
```bash
pytest tests/test_patterns.py -v -k "contradictory"
```

### Phase 3 (Prediction Agreement)
```bash
pytest tests/test_signal_agent.py -v -k "prediction_agreement"
```

### Phase 4 (S/R Warning)
```bash
# Check logs after a signal is generated
grep "entry.*support\|entry.*resistance" logs/trading.log
```

### Phase 5 (MTF Confirmation)
```bash
pytest tests/ -v -k "mtf"
```

### Phase 6 (Opportunity Score)
```bash
pytest tests/test_signal_agent.py -v -k "opportunity_score"
```

### Phase 7 (Message Format)
```bash
# Generate a signal and verify Telegram message contains:
# - R:R ratio
# - SL/TP distances
# - Position in oz with dollar risk
# - Market context (trend, pattern, RSI, MACD)
# - AI Analysis section
```

## Full System Verification

```bash
# All tests pass
pytest tests/ -v

# Run system
python main.py

# Verify in Telegram:
# 1. No indicator summary messages
# 2. Only approved trade signals appear
# 3. Signal messages have new format with R:R, context
# 4. /status, /performance, /last_signal commands still work
```

## Configuration

All new features are enabled by default. To disable any gate:

```env
# .env
PREDICTION_AGREEMENT_ENABLED=false
MTF_CONFIRMATION_ENABLED=false
OPPORTUNITY_SCORE_ENABLED=false
OPPORTUNITY_SCORE_THRESHOLD=0.55
MTF_MIN_AGREEING_TIMEFRAMES=2
```

## Test Scenarios

| Scenario | Expected |
|----------|----------|
| Normal cycle, no signal | Zero Telegram messages |
| Signal with LSTM disagreement | Rejected (prediction agreement) |
| Signal with only 1 TF agreeing | Rejected (MTF confirmation) |
| Signal with low opportunity score | Rejected (score < 0.55) |
| All gates pass | Signal broadcast in new format |
| All gates disabled | Identical to pre-feature behavior |
| Cold start (1 TF analyzed) | Signal allowed through (graceful degradation) |
| All patterns NEUTRAL | No pattern filtering |
| SELL entry < support | Warning logged, signal proceeds |

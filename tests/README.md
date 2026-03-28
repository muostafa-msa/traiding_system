# Test Suite

## Running Tests

```bash
pytest tests/ -v
```

## Test Files

| File | Tests | Purpose |
|------|-------|---------|
| test_database.py | 25 | SQLite CRUD, account state, performance |
| test_indicators.py | 20 | RSI, MACD, EMA, BB, ATR, S/R, trend, breakout |
| test_risk_agent.py | 12 | Risk rules, kill switch, position sizing |
| test_telegram.py | 14 | Chat ID restriction, commands, no-op mode |
| test_integration.py | 6 | Full pipeline, performance, OHLC validation |

## Manual 24-Hour Stability Test (SC-006)

This procedure validates that the system runs continuously without crashes, memory leaks, or missed cycles.

### Prerequisites

- A valid market data API key configured in `.env`
- System time synchronized (NTP)

### Procedure

1. Start the system:

   ```bash
   python main.py 2>&1 | tee logs/stability_test.log
   ```

2. Monitor for 24 hours. Check the following:

   - **No crashes**: The process should remain running for the full 24 hours
   - **No memory leaks**: Check RSS memory at start and end:

     ```bash
     # At start
     ps -o rss= -p $(pgrep -f main.py)
     # At end (should not exceed 2x start value)
     ps -o rss= -p $(pgrep -f main.py)
     ```

   - **No missed cycles**: Count scheduled jobs vs completed jobs:

     ```bash
     # Expected cycles in 24h: 288 (5min) + 96 (15min) + 24 (1h) + 6 (4h) = 414
     grep "Cycle complete" logs/stability_test.log | wc -l
     ```

   - **No cycle overlaps**: Check for overlap warnings:

     ```bash
     grep "overlap" logs/stability_test.log | wc -l
     ```

3. Verify database integrity after 24h:

   ```bash
   sqlite3 storage/trading.db "SELECT COUNT(*) FROM signals;"
   sqlite3 storage/trading.db "SELECT COUNT(*) FROM trades;"
   sqlite3 storage/trading.db "SELECT * FROM account_state;"
   ```

### Pass Criteria

- System runs continuously for 24 hours without crashing
- Memory usage does not grow beyond 2x initial RSS
- At least 95% of expected cycles complete successfully
- No data corruption in SQLite database
- Daily reset occurs at UTC midnight without errors

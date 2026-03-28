# Quickstart: Core System + Risk Management

**Feature**: `001-core-system-risk`

## Prerequisites

- Python 3.11+
- A market data provider API key (TwelveData recommended for XAU/USD)
- (Optional) A Telegram bot token and chat ID

## Setup

1. Clone and enter the project:
   ```bash
   cd traiding_system
   ```

2. Create a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Copy and configure environment:
   ```bash
   cp .env.example .env
   ```

5. Edit `.env` with your values:
   ```
   MARKET_DATA_PROVIDER=twelvedata
   MARKET_DATA_API_KEY=your_key_here
   INITIAL_CAPITAL=10000

   # Optional - system works without these
   TELEGRAM_BOT_TOKEN=your_bot_token
   TELEGRAM_CHAT_ID=your_chat_id
   ```

## Run

```bash
python main.py
```

The system will:
1. Fetch 250 historical candles for XAU/USD (startup)
2. Compute all technical indicators
3. Send an indicator summary to Telegram (if configured)
4. Repeat on schedule (5min/15min/1h/4h intervals)

## Verify

- **With Telegram**: Check your Telegram channel for indicator summary messages
- **Without Telegram**: Check `logs/trading.log` for formatted messages
- **Database**: Query `storage/trading.db` to verify signal records

```bash
sqlite3 storage/trading.db "SELECT * FROM signals ORDER BY created_at DESC LIMIT 5;"
```

## Telegram Commands

Send these to your bot (only works from the configured chat ID):

- `/status` — System health, uptime, kill switch status
- `/last_signal` — Most recent signal details
- `/kill` — Emergency stop (activates kill switch)

## Run Tests

```bash
pytest tests/ -v
```

## Configuration Reference

All settings via `.env`:

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| MARKET_DATA_PROVIDER | Yes | - | "twelvedata", "alphavantage", or "polygon" |
| MARKET_DATA_API_KEY | Yes | - | Provider API key |
| INITIAL_CAPITAL | Yes | - | Starting capital for position sizing |
| TELEGRAM_BOT_TOKEN | No | - | Bot token from @BotFather |
| TELEGRAM_CHAT_ID | No | - | Your Telegram chat/channel ID |
| SIGNAL_THRESHOLD | No | 0.68 | Minimum probability for signals |
| MAX_RISK_PER_TRADE | No | 0.01 | Max risk per trade (fraction) |
| MAX_DAILY_RISK | No | 0.03 | Max daily risk (fraction) |
| MAX_OPEN_POSITIONS | No | 2 | Max simultaneous positions |
| KILL_SWITCH_THRESHOLD | No | 0.05 | Daily loss to trigger kill switch |
| SL_ATR_MULTIPLIER | No | 1.5 | Stop loss ATR multiplier |
| TP_ATR_MULTIPLIER | No | 3.0 | Take profit ATR multiplier |
| LOG_LEVEL | No | INFO | Logging level |
| DB_PATH | No | storage/trading.db | SQLite database path |

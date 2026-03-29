# Research: Core System + Risk Management

**Feature**: `001-core-system-risk`
**Date**: 2026-03-26

## R1: Market Data Provider Abstraction

**Decision**: Abstract base class `MarketDataProvider` with `get_ohlc(asset, timeframe, bars)` method. Concrete implementations for TwelveData (primary), AlphaVantage, and Polygon. Factory function selects provider via `MARKET_DATA_PROVIDER` env var.

**Rationale**: The user does not have an API key yet (confirmed during plan review). An ABC allows starting development with any provider and switching later without code changes (FR-002). TwelveData is recommended first because it has the best free XAU/USD support (800 req/day).

**Alternatives considered**:
- Single hardcoded provider: Rejected — violates FR-002 and limits flexibility.
- CCXT-style unified client: Overkill for 3 providers; custom ABC is simpler.

## R2: Technical Indicator Library

**Decision**: Use the `ta` (Technical Analysis) library for Python. It provides pandas-based implementations of all required indicators: RSI, MACD, EMA, Bollinger Bands, ATR.

**Rationale**: `ta` is the most popular pure-Python TA library with no binary dependencies (unlike TA-Lib which requires C compilation). All indicator functions accept pandas DataFrames and return Series, making integration straightforward. Support/resistance and trend direction will be custom logic on top of `ta` outputs.

**Alternatives considered**:
- TA-Lib (C wrapper): Better performance but requires system-level C library installation. Rejected for ease of setup.
- pandas_ta: Similar to `ta` but less maintained. Rejected.
- Manual implementation: Rejected — reinventing well-tested math adds bug risk.

## R3: Support/Resistance Detection Method

**Decision**: Swing high/low pivot point method over the last 50 bars. A swing high is a bar whose high is higher than the N bars on each side (N=5). Support = most recent swing low; Resistance = most recent swing high.

**Rationale**: Simple, deterministic, reproducible. Matches the constitution requirement for "reproducible mathematical logic." More sophisticated methods (clustering, volume profile) are better suited for Phase 3 when the full decision engine is built.

**Alternatives considered**:
- Fibonacci retracement: Requires identifying trend start/end, more subjective.
- Volume profile: Requires volume-at-price data not available from all providers.
- Rolling min/max: Too simplistic, picks noise rather than meaningful levels.

## R4: Telegram Bot Architecture

**Decision**: Use `python-telegram-bot` v20+ (async). Run the bot in a separate thread alongside APScheduler. The bot is primarily a one-way broadcast system for signals. Commands (`/status`, `/last_signal`, `/kill`) are secondary and restricted to the configured `TELEGRAM_CHAT_ID`.

**Rationale**: Confirmed during clarification — the bot's primary role is broadcasting signals when great opportunities are found. Chat ID restriction (FR-013) prevents unauthorized users from activating the kill switch. Graceful no-op when token is absent (FR-012) allows development without Telegram setup.

**Alternatives considered**:
- Synchronous bot polling: Would block the main thread. Rejected.
- Webhook mode: Requires public URL/HTTPS endpoint. Rejected for local deployment.
- Separate process: Adds IPC complexity. Rejected — thread is sufficient for single-user.

## R5: SQLite Schema Design

**Decision**: 5 tables — signals, trades, performance, news, account_state. Schema created on first startup via `CREATE TABLE IF NOT EXISTS`. No migration framework needed for Phase 1.

**Rationale**: SQLite is the constitution-specified storage. 5 tables cover all persistence needs: signal audit trail (FR-015), trade tracking, daily performance rollup, news storage (prepared for Phase 2), and account state for risk agent queries. At ~288 cycles/day with 1 asset, write volume is negligible for SQLite.

**Alternatives considered**:
- Single table with JSON blobs: Rejected — makes risk agent queries complex.
- Alembic migrations: Overkill for Phase 1 with a single known schema.
- PostgreSQL: Constitution specifies SQLite for initial storage.

## R6: Per-Timeframe Scheduling

**Decision**: APScheduler `BackgroundScheduler` with separate `IntervalTrigger` jobs per timeframe: 5min (every 5 minutes), 15min (every 15 minutes), 1h (every 60 minutes), 4h (every 240 minutes). Each job runs the full pipeline for its timeframe. Use `max_instances=1` to prevent overlapping cycles (edge case from spec).

**Rationale**: Confirmed during plan review — user wants per-timeframe intervals rather than a single fixed loop. APScheduler's `max_instances=1` handles the overlapping cycle edge case natively (logs a warning and skips).

**Alternatives considered**:
- Single 5-min loop analyzing all timeframes: Wastes API calls on higher timeframes. Rejected.
- Cron-based scheduling: Less control over overlap prevention. Rejected.
- asyncio event loop: Adds complexity without benefit for CPU-bound indicator computation. Rejected.

## R7: Historical Data Startup Fetch

**Decision**: On startup, before the scheduler starts, fetch 250 historical candles per timeframe (padding above the 200 minimum for EMA-200 warmup). Use the same market data provider. Retry with exponential backoff (1s, 2s, 4s, 8s, max 60s) if the fetch fails. Do not start the scheduler until data is loaded.

**Rationale**: Confirmed during clarification — the system must produce valid indicators from the first cycle. 250 bars gives 50 bars of "warm" indicator values beyond the minimum 200 needed for EMA-200.

**Alternatives considered**:
- Start with partial data: Rejected — would produce invalid indicator values for hours/days.
- Require pre-loaded CSV: Rejected — adds manual step; API fetch is automatic.

## R8: Configuration via python-dotenv

**Decision**: Use `python-dotenv` to load `.env` file into `os.environ`. A frozen `AppConfig` dataclass reads all values at startup, validates required fields, and provides typed defaults for optional fields. All agents receive `AppConfig` via constructor injection.

**Rationale**: Simple, standard Python approach. Environment variables are the 12-factor app standard. Constructor injection (not global imports) ensures testability — tests can pass mock configs.

**Alternatives considered**:
- YAML/TOML config files: More complex than needed for flat key-value config. Rejected.
- pydantic Settings: Adds a heavy dependency for simple config loading. Rejected.
- Direct os.environ reads in each module: Violates single-source-of-truth. Rejected.

## R9: Kill Switch and Daily Reset

**Decision**: Kill switch state stored in `account_state` table. Checked at the start of every risk evaluation. Daily P&L and kill switch reset at midnight UTC (00:00 UTC) — implemented as a check: if `account_state.updated_at` date < current UTC date, reset daily_pnl to 0 and kill_switch_active to false.

**Rationale**: Confirmed during clarification — UTC midnight reset. Storing kill switch in the database ensures persistence across restarts. The "date changed" check is simpler than scheduling a separate midnight reset job.

**Alternatives considered**:
- In-memory kill switch: Lost on restart. Rejected — must persist.
- Scheduled midnight job: Adds complexity; date comparison is simpler.
- New York market close reset: More complex timezone handling. Rejected per user preference.

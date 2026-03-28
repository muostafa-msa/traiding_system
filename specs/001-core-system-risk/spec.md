# Feature Specification: Core System + Risk Management

**Feature Branch**: `001-core-system-risk`
**Created**: 2026-03-26
**Status**: Draft
**Input**: Phase 1 from implementation plan — market data collection, technical indicators, risk management, signal formatting, Telegram delivery, and scheduled execution for XAU/USD.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Receive Technical Analysis Summary via Telegram (Priority: P1)

As a trader monitoring XAU/USD, I want to receive periodic technical analysis summaries on Telegram so that I can make informed trading decisions without manually checking charts.

The system collects live market candle data for XAU/USD, computes standard technical indicators (RSI, MACD, EMA, Bollinger Bands, ATR), identifies support/resistance levels and trend direction, and sends a human-readable summary to a configured Telegram channel at regular intervals.

**Why this priority**: This is the foundational data pipeline — market data in, analysis out. Without this, no other feature (signals, risk, backtesting) can function. It delivers immediate value by replacing manual chart analysis.

**Independent Test**: Can be fully tested by starting the system, waiting for one scheduled cycle, and verifying a Telegram message arrives containing indicator values for XAU/USD.

**Acceptance Scenarios**:

1. **Given** the system is running and a market data provider is configured, **When** a scheduled cycle triggers, **Then** the system fetches OHLC candle data for XAU/USD and computes RSI, MACD, EMA (20/50/200), Bollinger Bands, and ATR values.
2. **Given** indicators have been computed, **When** the cycle completes, **Then** a formatted summary message is sent to the configured Telegram channel containing all indicator values, trend direction, and support/resistance levels.
3. **Given** the market data provider is unavailable, **When** a scheduled cycle triggers, **Then** the system logs the error and skips the cycle without crashing.

---

### User Story 2 - Risk-Check Any Trading Signal Before Delivery (Priority: P2)

As a trader, I want every trading signal to pass mandatory risk management checks before it reaches me, so that I never receive a signal that violates my capital protection rules.

The risk management agent validates every signal against configurable rules: maximum 1% risk per trade, maximum 3% daily risk, maximum 2 open positions, and a kill switch that disables trading if daily losses exceed 5%. Signals that fail any check are rejected with a reason.

**Why this priority**: The constitution mandates risk management on every signal. Building it in Phase 1 ensures no unfiltered signal ever reaches the user, even during development of later phases.

**Independent Test**: Can be tested by submitting synthetic signals to the risk agent and verifying approvals/rejections match the configured rules.

**Acceptance Scenarios**:

1. **Given** a valid signal with risk below 1% and no daily limit reached, **When** the risk agent evaluates it, **Then** the signal is approved with a calculated position size, stop loss, and take profit.
2. **Given** daily losses have exceeded 5% of capital, **When** the risk agent evaluates any signal, **Then** the kill switch activates and all signals are rejected with reason "Kill switch active".
3. **Given** 2 positions are already open, **When** the risk agent evaluates a new signal, **Then** it is rejected with reason "Max positions reached".
4. **Given** a signal where the risk-reward ratio is below 1.8, **When** the risk agent evaluates it, **Then** it is rejected with reason "Insufficient risk-reward".

---

### User Story 3 - Monitor and Control the System via Telegram (Priority: P3)

As a trader, I want to check the system status and control it remotely through Telegram commands, so that I can monitor its health and stop it in an emergency without accessing the terminal.

The Telegram bot responds to commands: `/status` shows system health and last cycle time, `/last_signal` shows the most recent signal, `/kill` activates the emergency kill switch to stop all signal generation.

**Why this priority**: Remote monitoring and emergency control are essential for a trading system that runs unattended. This builds on P1 (Telegram delivery) and P2 (kill switch).

**Independent Test**: Can be tested by sending each command to the bot and verifying the response content and format.

**Acceptance Scenarios**:

1. **Given** the system is running, **When** the user sends `/status`, **Then** the bot replies with system uptime, last cycle time, number of open positions, and whether the kill switch is active.
2. **Given** at least one signal has been generated, **When** the user sends `/last_signal`, **Then** the bot replies with the most recent signal details (asset, direction, entry, SL, TP, confidence).
3. **Given** the system is actively generating signals, **When** the user sends `/kill`, **Then** the kill switch activates, signal generation stops, and the bot confirms "Kill switch activated".

---

### User Story 4 - Persist All System Data for Tracking (Priority: P4)

As a trader, I want all signals, trades, and account state to be persisted in a local database, so that I can review historical performance and the risk agent can track daily P&L.

The system stores all generated signals, trade records, daily performance metrics, and account state in a local database. The risk agent reads account state to enforce daily risk limits and kill switch logic.

**Why this priority**: Persistence underpins risk management (daily P&L tracking), performance analysis, and auditability. It is a prerequisite for the risk agent to function correctly across cycles.

**Independent Test**: Can be tested by running the system for several cycles and querying the database to verify signals, account state, and performance records exist with correct data.

**Acceptance Scenarios**:

1. **Given** a signal is generated (approved or rejected), **When** the cycle completes, **Then** the signal is recorded in the database with all fields (asset, direction, entry, SL, TP, probability, reasoning, status).
2. **Given** the system has been running for a day, **When** the daily performance is queried, **Then** it returns total signals, trades taken, wins, losses, and net P&L for that day.
3. **Given** the risk agent needs to check daily risk, **When** it queries account state, **Then** it receives current capital, open position count, daily P&L, and kill switch status.

---

### Edge Cases

- What happens when the market data provider returns incomplete or malformed candle data? The system MUST validate data integrity and skip the cycle with a logged warning.
- What happens when the Telegram bot token is not configured? The system MUST continue running without Telegram delivery, logging messages locally instead.
- What happens when the database file is inaccessible or corrupted? The system MUST fail to start with a clear error message rather than running without persistence.
- What happens when multiple scheduled cycles overlap (previous cycle still running)? The system MUST skip the overlapping cycle and log a warning.
- What happens when capital is set to zero or a negative value? The system MUST reject the configuration and refuse to start.
- What happens during a market data provider rate limit? The system MUST respect rate limits, back off, and retry on the next cycle.
- What happens if the startup historical data fetch fails (API down, rate limited)? The system MUST retry with exponential backoff and refuse to start the scheduled loop until sufficient historical data is loaded.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST collect OHLC candle data (open, high, low, close, volume) for XAU/USD from a configurable market data provider.
- **FR-002**: System MUST support swapping between market data providers (TwelveData, AlphaVantage, Polygon) without code changes, using configuration only.
- **FR-003**: System MUST compute these technical indicators from candle data: RSI (14-period), MACD (12, 26, 9), EMA (20, 50, 200-period), Bollinger Bands (20-period, 2 std dev), and ATR (14-period).
- **FR-004**: System MUST estimate support and resistance levels from recent price action.
- **FR-005**: System MUST determine trend direction based on moving average alignment.
- **FR-006**: System MUST evaluate every signal against risk rules before delivery: maximum 1% capital risk per trade, maximum 3% daily capital risk, maximum 2 simultaneous open positions, minimum 1.8 risk-reward ratio.
- **FR-007**: System MUST calculate stop loss and take profit using ATR: SL at 1.5x ATR from entry, TP at 3.0x ATR from entry.
- **FR-008**: System MUST calculate position size based on configured capital and the 1% risk rule.
- **FR-009**: System MUST activate a kill switch that halts all signal generation when daily losses exceed 5% of capital. Daily P&L and kill switch MUST reset at midnight UTC (00:00 UTC).
- **FR-010**: System MUST format approved signals as human-readable messages containing: asset, direction, entry price, stop loss, take profit, confidence score, and reasoning.
- **FR-011**: System MUST send formatted messages to a configured Telegram channel.
- **FR-012**: System MUST operate without Telegram delivery when no bot token is configured, logging messages locally instead.
- **FR-013**: Telegram bot MUST respond to commands: `/status`, `/last_signal`, `/performance`, `/kill`. Commands MUST only be accepted from the configured chat ID; all other senders MUST be ignored.
- **FR-014**: System MUST run on a configurable scheduled loop with independent intervals per analysis timeframe.
- **FR-015**: System MUST persist all signals, trades, performance metrics, and account state in a local database.
- **FR-016**: System MUST load all configuration (API keys, capital, risk parameters, intervals) from environment variables.
- **FR-017**: System MUST log all operations with timestamps using rotating log files.
- **FR-018**: System MUST shut down gracefully when interrupted, completing any in-progress cycle before stopping.
- **FR-019**: All inter-agent data exchange MUST use defined data contracts with no circular dependencies between agents.
- **FR-020**: On startup, the system MUST fetch at least 200 historical candles per timeframe before running the first analysis cycle, ensuring all indicators produce valid values immediately.
- **FR-021**: System MUST estimate breakout probability from technical indicator data (Bollinger Band squeeze and ATR-based volatility analysis).

### Key Entities

- **OHLC Bar**: A single market candle — timestamp, open, high, low, close, volume. The fundamental unit of market data.
- **Indicator Result**: Computed technical indicators for a set of candles — RSI, MACD components, EMA values, Bollinger Band values, ATR, support, resistance, trend direction.
- **Trade Signal**: A proposed trade — asset, direction (BUY/SELL/NO_TRADE), entry price, stop loss, take profit, probability, reasoning, timeframe, timestamp.
- **Risk Verdict**: The risk agent's decision on a signal — approved or rejected, position size if approved, rejection reason if rejected, current daily risk usage, open position count.
- **Account State**: Current capital balance, open position count, daily P&L, kill switch status. Updated after each cycle.
- **Signal Record**: A persisted signal with all fields plus status (pending, approved, rejected, active, closed).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: System completes a full data-collection-to-delivery cycle within 60 seconds under normal conditions.
- **SC-002**: All 5 technical indicators (RSI, MACD, EMA, Bollinger Bands, ATR) produce values matching expected outputs for known input data within 0.1% tolerance.
- **SC-003**: Risk agent correctly rejects 100% of signals that violate any risk rule (tested with at least 10 boundary-condition scenarios).
- **SC-004**: Kill switch activates within 1 cycle of daily loss exceeding 5%, and blocks all subsequent signals for the remainder of the day.
- **SC-005**: Telegram messages arrive within 5 seconds of signal approval.
- **SC-006**: System runs continuously for 24 hours without crashes, memory leaks, or missed scheduled cycles.
- **SC-007**: All signals and account state changes are persisted and queryable from the database after system restart.
- **SC-008**: System starts and operates correctly when Telegram token is not configured, with all messages logged locally.

## Clarifications

### Session 2026-03-26

- Q: Should the Telegram bot restrict commands to authorized users? → A: Yes, restrict to configured chat ID only. The bot is primarily a one-way signal broadcast system; commands (/status, /last_signal, /kill) are secondary and limited to the owner.
- Q: When does "daily" reset for P&L tracking and kill switch? → A: Midnight UTC (00:00 UTC). Kill switch deactivates and daily P&L resets to zero at the start of each new UTC day.
- Q: What happens on first startup with no historical data? → A: Fetch 200+ historical candles on startup before the first cycle runs, ensuring all indicators (including EMA 200) produce valid values from the first cycle.

## Assumptions

- The user has a stable internet connection for API calls and Telegram delivery.
- At least one market data provider API key will be configured before live use (the system can start without one but will skip data collection).
- The Telegram bot and chat ID will be configured by the user separately via BotFather; the system does not create these.
- Phase 1 does not include sentiment analysis, pattern detection, or the full signal scoring algorithm — signals in Phase 1 are indicator summaries only. Full probabilistic signal generation is Phase 3.
- The system runs on a single local machine; distributed deployment is out of scope for Phase 1.
- The chosen database solution is sufficient for the data volume in Phase 1 (single asset, approximately 288 cycles per day at 5-minute intervals).
- Starting capital is user-configured; the system does not connect to any broker or real trading account.

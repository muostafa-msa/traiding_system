# Feature Specification: Telegram Performance Dashboard

**Feature Branch**: `005-telegram-performance`  
**Created**: 2026-04-06  
**Status**: Draft  
**Input**: User description: "Phase 5 — Polish + Telegram Commands: Full Telegram interface with enhanced performance reporting, multi-period rollups, Sharpe ratio computation, and formatted performance dashboard"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - View Daily Performance Summary (Priority: P1)

As a trader monitoring my system via Telegram, I want to send the `/performance` command and receive a comprehensive daily performance report that includes total signals generated, trades taken, win/loss counts, win rate, profit factor, net P&L, and Sharpe ratio for the current day — so I can quickly assess how the system is performing today without logging into any other interface.

**Why this priority**: Daily performance visibility is the core value of this feature. Without it, the trader has no way to assess same-day system behavior from Telegram.

**Independent Test**: Can be fully tested by sending `/performance` in Telegram and verifying a formatted daily summary is returned with accurate metrics drawn from trade data.

**Acceptance Scenarios**:

1. **Given** the system has recorded 5 signals and 3 closed trades today, **When** the user sends `/performance`, **Then** the bot returns a formatted message showing total signals (5), trades taken (3), wins, losses, win rate, profit factor, net P&L, and daily Sharpe ratio.
2. **Given** the system has no signals or trades today, **When** the user sends `/performance`, **Then** the bot returns a message indicating no trading activity for the day with all metrics at zero.
3. **Given** there are open (unclosed) trades, **When** the user sends `/performance`, **Then** only closed trades are included in win/loss calculations; open trades are shown as a separate count.

---

### User Story 2 - View Multi-Period Performance Rollups (Priority: P2)

As a trader, I want to view performance summaries for different time periods (weekly, monthly, all-time) so I can track trends and evaluate the system's longer-term effectiveness beyond just today.

**Why this priority**: Multi-period views provide the context needed to judge whether the system is improving or degrading over time. This builds on the daily view (P1) by aggregating across multiple days.

**Independent Test**: Can be fully tested by sending `/performance weekly`, `/performance monthly`, or `/performance all` in Telegram and verifying each returns correct aggregated metrics for the requested period.

**Acceptance Scenarios**:

1. **Given** the system has trade data spanning 10 days, **When** the user sends `/performance weekly`, **Then** the bot returns an aggregated performance summary for the last 7 calendar days including total trades, win rate, profit factor, net P&L, and Sharpe ratio.
2. **Given** the system has trade data spanning 45 days, **When** the user sends `/performance monthly`, **Then** the bot returns an aggregated performance summary for the last 30 calendar days.
3. **Given** the system has any amount of trade data, **When** the user sends `/performance all`, **Then** the bot returns a lifetime aggregated summary across all recorded trades.
4. **Given** the user sends `/performance` with no argument, **Then** the bot defaults to showing the daily summary (P1 behavior).

---

### User Story 3 - View Formatted Equity and Drawdown Metrics (Priority: P3)

As a trader, I want the performance report to include maximum drawdown and equity change information so I can understand my risk exposure and capital trajectory without needing a separate analytics tool.

**Why this priority**: Drawdown and equity metrics are critical for risk-aware traders, but they build on top of the basic performance data (P1/P2). They add depth to existing reports rather than standing alone.

**Independent Test**: Can be fully tested by verifying that the performance summary messages include max drawdown percentage and net equity change for the requested period.

**Acceptance Scenarios**:

1. **Given** the system has trade data with varying P&L outcomes, **When** the user requests any performance period, **Then** the report includes the maximum drawdown as a percentage of peak equity during that period.
2. **Given** the starting capital was 10,000 and the current equity is 10,500, **When** the user sends `/performance all`, **Then** the report shows total return as +5.0% alongside the absolute P&L.

---

### Edge Cases

- What happens when the Telegram command is sent from an unauthorized chat ID? The system rejects the request silently (existing behavior, preserved).
- What happens when the database has signals but no closed trades for a period? Metrics that require closed trades (win rate, profit factor, Sharpe) display as 0 or N/A; signal count is still shown.
- What happens when only one trade exists for a period? Sharpe ratio is reported as 0 (insufficient data for meaningful standard deviation) with other metrics computed normally.
- How does the system handle time zone boundaries? All dates and periods are computed in UTC, consistent with existing system behavior.
- What happens if the user provides an unrecognized period argument (e.g., `/performance yearly`)? The system responds with a help message listing valid options: daily (default), weekly, monthly, all.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST compute and display daily performance metrics (total signals, trades taken, wins, losses, win rate, profit factor, net P&L, Sharpe ratio) when the `/performance` command is invoked with no arguments.
- **FR-002**: System MUST support period arguments (`weekly`, `monthly`, `all`) on the `/performance` command to display aggregated metrics for the last 7 days, last 30 days, or all-time respectively.
- **FR-003**: System MUST default to daily performance when `/performance` is invoked with no arguments or with the `daily` argument.
- **FR-004**: System MUST compute Sharpe ratio from closed trade returns for any requested period, returning 0 when fewer than 2 closed trades exist in the period.
- **FR-005**: System MUST compute maximum drawdown as a percentage of peak equity during the requested period.
- **FR-006**: System MUST compute total return as a percentage of initial capital for the requested period.
- **FR-007**: System MUST format performance messages in a structured, readable layout suitable for mobile Telegram viewing (lines under 40 characters wide).
- **FR-008**: System MUST aggregate performance data from existing trade and signal records, using closed trades for P&L-based metrics and all signals for signal activity counts.
- **FR-009**: System MUST display the count of currently open (unclosed) trades separately from closed trade metrics.
- **FR-010**: System MUST reject performance commands from unauthorized chat IDs (existing authorization preserved).
- **FR-011**: System MUST respond with a help message listing valid period options when an unrecognized argument is provided.

### Key Entities

- **Performance Summary**: A computed snapshot of trading metrics for a given period — includes signal count, trade count, wins, losses, win rate, profit factor, net P&L, Sharpe ratio, max drawdown, total return, and open trade count.
- **Trade Record**: An individual trade with entry/exit prices, P&L, direction, and close reason — the raw data from which performance is computed.
- **Signal Record**: A generated trading signal — counted for activity metrics regardless of whether a trade was taken.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Trader can view current-day performance summary via a single Telegram command within 3 seconds of sending it.
- **SC-002**: Trader can view weekly, monthly, and all-time performance summaries via Telegram without accessing any other interface.
- **SC-003**: All reported metrics (win rate, profit factor, Sharpe ratio, max drawdown, total return) are mathematically accurate against the underlying trade data.
- **SC-004**: Performance reports are readable on mobile Telegram without horizontal scrolling (message width under 40 characters per line).
- **SC-005**: System handles periods with zero trading activity gracefully, displaying zero-state metrics instead of errors.

## Assumptions

- The existing `trades` and `signals` tables contain all data needed to compute performance metrics — no new data collection is required.
- The existing Telegram bot infrastructure (authentication, polling, command handling) is stable and will be extended, not replaced.
- Performance computation runs on-demand when the command is invoked (not pre-aggregated), which is acceptable given the expected trade volume (fewer than 100 trades per day).
- Sharpe ratio is computed using the standard formula: mean of trade returns divided by their standard deviation, annualized by multiplying by the square root of 252 (trading days).
- The `/performance` command continues to work alongside existing commands (`/status`, `/last_signal`, `/kill`) without interference.
- Initial capital value is available from the `account_state` table for total return computation.

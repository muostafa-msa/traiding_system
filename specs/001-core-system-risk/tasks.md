# Tasks: Core System + Risk Management

**Input**: Design documents from `/specs/001-core-system-risk/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/

**Tests**: Included — the spec defines measurable success criteria (SC-002, SC-003) requiring validated indicator outputs and risk rule boundary testing. Constitution mandates integration tests for agent-to-agent data flow.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- Custom multi-package layout at repository root: `core/`, `data/`, `analysis/`, `agents/`, `execution/`, `storage/`, `tests/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create project structure, dependencies, and configuration

- [x] T001 Create all package directories and `__init__.py` files for core/, data/, analysis/, agents/, execution/, storage/, tests/
- [x] T002 Create requirements.txt with pinned dependencies: pandas, numpy, ta, requests, python-dotenv, apscheduler, python-telegram-bot, feedparser, pytest, pytest-asyncio
- [x] T003 [P] Create .env.example with all configuration variables per quickstart.md in .env.example
- [x] T004 [P] Define all frozen dataclass contracts (OHLCBar, IndicatorResult, TradeSignal, RiskVerdict, AccountState, FinalSignal) in core/types.py per data-model.md (include breakout_probability field in IndicatorResult)
- [x] T005 Implement AppConfig dataclass loading from .env via python-dotenv in core/config.py with validation (reject zero/negative capital, require market_data_provider)
- [x] T006 [P] Implement get_logger(name) factory with rotating file handler + console handler in core/logger.py

**Checkpoint**: Project structure ready, all types defined, config loads from .env, logging operational.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented. Database tests written first (TDD).

### Tests for Foundation

- [x] T007 [P] Create test fixtures (sample OHLC data, test AppConfig, in-memory SQLite) in tests/conftest.py
- [x] T008 [P] Write unit tests for save_signal and get_last_signal in tests/test_database.py
- [x] T009 [P] Write unit tests for open_trade, close_trade, get_open_positions_count in tests/test_database.py
- [x] T010 [P] Write unit tests for get_account_state, update_account_state, reset_daily_if_needed in tests/test_database.py
- [x] T011 [P] Write unit tests for get_daily_performance, update_daily_performance in tests/test_database.py

### Implementation for Foundation

- [x] T012 Implement Database class in storage/database.py: schema creation for all 5 tables (signals, trades, performance, news, account_state) per data-model.md
- [x] T013 Implement Database.save_signal() and Database.get_last_signal() methods in storage/database.py
- [x] T014 Implement Database.get_account_state(), update_account_state(), and reset_daily_if_needed() (UTC midnight reset) in storage/database.py
- [x] T015 [P] Implement Database.open_trade(), close_trade(), get_open_positions_count(), get_daily_pnl() in storage/database.py
- [x] T016 [P] Implement Database.get_daily_performance() and update_daily_performance() in storage/database.py
- [x] T017 Implement Database.__init__ with account_state initialization from config.initial_capital in storage/database.py

**Checkpoint**: Foundation ready — database fully operational with passing tests, test fixtures available. User story implementation can now begin.

---

## Phase 3: User Story 1 - Receive Technical Analysis Summary via Telegram (Priority: P1)

**Goal**: Market data collection -> indicator computation -> formatted summary -> Telegram delivery on schedule

**Independent Test**: Start the system, wait for one scheduled cycle, verify a Telegram message arrives containing indicator values for XAU/USD.

### Tests for User Story 1

- [x] T018 [P] [US1] Write unit tests for compute_indicators() validating RSI, MACD, EMA, BB, ATR against known input data (SC-002: 0.1% tolerance) in tests/test_indicators.py
- [x] T019 [P] [US1] Write unit tests for support/resistance detection, trend direction, and breakout probability in tests/test_indicators.py

### Implementation for User Story 1

- [x] T020 [P] [US1] Implement MarketDataProvider ABC with get_ohlc(asset, timeframe, bars) and MarketDataError exception in data/market_data.py
- [x] T021 [US1] Implement TwelveDataProvider concrete class (API call, response parsing, OHLCBar conversion, rate limit handling) in data/market_data.py
- [x] T022 [P] [US1] Implement AlphaVantageProvider concrete class (API call, response parsing, OHLCBar conversion, rate limit handling) in data/market_data.py
- [x] T023 [P] [US1] Implement PolygonProvider concrete class (API call, response parsing, OHLCBar conversion, rate limit handling) in data/market_data.py
- [x] T024 [US1] Implement get_provider(name) factory function selecting provider from config in data/market_data.py
- [x] T025 [US1] Implement compute_indicators(bars) computing RSI(14), MACD(12,26,9), EMA(20,50,200), BB(20,2), ATR(14) using ta library in analysis/indicators.py
- [x] T026 [US1] Implement support/resistance detection via swing high/low pivot points (N=5, lookback=50) in analysis/indicators.py
- [x] T027 [US1] Implement trend_direction detection via EMA alignment (price vs EMA20 vs EMA50 vs EMA200) in analysis/indicators.py
- [x] T028 [US1] Implement breakout_probability estimation via Bollinger Band squeeze detection and ATR volatility ratio in analysis/indicators.py
- [x] T029 [US1] Implement format_indicator_summary(indicators: IndicatorResult) producing human-readable indicator summary message in execution/signal_generator.py
- [x] T030 [US1] Implement TelegramBot class with start(), stop(), broadcast() methods and no-op mode when token is absent in execution/telegram_bot.py
- [x] T031 [US1] Implement per-timeframe scheduling with APScheduler BackgroundScheduler (5min/15min/1h/4h intervals, max_instances=1) in core/scheduler.py
- [x] T032 [US1] Implement run_cycle(timeframe) pipeline: fetch data -> compute indicators -> format summary -> broadcast -> save to DB in core/scheduler.py
- [x] T033 [US1] Implement startup_fetch() to load 250 historical candles per timeframe with exponential backoff retry in core/scheduler.py
- [x] T034 [P] [US1] Write unit test for startup_fetch() exponential backoff retry logic in tests/test_indicators.py
- [x] T035 [US1] Implement main.py entry point: load config, init logger, init DB, startup fetch, start scheduler + bot, graceful shutdown on SIGINT/SIGTERM

**Checkpoint**: At this point, User Story 1 should be fully functional — system fetches XAU/USD data, computes indicators (including breakout probability), sends summaries to Telegram on schedule.

---

## Phase 4: User Story 2 - Risk-Check Any Trading Signal Before Delivery (Priority: P2)

**Goal**: Every signal passes through risk management checks before reaching the user

**Independent Test**: Submit synthetic TradeSignal objects to risk agent, verify approvals/rejections match all constitutional rules.

### Tests for User Story 2

- [x] T036 [P] [US2] Write unit tests for RiskAgent.evaluate() covering: approved signal with position sizing in tests/test_risk_agent.py
- [x] T037 [P] [US2] Write unit tests for kill switch activation (daily loss > 5%) and blocking in tests/test_risk_agent.py
- [x] T038 [P] [US2] Write unit tests for max positions rejection (>= 2 open) in tests/test_risk_agent.py
- [x] T039 [P] [US2] Write unit tests for daily risk limit (> 3%) and risk-reward ratio (< 1.8) rejection in tests/test_risk_agent.py
- [x] T040 [P] [US2] Write unit tests for UTC midnight daily reset logic in tests/test_risk_agent.py

### Implementation for User Story 2

- [x] T041 [US2] Implement RiskAgent class with __init__(config, database) in agents/risk_agent.py
- [x] T042 [US2] Implement RiskAgent.evaluate(signal) with ordered rule checks: kill switch -> daily loss 5% -> daily risk 3% -> positions -> RR ratio in agents/risk_agent.py
- [x] T043 [US2] Implement position_size calculation (risk_amount / price_risk) in agents/risk_agent.py
- [x] T044 [US2] Implement format_trade_signal(signal, risk) for approved trade signals (asset, direction, entry, SL, TP, confidence, reasoning) in execution/signal_generator.py
- [x] T045 [US2] Add risk evaluation hook to scheduler pipeline: when a TradeSignal is present, evaluate through risk agent before broadcast (no-op when pipeline produces indicator summaries only) in core/scheduler.py

**Checkpoint**: At this point, User Stories 1 AND 2 work together — risk agent is built, tested with synthetic signals, and wired into the pipeline for when TradeSignal generation is added in Phase 3.

---

## Phase 5: User Story 3 - Monitor and Control via Telegram (Priority: P3)

**Goal**: Telegram bot responds to /status, /last_signal, /performance, /kill commands restricted to configured chat ID

**Independent Test**: Send each command to the bot, verify response content and chat ID restriction.

### Tests for User Story 3

- [x] T046 [P] [US3] Write unit tests for chat ID restriction (verify messages from unauthorized senders are ignored) in tests/test_telegram.py
- [x] T047 [P] [US3] Write unit tests for all command handlers (/status, /last_signal, /performance, /kill) verifying response content in tests/test_telegram.py

### Implementation for User Story 3

- [x] T048 [US3] Implement chat ID restriction middleware: ignore all messages not from configured TELEGRAM_CHAT_ID in execution/telegram_bot.py
- [x] T049 [US3] Implement /status command handler returning uptime, last cycle time, open positions, kill switch status in execution/telegram_bot.py
- [x] T050 [US3] Implement /last_signal command handler querying Database.get_last_signal() and formatting response in execution/telegram_bot.py
- [x] T051 [US3] Implement /performance command handler querying Database.get_daily_performance() and returning total signals, win rate, profit factor, daily P&L in execution/telegram_bot.py
- [x] T052 [US3] Implement /kill command handler activating kill switch via Database.update_account_state() and confirming to user in execution/telegram_bot.py

**Checkpoint**: All Telegram interaction complete — broadcast + 4 commands, all restricted to owner.

---

## Phase 6: User Story 4 - Persist All System Data for Tracking (Priority: P4)

**Goal**: All signals, trades, and account state persisted and queryable

**Independent Test**: Run system for several cycles, query database to verify signal records, account state, and performance data.

### Implementation for User Story 4

- [x] T053 [US4] Ensure scheduler pipeline persists every signal (approved and rejected) with full fields after each cycle in core/scheduler.py
- [x] T054 [US4] Ensure scheduler calls database.reset_daily_if_needed() at the start of each cycle in core/scheduler.py
- [x] T055 [US4] Add signal status transitions: update signal status from pending to approved/rejected after risk evaluation in core/scheduler.py

**Checkpoint**: All user stories independently functional. Full data pipeline: collect -> analyze -> risk check -> deliver -> persist.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Edge cases, error handling, integration testing, and success criteria validation

- [x] T056 Add OHLC data validation (reject malformed candles, log warning, skip cycle) in core/scheduler.py
- [x] T057 Add overlapping cycle prevention logging (APScheduler max_instances=1 already handles skip) in core/scheduler.py
- [x] T058 [P] Add database inaccessibility check on startup (fail fast with clear error) in main.py
- [x] T059 [P] Write integration test: full pipeline (fetch -> compute -> format -> risk -> broadcast -> persist) with mocked market data provider in tests/test_integration.py
- [x] T060 [P] Validate SC-001: measure full cycle execution time and assert < 60 seconds in tests/test_integration.py
- [x] T061 Validate SC-006: run system for extended duration verifying no crashes, memory leaks, or missed cycles (document manual 24h test procedure in tests/README.md)
- [x] T062 Run full test suite: pytest tests/ -v and verify all tests pass
- [x] T063 Run quickstart.md validation: verify setup, run, and verify steps work end-to-end

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 (types.py, config.py) — BLOCKS all user stories
- **US1 (Phase 3)**: Depends on Phase 2 — core data pipeline
- **US2 (Phase 4)**: Depends on Phase 2 + database methods from Phase 2 — can start in parallel with US1
- **US3 (Phase 5)**: Depends on US1 (telegram_bot.py exists) + US2 (kill switch exists)
- **US4 (Phase 6)**: Depends on Phase 2 — can start in parallel with US1/US2
- **Polish (Phase 7)**: Depends on all user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Phase 2 — no dependencies on other stories
- **User Story 2 (P2)**: Can start after Phase 2 — independent of US1 (uses synthetic signals for testing)
- **User Story 3 (P3)**: Depends on US1 (telegram_bot) and US2 (kill switch, risk agent)
- **User Story 4 (P4)**: Can start after Phase 2 — pipeline integration tasks depend on US1/US2

### Within Each User Story

- Tests MUST be written first and FAIL before implementation
- Data collection before analysis
- Analysis before formatting
- Formatting before delivery
- Core logic before integration

### Parallel Opportunities

- T003 + T004 + T006 can run in parallel (Phase 1)
- T007 + T008 + T009 + T010 + T011 can run in parallel (Phase 2 tests)
- T015 + T016 can run in parallel (Phase 2 implementation)
- T018 + T019 can run in parallel (US1 tests)
- T020 + T022 + T023 can run in parallel (provider implementations)
- T036 + T037 + T038 + T039 + T040 can run in parallel (US2 tests)
- T046 + T047 can run in parallel (US3 tests)
- T058 + T059 + T060 can run in parallel (Phase 7)
- US1 and US2 can run in parallel after Phase 2
- US4 can run in parallel with US1 and US2

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: Start system, verify Telegram receives indicator summaries
5. This alone replaces manual chart checking

### Incremental Delivery

1. Setup + Foundational -> Foundation ready
2. Add User Story 1 -> Indicator summaries on Telegram (MVP!)
3. Add User Story 2 -> Signals risk-checked before delivery
4. Add User Story 3 -> Remote monitoring + emergency kill
5. Add User Story 4 -> Full audit trail and performance tracking
6. Polish -> Edge cases, validation, test suite green

### Parallel Strategy

With multiple agents (Claude + GLM5):

1. Both complete Setup + Foundational together
2. Once Foundational is done:
   - Agent A: User Story 1 (data pipeline)
   - Agent B: User Story 2 (risk agent) — can test with synthetic signals
3. After US1 + US2: Agent A does US3, Agent B does US4
4. Both do Polish phase

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Total tasks: 63

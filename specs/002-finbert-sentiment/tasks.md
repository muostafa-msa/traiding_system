# Tasks: Sentiment Intelligence (FinBERT)

**Input**: Design documents from `/specs/002-finbert-sentiment/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/

**Tests**: Included — the constitution mandates unit tests for every agent (Section 16). Spec defines measurable success criteria (SC-001, SC-002) requiring validated classification performance and blackout detection.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- Custom multi-package layout at repository root: `core/`, `data/`, `models/`, `agents/`, `execution/`, `storage/`, `tests/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create new package, dependencies, configuration, and data contracts

- [X] T001 Create models/ package directory with models/__init__.py
- [X] T002 Update requirements.txt adding torch>=2.0.0 and transformers>=4.30.0
- [X] T003 [P] Update .env.example with all new configuration variables: RSS_FEED_URLS, RSS_KEYWORDS, BLACKOUT_KEYWORDS, BLACKOUT_DURATION_HOURS, SENTIMENT_WINDOW_HOURS, FINBERT_MODEL_PATH, MODEL_DEVICE
- [X] T004 [P] Add NewsItem and SentimentResult frozen dataclasses to core/types.py per data-model.md (include all fields with validation)
- [X] T005 Extend AppConfig with new fields (rss_feed_urls, rss_keywords, blackout_keywords, blackout_duration_hours, sentiment_window_hours, finbert_model_path, model_device) and update load_config() in core/config.py

**Checkpoint**: Project structure ready, new types defined, config loads new fields from .env.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented. Model manager + database extensions.

### Tests for Foundation

- [X] T006 [P] Write unit tests for ModelManager (detect_device returns cpu/cuda/mps, lazy loading, cache reuse, force-cpu override) in tests/test_model_manager.py
- [X] T007 [P] Write unit tests for Database.save_news() and Database.get_recent_news(hours) in tests/test_database.py
- [X] T008 [P] Write unit tests for Database.check_hash_exists() deduplication in tests/test_database.py
- [X] T009 [P] Write unit tests for Database.set_blackout_until(), is_blackout_active(), and expired blackout auto-clear in tests/test_database.py

### Implementation for Foundation

- [X] T010 Implement ModelManager class in models/model_manager.py: detect_device() (CUDA -> MPS -> CPU priority chain, MODEL_DEVICE override), load_model(name, path), get_model(name), model caching dict, logging
- [X] T011 Update database schema in storage/database.py: add content_hash TEXT column to news table, add blackout_until TIMESTAMP column to account_state table
- [X] T012 Implement Database.save_news(item, classification, confidence, content_hash) with INSERT OR IGNORE for dedup, and Database.get_recent_news(hours) returning classified headlines within rolling window in storage/database.py
- [X] T013 Implement Database.check_hash_exists(content_hash), set_blackout_until(timestamp), is_blackout_active(), and clear_expired_blackout() in storage/database.py

**Checkpoint**: Foundation ready — ModelManager operational, database supports news CRUD + blackout state, all foundational tests pass. User story implementation can now begin.

---

## Phase 3: User Story 1 - Receive Sentiment-Enriched Market Analysis (Priority: P1)

**Goal**: RSS news collection -> FinBERT classification -> aggregate macro score -> persist to database

**Independent Test**: Configure RSS feed URLs, run one cycle, verify database contains classified headlines with Bullish/Bearish/Neutral labels and an aggregate macro score is computed.

### Tests for User Story 1

- [X] T014 [P] [US1] Write unit tests for FinBERT wrapper: classify known financial headlines (e.g., "Gold prices surge" -> Bullish, "Fed raises rates" -> Bearish), verify label mapping (positive->Bullish, negative->Bearish, neutral->Neutral), confidence in [0,1] in tests/test_finbert.py
- [X] T015 [P] [US1] Write unit tests for NewsCollector: RSS fetch with mocked feedparser, keyword filtering (match/no-match), SHA-256 dedup (duplicate rejected), empty feed handling in tests/test_sentiment.py
- [X] T016 [P] [US1] Write unit tests for SentimentAgent: classify list of NewsItems returns list of SentimentResults (same length), graceful degradation when model unavailable (returns empty list) in tests/test_sentiment.py
- [X] T017 [P] [US1] Write unit tests for NewsAgent: orchestration returns MacroSentiment, macro score calculation (mean of direction*confidence over 4h window), empty headlines returns score=0.0, persistence to database in tests/test_sentiment.py

### Implementation for User Story 1

- [X] T018 [US1] Implement FinBERT wrapper in models/finbert.py: load ProsusAI/finbert via ModelManager, batch classification using transformers pipeline (batch_size=8, truncation=True), label mapping (positive->Bullish, negative->Bearish, neutral->Neutral), return list[SentimentResult]
- [X] T019 [US1] Implement NewsCollector class in data/news_data.py: fetch_headlines(feed_urls, keywords) using requests.get(url, timeout=10) + feedparser.parse(), keyword filtering (case-insensitive any-match), SHA-256 content hash dedup, return list[NewsItem]
- [X] T020 [US1] Implement SentimentAgent class in agents/sentiment_agent.py: __init__(config), classify(news_items: list[NewsItem]) -> list[SentimentResult] wrapping FinBERT model, graceful no-op if model unavailable
- [X] T021 [US1] Implement NewsAgent class in agents/news_agent.py: __init__(config, database), run() -> MacroSentiment orchestrating collect -> classify -> persist -> aggregate, compute macro_score as mean(direction_sign * confidence) over 4h rolling window from database
- [X] T022 [US1] Integrate news agent into scheduler pipeline in core/scheduler.py: call news_agent.run() in run_cycle() after indicator computation, no-op when RSS not configured (empty rss_feed_urls)

**Checkpoint**: At this point, User Story 1 should be fully functional — system collects news, classifies sentiment via FinBERT, computes macro score, persists to database.

---

## Phase 4: User Story 2 - Block Signals During High-Impact News Events (Priority: P2)

**Goal**: Detect blackout trigger keywords -> activate time-based blackout -> risk agent rejects signals during blackout

**Independent Test**: Inject headline with "Federal Reserve interest rate decision", verify blackout activates, submit synthetic TradeSignal, confirm rejection with "News blackout period".

### Tests for User Story 2

- [X] T023 [P] [US2] Write unit tests for blackout keyword detection: headline containing "Fed" triggers blackout, "FOMC" triggers, "NFP" triggers, non-trigger headline does not activate, case-insensitive matching in tests/test_sentiment.py
- [X] T024 [P] [US2] Write unit tests for RiskAgent blackout rejection: active blackout rejects signal with "News blackout period", no blackout allows signal through, blackout check occurs between position limit and RR ratio checks in tests/test_risk_agent.py
- [X] T025 [P] [US2] Write unit tests for blackout auto-expiry: blackout_until in the past clears automatically, new trigger keyword resets the timer in tests/test_sentiment.py

### Implementation for User Story 2

- [X] T026 [US2] Add blackout keyword detection to NewsAgent.run() in agents/news_agent.py: scan current batch headlines for blackout keywords (from config), if match found call database.set_blackout_until(now + duration)
- [X] T027 [US2] Add blackout check to RiskAgent.evaluate() in agents/risk_agent.py: insert between position limit check and RR ratio check, query database.is_blackout_active(), reject with "News blackout period" if active
- [X] T028 [US2] Add blackout expiry handling in agents/news_agent.py: at start of run(), call database.clear_expired_blackout() to auto-clear if current_time > blackout_until

**Checkpoint**: At this point, User Stories 1 AND 2 work together — sentiment analysis active, blackout protection enforced, risk agent rejects during blackout periods.

---

## Phase 5: User Story 3 - One-Time Model Setup (Priority: P3)

**Goal**: Single script downloads FinBERT weights locally for offline operation

**Independent Test**: Run setup_models.py, verify models/finbert/ directory contains config.json and model weights, run again and verify it skips re-download.

### Implementation for User Story 3

- [X] T029 [US3] Implement setup_models.py: download ProsusAI/finbert using transformers AutoModel.from_pretrained() + AutoTokenizer.from_pretrained(), save to FINBERT_MODEL_PATH (default models/finbert/), create directory if needed, skip if config.json exists, clear error/success messages

**Checkpoint**: Model setup script operational — developers can prepare system for offline sentiment analysis.

---

## Phase 6: User Story 4 - Model Lifecycle Management (Priority: P4)

**Goal**: Validate ML model resource management — lazy loading, device detection, caching

**Independent Test**: Start system on CPU, trigger sentiment analysis, verify FinBERT loads on CPU. Monitor memory before/after.

**Note**: ModelManager implementation is in Phase 2 (Foundational) since it blocks US1. This phase validates it end-to-end.

### Tests for User Story 4

- [X] T030 [P] [US4] Write integration test: FinBERT loads lazily on first sentiment call, second call reuses cached model (no reload) in tests/test_model_manager.py
- [X] T031 [P] [US4] Write unit test: MODEL_DEVICE=cpu forces CPU even if CUDA available (mock torch.cuda.is_available=True) in tests/test_model_manager.py

**Checkpoint**: Model lifecycle verified — lazy loading, caching, and device override all validated.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Integration testing, performance validation, and success criteria verification

- [X] T032 [P] Write integration test: full sentiment pipeline (fetch RSS -> filter -> dedup -> classify -> aggregate -> persist) with mocked feedparser in tests/test_integration.py
- [X] T033 [P] Validate SC-001: batch classify 20 headlines and assert < 30 seconds on CPU in tests/test_integration.py (can mock model for CI, manual test with real model)
- [X] T034 [P] Write integration test: blackout pipeline (trigger headline -> blackout active -> signal rejected -> expiry -> signal allowed) in tests/test_integration.py
- [X] T035 Run full test suite: pytest tests/ -v and verify all tests pass
- [X] T036 Run quickstart.md validation: verify setup, configure, run, and verify steps work end-to-end

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 (types.py, config.py) — BLOCKS all user stories
- **US1 (Phase 3)**: Depends on Phase 2 — core sentiment pipeline
- **US2 (Phase 4)**: Depends on Phase 2 + US1's news_agent.py (adds blackout to existing agent)
- **US3 (Phase 5)**: Depends on Phase 1 only (standalone script) — can start in parallel with US1
- **US4 (Phase 6)**: Depends on Phase 2 (ModelManager already built) — validation phase
- **Polish (Phase 7)**: Depends on US1 + US2 being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Phase 2 — no dependencies on other stories
- **User Story 2 (P2)**: Depends on US1's news_agent.py (adds blackout detection to it)
- **User Story 3 (P3)**: Can start after Phase 1 — independent (standalone setup script)
- **User Story 4 (P4)**: Can start after Phase 2 — validates foundational ModelManager

### Within Each User Story

- Tests MUST be written first and FAIL before implementation
- Data collection before analysis
- Analysis before aggregation
- Core logic before integration
- Agent implementation before scheduler integration

### Parallel Opportunities

- T003 + T004 can run in parallel (Phase 1)
- T006 + T007 + T008 + T009 can run in parallel (Phase 2 tests)
- T014 + T015 + T016 + T017 can run in parallel (US1 tests)
- T023 + T024 + T025 can run in parallel (US2 tests)
- T030 + T031 can run in parallel (US4 tests)
- T032 + T033 + T034 can run in parallel (Phase 7)
- US1 and US3 can run in parallel after Phase 2
- US4 can run in parallel with US1

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: Start system, verify news collected + classified + macro score computed
5. This alone adds sentiment analysis to the trading system

### Incremental Delivery

1. Setup + Foundational -> Foundation ready
2. Add User Story 1 -> Sentiment analysis on news (MVP!)
3. Add User Story 2 -> Blackout protection during major events
4. Add User Story 3 -> One-command model setup
5. Add User Story 4 -> Validated model lifecycle
6. Polish -> Integration tests, performance validation

### Parallel Strategy

With multiple agents (Claude + GLM5):

1. Both complete Setup + Foundational together
2. Once Foundational is done:
   - Agent A: User Story 1 (sentiment pipeline)
   - Agent B: User Story 3 (setup script — independent)
3. After US1: Agent A does US2, Agent B does US4
4. Both do Polish phase

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Total tasks: 36

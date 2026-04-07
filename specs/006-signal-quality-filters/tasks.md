# Tasks: Signal Quality Filtering Improvements

**Input**: Design documents from `/specs/006-signal-quality-filters/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup

**Purpose**: Branch creation and shared configuration additions

- [X] T001 Create feature branch `006-signal-quality-filters` from main
- [X] T002 Add 5 new config fields (`prediction_agreement_enabled`, `mtf_confirmation_enabled`, `mtf_min_agreeing_timeframes`, `opportunity_score_enabled`, `opportunity_score_threshold`) to `AppConfig` dataclass in `core/config.py` and `load_config()` function with env var parsing and defaults (`True`, `True`, `2`, `True`, `0.55`)
- [X] T003 [P] Add the 5 new env vars (`PREDICTION_AGREEMENT_ENABLED`, `MTF_CONFIRMATION_ENABLED`, `MTF_MIN_AGREEING_TIMEFRAMES`, `OPPORTUNITY_SCORE_ENABLED`, `OPPORTUNITY_SCORE_THRESHOLD`) with defaults to `.env.example`
- [X] T004 [P] Update test config fixtures in `tests/conftest.py` to include the 5 new `AppConfig` fields with their default values so all existing tests continue to pass

**Checkpoint**: `pytest tests/ -v` passes with no regressions. Config loads with new fields.

---

## Phase 2: Foundational

**Purpose**: New dataclass needed by multiple user stories

- [X] T005 Add `OpportunityScore` frozen dataclass to `core/types.py` with fields: `trend_strength`, `volatility_regime`, `pattern_confidence`, `prediction_confidence`, `sentiment_alignment`, `indicator_agreement`, `mtf_agreement` (all `float` in `[0.0, 1.0]`), and `composite` (auto-computed in `__post_init__` using weights: 0.20, 0.15, 0.15, 0.15, 0.10, 0.15, 0.10). Add validation that all fields are in `[0.0, 1.0]`.

**Checkpoint**: Foundation ready — user story implementation can now begin.

---

## Phase 3: User Story 1 — Reduce Telegram Noise (Priority: P1)

**Goal**: Only approved trade signals are broadcast to Telegram. Indicator analysis summaries go to logs only.

**Independent Test**: Run the system for multiple cycles. Verify zero Telegram messages unless an approved trade signal is generated. `/status` command still works.

### Implementation for User Story 1

- [X] T006 [US1] Remove the `self._bot.broadcast(message)` call at line 168 of `core/scheduler.py`. Keep the `logger.info()` on line 166 so indicator summaries still appear in log files.
- [X] T007 [US1] Update `test_pipeline_persist_and_broadcast` in `tests/test_integration.py` — remove or update the assertion that checks for "GOLD TECHNICAL ANALYSIS" in broadcast calls, since indicator summaries are no longer broadcast. Verify the test still validates that approved trade signals ARE broadcast.

**Checkpoint**: Indicator summaries appear in `logs/trading.log` but not in Telegram. Trade signals still broadcast. All tests pass.

---

## Phase 4: User Story 2 — Coherent Pattern Detection (Priority: P1)

**Goal**: Filter contradictory patterns so only the strongest direction's patterns (plus NEUTRAL) reach the scoring model.

**Independent Test**: Feed bar data that produces both double_top (SELL) and double_bottom (BUY). Verify only the stronger pattern and NEUTRAL patterns remain.

### Implementation for User Story 2

- [X] T008 [US2] Add `_filter_contradictory_patterns(results: list[PatternResult]) -> list[PatternResult]` function in `analysis/pattern_detection.py`. Logic: find strongest pattern by confidence, remove patterns whose `direction` opposes the strongest pattern's direction, preserve all NEUTRAL-direction patterns. If all patterns are NEUTRAL, return unchanged.
- [X] T009 [US2] Integrate `_filter_contradictory_patterns()` into `detect_patterns()` in `analysis/pattern_detection.py` — call it after collecting all results (after line 311) and before computing `best` (line 318). Update the `best` computation and `PatternDetectionResult` construction to use the filtered list.
- [X] T010 [US2] Add `TestContradictoryPatternFiltering` test class in `tests/test_patterns.py` with cases: (a) double_top SELL + double_bottom BUY → only strongest kept + NEUTRAL preserved, (b) all NEUTRAL → no filtering, (c) single pattern → unchanged, (d) two same-direction patterns → both preserved.

**Checkpoint**: `pytest tests/test_patterns.py -v` passes. Pattern detection only returns coherent directional patterns.

---

## Phase 5: User Story 3 — Prediction Model Agreement (Priority: P1)

**Goal**: Reject trade signals when LSTM prediction disagrees with signal direction. NEUTRAL predictions also cause rejection.

**Independent Test**: Generate a SELL signal from indicators with LSTM predicting BUY or NEUTRAL — verify system rejects the trade.

### Implementation for User Story 3

- [X] T011 [US3] Add `_check_prediction_agreement(self, direction: str, prediction: PricePrediction) -> bool` method to `SignalAgent` class in `agents/signal_agent.py`. Returns `True` if `prediction.direction == direction`, `False` otherwise. Also return `True` (bypass) when LSTM is unavailable — detect this by checking if `prediction.confidence == 0.0 and prediction.direction == "NEUTRAL"` (the default PricePrediction returned when LSTM fails to load). Log AUDIT line when disagreement detected or when bypassed due to unavailable LSTM.
- [X] T012 [US3] Integrate prediction agreement gate into `SignalAgent.decide()` in `agents/signal_agent.py` — after direction is determined (after line 196 for both xgboost and fallback paths) but before the probability threshold check (line 213). If `self._config.prediction_agreement_enabled` is `True` and `_check_prediction_agreement()` returns `False`, return `_make_no_trade()`. Log the rejection reason.
- [X] T013 [US3] Add `TestPredictionAgreement` test class in `tests/test_signal_agent.py` with cases: (a) BUY signal + BUY prediction → passes, (b) SELL signal + SELL prediction → passes, (c) BUY signal + SELL prediction → rejected, (d) SELL signal + NEUTRAL prediction → rejected, (e) prediction agreement disabled → all pass through, (f) LSTM unavailable (default PricePrediction with confidence=0.0, direction=NEUTRAL) → bypassed, gate returns True. Also add `TestAllGatesDisabled` test case: set `prediction_agreement_enabled=False`, `opportunity_score_enabled=False`, `mtf_confirmation_enabled=False` and verify `decide()` produces the same output as the pre-feature baseline (no regressions).

**Checkpoint**: `pytest tests/test_signal_agent.py -v -k prediction_agreement` passes. Signals are rejected when LSTM disagrees.

---

## Phase 6: User Story 4 — Multi-Timeframe Trend Confirmation (Priority: P2)

**Goal**: Require at least N timeframes to agree on trend direction before allowing a signal. Graceful degradation on cold start.

**Independent Test**: Analyze bars where 5m is bearish but 1h and 4h are bullish. Verify the 5m SELL signal is rejected.

### Implementation for User Story 4

- [X] T014 [US4] Add `get_trend_consensus(self, exclude_timeframe: str) -> dict` method to `ChartAgent` class in `agents/chart_agent.py`. Queries `self._analyses` dict for all timeframes except `exclude_timeframe`. Returns `{"total": int, "bullish": int, "bearish": int, "neutral": int}` counts based on each analysis's `indicators.trend_direction`. Returns `{"total": 0, ...}` if no other timeframes analyzed yet.
- [X] T015 [US4] Add `_check_mtf_agreement(self, signal_direction: str, analysis: TimeframeAnalysis) -> bool` method to `TradingScheduler` in `core/scheduler.py`. Uses `self._chart_agent.get_trend_consensus(analysis.timeframe)`. Maps signal BUY→bullish, SELL→bearish. Returns `True` if agreeing count >= `self._config.mtf_min_agreeing_timeframes` OR if `consensus["total"] < self._config.mtf_min_agreeing_timeframes` (cold start graceful degradation). Log AUDIT line with consensus details.
- [X] T016 [US4] Integrate MTF check into `_evaluate_signal_if_present()` in `core/scheduler.py` — after `decision.direction != "NO_TRADE"` check but before `TradeSignal` creation. If `self._config.mtf_confirmation_enabled` is `True` and `_check_mtf_agreement()` returns `False`, log rejection and return early (skip `process_signal()`).
- [X] T017 [US4] Add `TestMTFConfirmation` test class in `tests/test_chart_agent.py` — test `get_trend_consensus()` with various `_analyses` states (empty, partial, full), test cold start graceful degradation (total < min_agreeing → allow through), test rejection when insufficient timeframes agree, test pass-through when `mtf_confirmation_enabled=False`.

**Checkpoint**: `pytest tests/ -v -k mtf` passes. Signals are rejected when insufficient timeframes agree.

---

## Phase 7: User Story 5 — Trade Opportunity Score Gate (Priority: P2)

**Goal**: Compute a 7-component opportunity score and reject signals below threshold (0.55).

**Independent Test**: Create scenarios with varying quality levels. Verify signals below threshold are rejected.

### Implementation for User Story 5

- [X] T018 [US5] Add `compute_opportunity_score()` function in `agents/signal_agent.py`. Takes `analysis: TimeframeAnalysis`, `prediction: PricePrediction`, `sentiment: MacroSentiment`, `signal_direction: str`, `mtf_agreement_fraction: float = 0.0` parameters. Computes each of the 7 components: (1) `trend_strength` from `prediction.trend_strength`, (2) `volatility_regime` from normalized ATR (`min(analysis.indicators.atr / last_close, 0.02) / 0.02` clamped to [0,1] — moderate volatility is favorable), (3) `pattern_confidence` from `analysis.patterns.strongest_confidence`, (4) `prediction_confidence` from `prediction.confidence`, (5) `sentiment_alignment` = 1.0 if sentiment agrees with direction (positive macro→BUY, negative→SELL) else 0.0, (6) `indicator_agreement` from `analysis.clarity.indicator_agreement`, (7) `mtf_agreement` from the fraction parameter. Returns an `OpportunityScore` instance.
- [X] T019 [US5] Update `SignalAgent.decide()` signature to accept optional `mtf_agreement_fraction: float = 0.0` parameter. Update the caller in `core/scheduler.py:_evaluate_signal_if_present()` to compute the MTF agreement fraction from `self._chart_agent.get_trend_consensus()` and pass it to `decide()`. This wires real MTF data into the opportunity score before the gate is added.
- [X] T020 [US5] Integrate opportunity score gate into `SignalAgent.decide()` in `agents/signal_agent.py` — after prediction agreement check and before existing probability threshold check. If `self._config.opportunity_score_enabled` is `True`, call `compute_opportunity_score()` with the `mtf_agreement_fraction` parameter from `decide()`. If `score.composite < self._config.opportunity_score_threshold`, return `_make_no_trade()`. Log AUDIT line with all 7 component values and composite.
- [X] T021 [US5] Add `TestOpportunityScore` test class in `tests/test_signal_agent.py` with cases: (a) all strong components → score > 0.55, passes, (b) mixed weak components → score < 0.55, rejected, (c) opportunity score disabled → all pass through, (d) missing data defaults to 0.0.

**Checkpoint**: `pytest tests/test_signal_agent.py -v -k opportunity_score` passes. Low-quality signals are rejected.

---

## Phase 8: User Story 6 — Improved Signal Message Format (Priority: P3)

**Goal**: Telegram signal messages include R:R ratio, SL/TP distances, position size in oz with dollar risk, market context, and AI analysis.

**Independent Test**: Generate a signal and verify the Telegram message contains all required fields per the contract in `contracts/telegram-signal-format.md`.

### Implementation for User Story 6

- [X] T022 [US6] Redesign `format_trade_signal()` in `execution/signal_generator.py` to accept keyword args `indicators: IndicatorResult | None = None` and `patterns_summary: str | None = None`. Compute: SL distance = `abs(signal.stop_loss - signal.entry_price)`, TP distance = `abs(signal.take_profit - signal.entry_price)`, R:R ratio = `tp_distance / sl_distance`, dollar risk = `risk.position_size * sl_distance`. Format per the contract template with direction emoji, entry/SL/TP with distances, R:R, position in oz with dollar risk, confidence, market context section (trend, pattern, RSI, MACD), and AI analysis section. When `indicators` is `None`, omit the Market Context section. When `patterns_summary` is `None`, show "None detected".
- [X] T023 [US6] Update the `process_signal()` call in `core/scheduler.py` to pass `indicators` and `patterns_summary` to `format_trade_signal()`. Extract these from the `TimeframeAnalysis` available in `_evaluate_signal_if_present()` — pass them through to `process_signal()` by adding `analysis` parameter or storing as instance state.

**Checkpoint**: Trade signals in Telegram show new format with R:R, distances, market context. `/status` and other commands still work.

---

## Phase 9: User Story 7 — Entry vs Support/Resistance Warning (Priority: P3)

**Goal**: Log a warning when SELL entry is below support or BUY entry is above resistance.

**Independent Test**: Generate a SELL signal where entry < support. Verify a warning appears in `logs/trading.log`.

### Implementation for User Story 7

- [X] T024 [US7] Add `_log_sr_proximity(self, signal: TradeSignal, indicators: IndicatorResult) -> None` method to `TradingScheduler` in `core/scheduler.py`. Checks: if `signal.direction == "SELL"` and `signal.entry_price < indicators.support`, log warning "Entry {entry} below support {support} — breakout may have already occurred". If `signal.direction == "BUY"` and `signal.entry_price > indicators.resistance`, log warning "Entry {entry} above resistance {resistance}". Otherwise, no warning.
- [X] T025 [US7] Call `_log_sr_proximity()` in `_evaluate_signal_if_present()` in `core/scheduler.py` after `TradeSignal` creation (after line 233) but before `process_signal()`. Pass the signal and `analysis.indicators`.

**Checkpoint**: S/R proximity warnings appear in logs when entry is beyond support/resistance levels.

---

## Phase 10: Polish & Cross-Cutting Concerns

**Purpose**: Final validation and cleanup

- [X] T026 Run full test suite `pytest tests/ -v` — verify all existing and new tests pass with zero failures
- [X] T027 Run `python main.py` for a brief live test — verify: (a) no indicator summaries in Telegram, (b) AUDIT logs show prediction agreement checks, MTF consensus, and opportunity scores, (c) trade signals (if any) appear in new format
- [X] T028 Run quickstart.md validation — verify all per-phase checks from `specs/006-signal-quality-filters/quickstart.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on T002 (config fields) from Setup
- **User Stories (Phase 3+)**: All depend on Foundational phase completion
  - US1 (Phase 3): Independent — no dependency on other stories
  - US2 (Phase 4): Independent — no dependency on other stories
  - US3 (Phase 5): Independent — no dependency on other stories
  - US4 (Phase 6): Independent — no dependency on other stories
  - US5 (Phase 7): Depends on US4 (T014 `get_trend_consensus()` for MTF fraction) and Phase 2 (T005 `OpportunityScore` dataclass)
  - US6 (Phase 8): Independent — no dependency on other stories
  - US7 (Phase 9): Independent — no dependency on other stories
- **Polish (Phase 10)**: Depends on all user stories being complete

### User Story Dependencies

```
Phase 1 (Setup)
    │
Phase 2 (Foundational)
    │
    ├── US1 (Telegram Noise) ─────── independent
    ├── US2 (Pattern Filtering) ──── independent
    ├── US3 (Prediction Agreement) ── independent
    ├── US4 (MTF Confirmation) ────── independent
    ├── US5 (Opportunity Score) ────── depends on US4 (get_trend_consensus)
    ├── US6 (Message Format) ──────── independent
    └── US7 (S/R Warning) ─────────── independent
         │
    Phase 10 (Polish)
```

### Parallel Opportunities

- T003 and T004 can run in parallel (different files)
- US1, US2, US3, US4 can all run in parallel (different files, no cross-dependencies)
- US6 and US7 can run in parallel (different parts of scheduler.py + signal_generator.py)
- US5 should run after US4 (needs `get_trend_consensus()`)

---

## Parallel Example: P1 User Stories

```
# After Phase 2 is complete, these 3 stories can run in parallel:

Story US1 (Telegram Noise):
  T006 → T007

Story US2 (Pattern Filtering):
  T008 → T009 → T010

Story US3 (Prediction Agreement):
  T011 → T012 → T013
```

---

## Implementation Strategy

### MVP First (User Stories 1-3 Only)

1. Complete Phase 1: Setup (T001-T004)
2. Complete Phase 2: Foundational (T005)
3. Complete Phase 3: US1 — Reduce Telegram Noise (T006-T007)
4. Complete Phase 4: US2 — Coherent Pattern Detection (T008-T010)
5. Complete Phase 5: US3 — Prediction Agreement (T011-T013)
6. **STOP and VALIDATE**: Run `pytest tests/ -v`, test live with `python main.py`
7. Deploy if ready — the 3 P1 stories deliver the highest-impact quality improvements

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. Add US1-US3 (P1) → Test → Deploy (**MVP**)
3. Add US4-US5 (P2) → Test → Deploy (MTF + opportunity score)
4. Add US6-US7 (P3) → Test → Deploy (message format + S/R warnings)
5. Each increment adds value without breaking previous stories

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story is independently completable and testable
- Commit after each phase or logical task group
- All new quality gates default to enabled — system immediately benefits from improved filtering
- When all gates are disabled via config, system behaves identically to pre-feature version

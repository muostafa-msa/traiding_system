# Tasks: AI Decision Engine (LSTM + XGBoost + GPT-2B)

**Input**: Design documents from `/specs/003-ai-decision-engine/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: Included per constitution §16: "Every agent MUST have unit tests" and "Integration tests MUST verify agent-to-agent data flow."

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Install new dependencies and define shared data types

- [x] T001 Update requirements.txt with scikit-learn and xgboost dependencies
- [x] T002 Add new dataclasses (PatternResult, PatternDetectionResult, PricePrediction, ClarityScore, TimeframeAnalysis, FeatureVector, SignalDecision) to core/types.py per data-model.md

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Extend core infrastructure that ALL user stories depend on

**CRITICAL**: No user story work can begin until this phase is complete

- [x] T003 [P] Extend core/config.py with new fields: lstm_model_path, xgboost_model_path, gpt2_model_path, fallback_weight_indicators, fallback_weight_patterns, fallback_weight_sentiment, fallback_weight_prediction, gpt2_max_tokens, gpt2_temperature, lstm_sequence_length, decision_window_minutes per data-model.md
- [x] T004 [P] Extend models/model_manager.py with load/unload support for LSTM (PyTorch), XGBoost (xgboost.Booster), and GPT-2 (transformers pipeline) model types, including sequential unloading for memory management per research.md R7
- [x] T005 [P] Extend tests/conftest.py with new fixtures: sample PatternDetectionResult, sample PricePrediction, sample MacroSentiment, sample FeatureVector, sample TimeframeAnalysis, and mock ModelManager returning fake models

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - Probability-Based Trade Signals (Priority: P1) MVP

**Goal**: Combine all available analysis into a single probability score and generate signals only when probability >= 0.68 threshold. Falls back to weighted formula when XGBoost is unavailable.

**Independent Test**: Feed historical market data with existing indicators (from Phase 1) and verify: probability score produced for every cycle, BUY/SELL only when >= 0.68, NO_TRADE otherwise, fallback formula works without trained XGBoost.

### Implementation for User Story 1

- [x] T006 [P] [US1] Implement XGBoostWrapper class (inference-only: __init__, predict, is_trained) in models/xgboost_model.py per contracts/pipeline-contract.md — loads saved model if available, returns probability 0.0-1.0 from FeatureVector
- [x] T007 [P] [US1] Implement weighted_formula() fallback function in agents/signal_agent.py per research.md R6 — linear combination with configurable weights (0.30/0.20/0.25/0.25), direction by majority vote, ties produce NO_TRADE
- [x] T008 [P] [US1] Implement template_explain() fallback function in agents/signal_agent.py — constructs explanation from structured signal data referencing trend, sentiment, and patterns
- [x] T009 [US1] Implement FeatureVector assembly logic (assemble_features method) in agents/signal_agent.py per data-model.md — combine indicators, patterns, sentiment, prediction into feature vector with neutral defaults for missing components (0.0 confidence, NEUTRAL direction, 0.0 sentiment)
- [x] T010 [US1] Implement SignalAgent.decide() in agents/signal_agent.py per contracts/pipeline-contract.md — score via XGBoost if trained else fallback, apply 0.68 threshold, generate explanation if threshold met, return SignalDecision with scoring_method field
- [x] T011 [US1] Implement best-signal-wins deduplication logic in agents/signal_agent.py — maintain sliding window of recent SignalDecisions per decision_window_minutes, emit only highest-probability signal, suppress and log conflicting/lower signals
- [x] T012 [US1] Extend core/scheduler.py to wire SignalAgent into the pipeline — after indicators and news, assemble features, call signal_agent.decide(), pass approved signals to risk_agent and Telegram delivery
- [x] T013 [US1] Write unit tests for SignalAgent in tests/test_signal_agent.py — test: fallback formula scoring, threshold enforcement (>=0.68 → signal, <0.68 → NO_TRADE), partial feature vector with neutral defaults, best-signal-wins deduplication, scoring_method field accuracy
- [x] T014 [US1] Write integration test in tests/test_signal_scoring.py — test full pipeline from indicators → feature assembly → scoring → threshold → signal construction with mock models and real indicator data

**Checkpoint**: System produces probability-based signals using fallback formula with existing indicators. XGBoost scoring activates automatically when a trained model is available. MVP is functional.

---

## Phase 4: User Story 3 - Chart Pattern Detection (Priority: P2)

**Goal**: Automatically detect 6 chart patterns (breakout, triangle, double top/bottom, head and shoulders, range) and assign confidence scores for inclusion in the probability calculation.

**Independent Test**: Provide price data with known patterns and verify each detector identifies the pattern with appropriate confidence 0.0-1.0. Feed pattern results into US1 feature vector and confirm probability score changes.

### Implementation for User Story 3

- [x] T015 [P] [US3] Implement detect_breakout() in analysis/pattern_detection.py — price closes above resistance (or below support), confidence based on break magnitude vs ATR, returns PatternResult or None
- [x] T016 [P] [US3] Implement detect_triangle() in analysis/pattern_detection.py — converging trendlines (higher lows + lower highs) over minimum 10 bars, confidence based on touches and convergence tightness
- [x] T017 [P] [US3] Implement detect_double_top() and detect_double_bottom() in analysis/pattern_detection.py — two peaks/troughs within 2% of each other separated by at least 10 bars, confidence based on symmetry
- [x] T018 [P] [US3] Implement detect_head_shoulders() in analysis/pattern_detection.py — three peaks with middle highest, neckline break detection, confidence based on shoulder symmetry and neckline penetration
- [x] T019 [P] [US3] Implement detect_range() in analysis/pattern_detection.py — price oscillating between support/resistance for 20+ bars, confidence based on touch count and range tightness
- [x] T020 [US3] Implement detect_patterns() aggregator in analysis/pattern_detection.py per contracts/pipeline-contract.md — calls all 6 detectors, assembles PatternDetectionResult with strongest_confidence and strongest_direction, requires minimum 50 bars
- [x] T021 [US3] Write tests in tests/test_patterns.py — test each detector with synthetic data containing known patterns, test aggregator with multiple simultaneous patterns, test empty/no-pattern case returns neutral result, test minimum bar validation

**Checkpoint**: Pattern detection runs on price data and feeds confidence scores into the feature vector. SC-006 target: >=70% recall on known patterns.

---

## Phase 5: User Story 5 - Multi-Timeframe Signal Selection (Priority: P2)

**Goal**: Analyze multiple timeframes independently, compute clarity scores, and select the best timeframe for signal generation.

**Independent Test**: Run analysis across 5m/15m/1h/4h on the same data and verify the system selects the timeframe with the highest clarity score. Confirm best-signal-wins emits only one signal per decision window.

### Implementation for User Story 5

- [x] T022 [US5] Implement clarity score computation in agents/chart_agent.py per research.md R5 — indicator_agreement (50%): fraction of RSI/MACD/EMA/BB agreeing on direction; pattern_confidence (30%): strongest pattern; data_completeness (20%): 1.0 minus missing bar ratio. Returns ClarityScore dataclass.
- [x] T023 [US5] Implement chart_agent.analyze() in agents/chart_agent.py per contracts/pipeline-contract.md — runs indicators + pattern detection on a single timeframe, assembles TimeframeAnalysis with clarity score
- [x] T024 [US5] Implement chart_agent.select_best_timeframe() in agents/chart_agent.py — compares TimeframeAnalysis across all recently-run timeframes, returns the one with highest clarity composite
- [x] T025 [US5] Integrate chart_agent into scheduler pipeline in core/scheduler.py — replace direct indicator calls with chart_agent.analyze() per timeframe, pass best TimeframeAnalysis to signal_agent
- [x] T026 [US5] Write tests in tests/test_chart_agent.py — test clarity score computation with known indicator states, test best timeframe selection with varying clarity scores, test single-timeframe fallback, test data completeness penalty for gapped data

**Checkpoint**: System analyzes all 4 timeframes and selects the clearest one for signal generation. Clarity score visible in logs.

---

## Phase 6: User Story 2 - Price Direction Prediction (Priority: P2)

**Goal**: Predict short-term price direction using LSTM from historical price patterns and indicator features, providing forward-looking input to probability scoring.

**Independent Test**: Provide 60+ bars of historical OHLC data with indicators and verify prediction agent returns direction (BUY/SELL/NEUTRAL), confidence 0.0-1.0, volatility estimate, and trend strength. Verify fallback to NEUTRAL with 0.0 confidence when model is unavailable.

### Implementation for User Story 2

- [x] T027 [P] [US2] Implement LSTM model architecture (LSTMNet class) in models/lstm_model.py per research.md R1 — single-layer LSTM, 64 hidden units, 15 input features, 3 outputs (direction logit, volatility, trend strength), dropout 0.2
- [x] T028 [US2] Implement LSTMWrapper class (inference: __init__, predict, is_trained, feature preparation) in models/lstm_model.py per contracts/pipeline-contract.md — prepare sequences of 60 bars with 15 features, run inference, map output to PricePrediction dataclass, fallback to neutral prediction if model unavailable or data insufficient (<60 bars)
- [x] T029 [US2] Implement PredictionAgent in agents/prediction_agent.py per contracts/pipeline-contract.md — wraps LSTMWrapper, prepares OHLC + indicator features, catches all exceptions and returns fallback PricePrediction (NEUTRAL, 0.0), logs warnings
- [x] T030 [US2] Integrate prediction_agent into scheduler pipeline in core/scheduler.py — call prediction_agent.predict() after chart analysis, pass PricePrediction to signal_agent feature assembly
- [x] T031 [US2] Write tests in tests/test_lstm.py — test LSTM architecture forward pass shape, test feature preparation from OHLCBar + IndicatorResult, test fallback on insufficient data, test prediction output bounds (confidence 0-1, trend_strength 0-1)
- [x] T032 [US2] Write tests in tests/test_prediction_agent.py — test agent wrapping with mock LSTM, test fallback behavior on model load failure, test exception handling returns neutral prediction

**Checkpoint**: LSTM predictions feed into the feature vector. Trained model produces learned predictions; untrained returns neutral defaults.

---

## Phase 7: User Story 4 - Human-Readable Trade Explanations (Priority: P3)

**Goal**: Generate plain-language explanations for each trade signal referencing key contributing factors, using GPT-2 with template fallback.

**Independent Test**: Provide structured signal context and verify: explanation generated for signals >= 0.68, explanation references at least 2 contributing factors, template fallback produces valid explanation when GPT-2 unavailable, no explanation for NO_TRADE.

### Implementation for User Story 4

- [x] T033 [US4] Implement ExplanationModel class in models/explanation_model.py per contracts/pipeline-contract.md and research.md R3 — call GPT-OSS-20B via Ollama HTTP API (`/api/generate`), structured prompt template with market analysis context, max 150 tokens generation, temperature 0.7, return explanation string or None on failure
- [x] T034 [US4] Integrate explanation generation into SignalAgent.decide() in agents/signal_agent.py — call ExplanationModel.explain() when probability >= threshold, fall back to template_explain() on failure, skip explanation entirely for NO_TRADE
- [x] T035 [US4] Update execution/signal_generator.py to include the explanation field prominently in formatted Telegram signal messages
- [x] T036 [US4] Write tests in tests/test_explanation_model.py — test prompt template formatting with sample data, test explanation generation with mocked Ollama HTTP response, test fallback to template on Ollama failure, test NO_TRADE skips explanation

**Checkpoint**: Every generated signal includes a human-readable explanation. SC-003: explanation references at least 2 contributing factors.

---

## Phase 8: User Story 6 - Model Training on Historical Data (Priority: P3)

**Goal**: Train LSTM and XGBoost models on historical CSV data using walk-forward cross-validation so models outperform fallback.

**Independent Test**: Run training on a CSV of historical data, verify trained model is saved to disk, verify it loads on next startup, verify trained model outputs differ from fallback formula.

### Implementation for User Story 6

- [x] T037 [P] [US6] Implement LSTMWrapper.train() in models/lstm_model.py per research.md R1 — walk-forward expanding window CV (80/20 split), Adam optimizer lr=0.001, batch_size=32, max 100 epochs with early stopping (patience=10), save best model to lstm_model_path
- [x] T038 [P] [US6] Implement XGBoostWrapper.train() in models/xgboost_model.py per research.md R2 — walk-forward CV, max_depth=6, n_estimators=200, lr=0.1, subsample=0.8, probability calibration via CalibratedClassifierCV, save model to xgboost_model_path
- [x] T039 [US6] Implement CLI training interface (__main__ blocks) in models/lstm_model.py and models/xgboost_model.py — accept --train --data <csv_path> arguments, load CSV data, compute indicators, run training, report metrics
- [x] T040 [US6] Write tests in tests/test_xgboost.py — test feature engineering from FeatureVector, test training on small synthetic dataset, test model save/load round-trip, test inference produces calibrated probabilities in [0,1]

**Checkpoint**: Models can be trained offline on historical CSV data. Trained models automatically loaded on next system start. SC-007: trained outputs differ from fallback.

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Finalize setup scripts, documentation, logging, and full validation

- [x] T041 [P] Update setup_models.py to verify Ollama connectivity and GPT-OSS-20B availability (replaces GPT-2 download — model is managed by Ollama)
- [x] T042 [P] Update .env.example with all new configuration fields per quickstart.md
- [x] T043 Implement FR-012 audit logging across pipeline — log all model predictions, probability scores, scoring methods, signal decisions, and suppressed signals in core/scheduler.py and agents/signal_agent.py
- [x] T044 Run full test suite validation (pytest tests/ -v) and fix any failures
- [x] T045 Run quickstart.md validation — verify setup instructions, training commands, and normal operation work end-to-end

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 (T002 types must exist for T003-T005)
- **User Stories (Phase 3+)**: All depend on Phase 2 completion
  - User stories can proceed in priority order (P1 → P2 → P3)
  - Some P2 stories can run in parallel (see below)
- **Polish (Phase 9)**: Depends on all user stories being complete

### User Story Dependencies

- **US1 (P1) Probability Signals**: Can start after Phase 2. No dependencies on other stories. Uses existing indicators + neutral defaults for missing features. **This is the MVP.**
- **US3 (P2) Chart Patterns**: Can start after Phase 2. Independent of US1. Enriches US1's feature vector once complete.
- **US5 (P2) Multi-Timeframe**: Depends on US3 (patterns needed for clarity score). Can start once T020 is done.
- **US2 (P2) Price Prediction**: Can start after Phase 2. Independent of US1/US3/US5. Enriches US1's feature vector once complete.
- **US4 (P3) Explanations**: Depends on US1 (needs SignalAgent.decide() to exist).
- **US6 (P3) Training**: Depends on US1 (XGBoostWrapper) and US2 (LSTMWrapper) for training implementations.

### Parallel Opportunities

Within Phase 2: T003, T004, T005 can all run in parallel.

Within Phase 3 (US1): T006, T007, T008 can run in parallel (different functions/files).

Within Phase 4 (US3): T015, T016, T017, T018, T019 can all run in parallel (independent pattern detectors).

**Cross-story parallelism** (after Phase 2):
- US1 + US3 + US2 can all start simultaneously
- US5 starts after US3 completes
- US4 starts after US1 completes
- US6 starts after US1 + US2 complete

```text
Phase 2 ──→ US1 (P1) ──→ US4 (P3) ──→ Polish
         ├─→ US3 (P2) ──→ US5 (P2) ──┘
         └─→ US2 (P2) ──→ US6 (P3) ──┘
```

---

## Parallel Example: User Story 3 (Chart Patterns)

```bash
# Launch all 5 pattern detectors together (different functions, no deps):
Task: "T015 Implement detect_breakout() in analysis/pattern_detection.py"
Task: "T016 Implement detect_triangle() in analysis/pattern_detection.py"
Task: "T017 Implement detect_double_top() and detect_double_bottom() in analysis/pattern_detection.py"
Task: "T018 Implement detect_head_shoulders() in analysis/pattern_detection.py"
Task: "T019 Implement detect_range() in analysis/pattern_detection.py"

# Then sequentially:
Task: "T020 Implement detect_patterns() aggregator"
Task: "T021 Write tests"
```

## Parallel Example: User Story 1 (MVP)

```bash
# Launch independent scoring implementations together:
Task: "T006 Implement XGBoostWrapper in models/xgboost_model.py"
Task: "T007 Implement weighted_formula() fallback in agents/signal_agent.py"
Task: "T008 Implement template_explain() fallback in agents/signal_agent.py"

# Then sequentially (depends on above):
Task: "T009 Implement FeatureVector assembly"
Task: "T010 Implement SignalAgent.decide()"
Task: "T011 Implement best-signal-wins"
Task: "T012 Extend scheduler"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001-T002)
2. Complete Phase 2: Foundational (T003-T005)
3. Complete Phase 3: User Story 1 (T006-T014)
4. **STOP and VALIDATE**: Test US1 independently — system produces signals using fallback formula with existing indicators
5. The system is now functional end-to-end with probability-based signals

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. Add US1 → Probability signals with fallback (MVP!)
3. Add US3 → Pattern detection enriches feature vector
4. Add US5 → Multi-timeframe selection improves signal quality
5. Add US2 → LSTM predictions add forward-looking analysis
6. Add US4 → Human-readable explanations improve UX
7. Add US6 → Model training enables learning from data
8. Each story adds value without breaking previous stories

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- The fallback mechanism ensures the system works at every stage of incremental delivery
- Constitution §16 mandates tests for every agent, so test tasks are included in each user story

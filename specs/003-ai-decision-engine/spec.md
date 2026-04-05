# Feature Specification: AI Decision Engine (LSTM + XGBoost + GPT-2B)

**Feature Branch**: `003-ai-decision-engine`
**Created**: 2026-03-30
**Status**: Draft
**Input**: Phase 3 of implementation plan — Full probability-based signal generation with ML models

## Clarifications

### Session 2026-03-30

- Q: Can multiple timeframes independently trigger separate signals, or only one signal per decision window? → A: Only the highest-probability signal across recent timeframes is emitted per decision window (best-signal-wins). Conflicting signals from different timeframes are suppressed.
- Q: Should probability scoring use partial features when some sources are unavailable, or skip the cycle? → A: Score with partial features — substitute neutral defaults (0.0 confidence, NEUTRAL direction, 0.0 sentiment) for missing components. Never skip a cycle due to a single unavailable source.
- Q: What factors compose the clarity score for timeframe selection? → A: Indicator agreement (percentage of indicators aligned on direction) + strongest pattern confidence + data completeness (no gaps in candle data).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Probability-Based Trade Signals (Priority: P1)

As a trader, I want the system to combine all available analysis (technical indicators, chart patterns, price predictions, and news sentiment) into a single probability score for each potential trade, so that I receive signals backed by quantitative confidence rather than subjective interpretation.

**Why this priority**: This is the core value proposition of Phase 3. Without unified probability scoring, the system cannot make autonomous signal decisions. All other stories depend on this capability.

**Independent Test**: Can be fully tested by feeding historical market data and verifying that the system produces a probability score between 0 and 1 for each analysis cycle, and only generates BUY/SELL signals when the probability exceeds the 0.68 threshold.

**Acceptance Scenarios**:

1. **Given** the system has received current market data, technical indicators, pattern detections, price predictions, and sentiment scores, **When** a full analysis cycle completes, **Then** the system produces a probability score between 0.0 and 1.0 representing trade confidence.
2. **Given** the probability score is 0.68 or higher, **When** the signal decision is made, **Then** a BUY or SELL signal is generated with the probability included.
3. **Given** the probability score is below 0.68, **When** the signal decision is made, **Then** a NO_TRADE result is produced and no signal is sent.
4. **Given** the ML model has not been trained yet, **When** an analysis cycle runs, **Then** the system falls back to a weighted formula combining indicator scores, pattern confidence, prediction confidence, and sentiment score to produce the probability.

---

### User Story 2 - Price Direction Prediction (Priority: P2)

As a trader, I want the system to predict short-term price direction using historical price patterns and technical features, so that the signal decisions incorporate forward-looking analysis rather than relying solely on current state.

**Why this priority**: Price prediction is a key input to the probability scoring model. It provides the forward-looking component that distinguishes this system from a simple indicator-based alert tool.

**Independent Test**: Can be tested by providing historical OHLC data with indicator features and verifying the prediction agent returns a direction (BUY/SELL/NEUTRAL), a confidence value, and a volatility estimate.

**Acceptance Scenarios**:

1. **Given** the system has at least 60 bars of historical OHLC data with computed indicators, **When** a prediction is requested, **Then** the system returns a predicted direction (BUY, SELL, or NEUTRAL), a confidence score (0.0-1.0), a volatility estimate, and a trend strength score (0.0-1.0).
2. **Given** insufficient historical data (fewer than 60 bars), **When** a prediction is requested, **Then** the system returns a NEUTRAL prediction with low confidence and logs a warning.
3. **Given** the prediction model is trained on historical data, **When** new market data arrives, **Then** the prediction reflects learned patterns from training data rather than only rule-based heuristics.

---

### User Story 3 - Chart Pattern Detection (Priority: P2)

As a trader, I want the system to automatically detect common chart patterns (breakouts, triangles, double tops/bottoms, head and shoulders, trading ranges), so that pattern-based signals are included in the overall probability calculation.

**Why this priority**: Chart patterns are a widely recognized component of technical analysis. Detecting them automatically ensures no significant visual pattern is missed and feeds valuable features into the probability model.

**Independent Test**: Can be tested by providing price data containing known patterns and verifying each detector correctly identifies the pattern with an appropriate confidence score.

**Acceptance Scenarios**:

1. **Given** price data exhibiting a breakout above resistance, **When** pattern detection runs, **Then** a breakout pattern is identified with a confidence score between 0.0 and 1.0.
2. **Given** price data forming a double top, **When** pattern detection runs, **Then** a double top pattern is identified with appropriate confidence.
3. **Given** price data with no discernible pattern, **When** pattern detection runs, **Then** no patterns are detected (empty result or all confidences near zero).
4. **Given** multiple patterns detected simultaneously, **When** results are aggregated, **Then** all detected patterns and their confidences are available for downstream processing.

---

### User Story 4 - Human-Readable Trade Explanations (Priority: P3)

As a trader, I want each trade signal to include a plain-language explanation of why the signal was generated, so that I can understand and validate the reasoning before acting on it.

**Why this priority**: Explanations build trust and allow the trader to apply human judgment. While the system can produce signals without explanations, the explanatory text significantly improves usability and trader confidence.

**Independent Test**: Can be tested by providing a structured signal context (indicators, sentiment, prediction, probability) and verifying the system generates a coherent, readable explanation that references the key factors.

**Acceptance Scenarios**:

1. **Given** a trade signal has been generated with probability >= 0.68, **When** the explanation step runs, **Then** a human-readable text is produced that references the key factors (trend, sentiment, prediction, patterns) contributing to the decision.
2. **Given** the signal is NO_TRADE (probability < 0.68), **When** the analysis cycle completes, **Then** no explanation is generated (explanation is skipped to save resources).
3. **Given** the explanation model is unavailable or fails, **When** the explanation step runs, **Then** the system falls back to a template-based summary constructed from the structured signal data, and the signal is still delivered.

---

### User Story 5 - Multi-Timeframe Signal Selection (Priority: P2)

As a trader, I want the system to analyze multiple timeframes (5m, 15m, 1h, 4h) independently and select the best timeframe for signal generation, so that signals are based on the clearest and most reliable analysis available.

**Why this priority**: Different market conditions favor different timeframes. Selecting the best timeframe by clarity score improves signal quality and reduces false signals.

**Independent Test**: Can be tested by running analysis across multiple timeframes on the same data and verifying the system selects the timeframe with the highest clarity score.

**Acceptance Scenarios**:

1. **Given** analysis has been performed on 5m, 15m, 1h, and 4h timeframes, **When** the chart agent selects the best timeframe, **Then** it picks the timeframe with the highest clarity score (a composite of indicator agreement percentage, strongest pattern confidence, and data completeness).
2. **Given** only one timeframe has sufficient data, **When** timeframe selection occurs, **Then** that timeframe is used by default.
3. **Given** the system is running per-timeframe on independent schedules, **When** the signal agent runs, **Then** it considers the most recent results from all recently-run timeframes and emits only the single highest-probability signal per decision window (best-signal-wins), suppressing lower-probability or conflicting signals from other timeframes.

---

### User Story 6 - Model Training on Historical Data (Priority: P3)

As a system operator, I want to train the prediction and probability models on historical market data, so that the models learn from past patterns and produce more accurate predictions than the rule-based fallbacks.

**Why this priority**: Training enables the models to outperform the weighted-formula fallback. However, the system is functional without trained models (via fallback), making this a lower priority for initial delivery.

**Independent Test**: Can be tested by running the training process on a CSV of historical data and verifying the trained model produces different (ideally improved) outputs compared to the untrained fallback.

**Acceptance Scenarios**:

1. **Given** a CSV file of historical OHLC data (at least 1 year), **When** the training process is executed, **Then** a trained model is saved to disk and can be loaded for inference.
2. **Given** a trained model exists, **When** the system starts, **Then** it loads the trained model instead of using the fallback formula.
3. **Given** training data is provided, **When** training runs, **Then** walk-forward cross-validation is used to prevent look-ahead bias.

---

### Edge Cases

- What happens when all ML models fail to load at startup? The system must fall back to the weighted formula for probability and template-based reasoning, logging errors but continuing to operate.
- What happens when some feature sources are unavailable during a cycle (e.g., RSS down, prediction model not loaded)? The system substitutes neutral defaults for missing features and proceeds with scoring — it never skips a cycle due to a single unavailable source.
- What happens when the prediction model returns extreme confidence (>0.95)? The probability score should still be bounded and subject to the same threshold and risk management rules.
- What happens when news sentiment and technical indicators strongly disagree? The probability model must weigh all inputs and may produce a score below threshold, resulting in NO_TRADE.
- What happens when market data gaps or missing candles are encountered? The system should skip the analysis cycle for that timeframe and log the issue rather than producing predictions from incomplete data.
- What happens when the probability model is retrained mid-operation? The system should complete the current analysis cycle with the old model and load the new model on the next cycle.
- What happens when the 5m timeframe produces a BUY and the 1h timeframe produces a SELL within the same decision window? Only the highest-probability signal is emitted; the conflicting signal is suppressed and logged.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST detect chart patterns (breakout, triangle, double top, double bottom, head and shoulders, trading range) and assign each a confidence score between 0.0 and 1.0.
- **FR-002**: System MUST perform multi-timeframe analysis across 5m, 15m, 1h, and 4h intervals and select the best timeframe based on a clarity score. The clarity score is a composite of: (1) indicator agreement — the percentage of indicators (RSI, MACD, EMA alignment, Bollinger Bands) that agree on direction, (2) strongest detected pattern confidence, and (3) data completeness — absence of gaps in candle data for that timeframe.
- **FR-003**: System MUST predict price direction (BUY, SELL, or NEUTRAL) with an associated confidence, volatility estimate, and trend strength from historical price data and indicator features.
- **FR-004**: System MUST combine all available features (indicators, patterns, sentiment, price prediction, volatility) into a single probability score between 0.0 and 1.0. When a feature source is unavailable (e.g., RSS down, prediction model not loaded), the system MUST substitute neutral defaults (0.0 confidence, NEUTRAL direction, 0.0 sentiment) and proceed with scoring rather than skipping the cycle.
- **FR-005**: System MUST generate a BUY or SELL signal only when the probability score meets or exceeds the 0.68 threshold, and produce NO_TRADE otherwise. When multiple timeframes produce signals within the same decision window, only the single highest-probability signal is emitted; conflicting or lower-probability signals from other timeframes are suppressed.
- **FR-006**: System MUST generate a human-readable explanation for each signal that meets the probability threshold, referencing the key contributing factors.
- **FR-007**: System MUST fall back to a weighted formula for probability scoring when the trained model is not available.
- **FR-008**: System MUST fall back to template-based explanations when the explanation model is unavailable.
- **FR-009**: System MUST support training the prediction and probability models from historical CSV data using walk-forward cross-validation.
- **FR-010**: System MUST orchestrate the full pipeline (chart analysis, news/sentiment, prediction, probability scoring, explanation, risk management, delivery) through the scheduler on per-timeframe intervals.
- **FR-011**: System MUST run all ML inference locally (no cloud inference calls) with automatic device selection.
- **FR-012**: System MUST log all model predictions, probability scores, and signal decisions for auditability.

### Key Entities

- **Pattern Detection Result**: Represents a detected chart pattern with its type (breakout, triangle, double top, double bottom, head and shoulders, range), confidence score, and associated price levels.
- **Price Prediction**: Represents a forward-looking prediction with direction, confidence, volatility estimate, and trend strength. Produced by the prediction model from OHLC + indicator features.
- **Feature Vector**: The unified collection of all analysis features (indicator values, pattern confidences, sentiment scores, prediction outputs, volatility metrics) assembled for probability scoring.
- **Signal Probability**: The output of the probability scoring model — a single 0.0-1.0 value representing overall trade confidence.
- **Trade Explanation**: A human-readable text explaining the reasoning behind a generated signal, referencing the dominant contributing factors.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The system generates a probability score for every completed analysis cycle, with no unhandled failures during scoring.
- **SC-002**: Signals are generated only when probability >= 0.68; all signals below threshold result in NO_TRADE.
- **SC-003**: Every generated signal includes a human-readable explanation referencing at least two contributing factors (e.g., trend direction, sentiment, pattern).
- **SC-004**: The system completes a full analysis cycle (data collection through signal decision) within 30 seconds per timeframe on commodity hardware.
- **SC-005**: When ML models are unavailable, the system still produces signals using the fallback formula with no user-visible degradation in reliability.
- **SC-006**: Pattern detection identifies known patterns in test data with at least 70% recall against manually labeled examples.
- **SC-007**: Trained prediction and probability models produce measurably different outputs compared to the untrained fallback when tested on held-out data.
- **SC-008**: The full pipeline runs continuously across all four timeframes (5m, 15m, 1h, 4h) without memory leaks or crashes over a 24-hour period.

## Assumptions

- Phase 1 (core infrastructure, risk management, indicators, scheduler, Telegram delivery) and Phase 2 (FinBERT sentiment, news agent) are fully implemented and operational.
- Historical CSV data for XAU/USD (at least 1 year of 1h candles) is available for model training.
- The system runs on hardware with at least 8 GB RAM to accommodate all models loaded sequentially (not simultaneously).
- The 0.68 probability threshold is configurable via environment settings, though it serves as the default.
- Model training is a separate offline step, not part of the real-time analysis pipeline.
- GPU acceleration is optional — the system defaults to CPU inference and must meet performance criteria on CPU.
- The weighted-formula fallback uses a linear combination of indicator trend score, pattern confidence, sentiment macro score, and prediction confidence with configurable weights.

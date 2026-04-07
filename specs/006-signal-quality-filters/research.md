# Research: Signal Quality Filtering Improvements

**Feature**: 006-signal-quality-filters
**Date**: 2026-04-07

## R1: Indicator Summary Broadcast Removal

**Decision**: Remove `self._bot.broadcast(message)` at `core/scheduler.py:168`, keep the `logger.info()` on line 166.

**Rationale**: The broadcast fires on every cycle for all 4 timeframes (~17 messages/hour). Trade signals are already broadcast separately at `scheduler.py:279`. Removing the indicator broadcast achieves a >90% reduction in Telegram noise while preserving log-based debugging.

**Alternatives considered**:
- Rate-limiting broadcasts (e.g., 1/hour) -- rejected because indicator summaries have zero user value in Telegram.
- Moving to a separate "verbose" channel -- adds complexity for no clear benefit.

---

## R2: Contradictory Pattern Filtering

**Decision**: Add `_filter_contradictory_patterns()` in `analysis/pattern_detection.py` after collecting all results (line 311), before computing `best` (line 318). Logic: find strongest pattern by confidence, remove patterns with opposing direction, preserve NEUTRAL patterns. Zero out filtered patterns in XGBoost feature vector.

**Rationale**: `detect_patterns()` currently appends ALL detected patterns (lines 287-311). Double_top (SELL) and double_bottom (BUY) can appear simultaneously, feeding contradictory signals to XGBoost. The strongest pattern should determine the directional bias, and opposing patterns should be removed.

**Alternatives considered**:
- Weighted averaging of conflicting patterns -- rejected because conflicting patterns indicate a detection ambiguity, not a balanced signal.
- Rejecting all patterns when conflicts exist -- too aggressive, discards valid strongest pattern.

**Key implementation detail**: The `PatternDetectionResult` dataclass (types.py:197-215) is not frozen, so patterns can be filtered in-place. The `__post_init__` auto-computes `strongest_confidence/strongest_direction` from `max(patterns, key=confidence)` when `strongest_confidence == 0.0`, but since `detect_patterns()` explicitly sets these fields (line 318-322), the filter must also update them after filtering.

---

## R3: Prediction Agreement Gate

**Decision**: Add hard gate in `signal_agent.py:decide()` after direction is determined (after line 196) but before threshold check (line 213). If `prediction.direction != direction` (including NEUTRAL predictions), return NO_TRADE.

**Rationale**: The LSTM prediction is currently just one of 26 XGBoost features. There is no validation that the system's own prediction model agrees with the signal direction. Trading against the prediction model is fundamentally inconsistent.

**User preference**: Reject entirely -- both opposite predictions (BUY signal + SELL prediction) AND neutral predictions cause rejection. The LSTM must explicitly confirm direction.

**Alternatives considered**:
- Soft penalty (reduce probability) -- rejected by user preference for hard gate.
- Accept NEUTRAL as "no opinion" -- rejected by user; LSTM must confirm.

**Configuration**: `PREDICTION_AGREEMENT_ENABLED` (bool, default `true`) added to `AppConfig`. When disabled, the gate is bypassed for backward compatibility.

---

## R4: Entry vs Support/Resistance Warning

**Decision**: Log-only warning in `core/scheduler.py` when SELL entry < support or BUY entry > resistance. No hard rejection.

**Rationale**: XGBoost already receives `price_vs_support` and `price_vs_resistance` features (signal_agent.py:140-143). A hard rejection could filter valid momentum trades. Break+retest detection requires multi-bar state tracking, which is architecturally complex for a monitoring-only feature.

**Alternatives considered**:
- Hard rejection -- too aggressive; would filter valid breakout momentum trades.
- Break+retest detection -- architecturally complex, deferred to a future feature.

---

## R5: Multi-Timeframe Trend Confirmation

**Decision**: Add `ChartAgent.get_trend_consensus(exclude_timeframe)` method querying `self._analyses` dict (chart_agent.py:76). Call from scheduler before `process_signal()`. Require at least N timeframes (default 2) to agree on trend direction.

**Rationale**: `ChartAgent._analyses` already persists across cycles (instance-level dict set at line 76, stored at line 102). Each timeframe's `TimeframeAnalysis` contains `indicators.trend_direction` ("bullish"/"bearish"/"neutral"). This data is readily queryable for cross-timeframe consensus.

**Graceful degradation**: On cold start (not all timeframes analyzed yet), allow signals through. Only enforce when enough timeframes have data.

**Configuration**: `MTF_CONFIRMATION_ENABLED` (bool, default `true`), `MTF_MIN_AGREEING_TIMEFRAMES` (int, default `2`).

**Alternatives considered**:
- Weighted timeframe voting (higher TF = more weight) -- adds complexity, simple count is sufficient for initial implementation.
- Blocking until all 4 timeframes analyzed -- too aggressive on cold start.

---

## R6: Opportunity Score Gate

**Decision**: New `OpportunityScore` dataclass in `core/types.py`. Computed in `signal_agent.py:decide()` after prediction agreement check. If below threshold, return NO_TRADE.

**Rationale**: The existing `ClarityScore` (types.py:243-268) only combines 3 components (indicator_agreement, pattern_confidence, data_completeness) and is never used as a gate. The `OpportunityScore` combines 7 components for a more comprehensive quality assessment.

**Weights**:
```
0.20 x trend_strength     -- from PricePrediction.trend_strength
0.15 x volatility_regime   -- ATR-normalized, favorable = moderate volatility
0.15 x pattern_confidence  -- strongest pattern confidence
0.15 x prediction_confidence -- LSTM confidence
0.10 x sentiment_alignment -- does sentiment agree with signal direction?
0.15 x indicator_agreement -- from ClarityScore
0.10 x mtf_agreement      -- fraction of agreeing timeframes
```

**Configuration**: `OPPORTUNITY_SCORE_ENABLED` (bool, default `true`), `OPPORTUNITY_SCORE_THRESHOLD` (float, default `0.55`).

**Alternatives considered**:
- Extending existing ClarityScore -- rejected because ClarityScore has a fixed 3-component formula used elsewhere; adding 4 more components would break existing behavior.
- ML-based quality scoring -- over-engineered for this use case; static weights are interpretable and tunable.

---

## R7: Improved Telegram Signal Format

**Decision**: Redesign `format_trade_signal()` in `execution/signal_generator.py:91-106` to include R:R ratio, stop/TP distances, position size unit, market context (trend, pattern, RSI, MACD), and AI analysis section.

**Rationale**: Current format lacks R:R ratio, market context, and position size unit clarification. Users cannot assess trade quality from the message alone.

**Additional parameters needed**: The function currently receives `(signal, risk)`. New format requires: indicators (trend_direction, RSI, MACD), patterns_summary (strongest pattern), and opportunity_score. These will be passed via keyword arguments with defaults for backward compatibility.

**Alternatives considered**:
- Separate "detailed" and "brief" formats -- adds complexity; one well-designed format is sufficient.
- HTML/Markdown Telegram formatting -- keep plain text for now; all Telegram clients render it consistently.

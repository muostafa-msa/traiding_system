# Feature Specification: Signal Quality Filtering Improvements

**Feature Branch**: `006-signal-quality-filters`
**Created**: 2026-04-07
**Status**: Draft
**Input**: Improve signal quality by reducing Telegram noise, filtering contradictory patterns, enforcing model agreement, adding multi-timeframe confirmation, implementing an opportunity score gate, and improving signal message format.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Reduce Telegram Noise (Priority: P1)

As a trader monitoring my Telegram channel, I only want to receive messages when an actionable trade signal is generated. I should not receive technical analysis summaries every few minutes, as they create noise and make it hard to identify real trade signals.

**Why this priority**: The highest user-facing annoyance. Currently ~17 analysis messages/hour drown out actual signals. Fixing this immediately improves the user experience.

**Independent Test**: Verify that running the system for multiple cycles produces zero Telegram messages unless an approved trade signal is generated.

**Acceptance Scenarios**:

1. **Given** the system is running with 4 timeframes, **When** a cycle completes without generating a trade signal, **Then** no Telegram message is sent.
2. **Given** the system generates an approved trade signal, **When** the signal passes all quality gates, **Then** exactly one Telegram message is sent with the signal details.
3. **Given** a user sends `/status` to the bot, **Then** the bot still responds with system status (commands are unaffected).

---

### User Story 2 - Coherent Pattern Detection (Priority: P1)

As a trader, I expect the system to identify a single dominant market pattern rather than reporting contradictory patterns simultaneously (e.g., double_top and double_bottom at the same time). Contradictory patterns indicate a detection bug and undermine confidence in the system's analysis.

**Why this priority**: Contradictory patterns feed conflicting signals to the scoring model, directly degrading signal accuracy. This is a correctness issue.

**Independent Test**: Feed historical bar data known to produce a double top pattern and verify only BUY-aligned or NEUTRAL patterns remain; SELL-direction patterns are filtered out when the strongest pattern is BUY-direction.

**Acceptance Scenarios**:

1. **Given** the pattern detector identifies both a double_top (SELL, 86%) and double_bottom (BUY, 98%), **When** patterns are filtered, **Then** only the double_bottom (strongest, BUY) and any NEUTRAL patterns remain. The double_top is removed.
2. **Given** the pattern detector identifies only NEUTRAL patterns (range, triangle), **When** patterns are filtered, **Then** all NEUTRAL patterns are preserved.
3. **Given** only one pattern is detected, **When** filtering runs, **Then** that single pattern is preserved unchanged.

---

### User Story 3 - Prediction Model Agreement (Priority: P1)

As a system operator, I want the trading system to reject trade signals when the LSTM prediction model disagrees with or does not confirm the signal direction. If the technical analysis says SELL but the LSTM model predicts NEUTRAL or BUY, the system should not trade.

**Why this priority**: Trading against the system's own prediction model is fundamentally inconsistent. Enforcing model agreement significantly reduces false signals.

**Independent Test**: Generate a SELL signal from indicators with an LSTM prediction of NEUTRAL or BUY, and verify the system rejects the trade.

**Acceptance Scenarios**:

1. **Given** indicators produce a SELL signal, **When** the LSTM prediction is BUY, **Then** the signal is rejected as NO_TRADE.
2. **Given** indicators produce a BUY signal, **When** the LSTM prediction is NEUTRAL, **Then** the signal is rejected as NO_TRADE.
3. **Given** indicators produce a SELL signal, **When** the LSTM prediction is SELL, **Then** the signal proceeds normally through the pipeline.
4. **Given** the prediction agreement feature is disabled via configuration, **When** any signal is generated, **Then** prediction agreement is not checked.

---

### User Story 4 - Multi-Timeframe Trend Confirmation (Priority: P2)

As a trader, I want the system to only generate signals when multiple timeframes agree on the market direction. A 5-minute SELL signal should not be sent if the 1-hour trend is bullish.

**Why this priority**: Cross-timeframe confirmation is a well-established practice in professional trading. It significantly reduces false signals from short-term noise.

**Independent Test**: Analyze bars across multiple timeframes where 5m is bearish but 1h is bullish, and verify the 5m SELL signal is rejected.

**Acceptance Scenarios**:

1. **Given** the 5m trend is bearish and the 15m trend is also bearish, **When** a 5m SELL signal is generated, **Then** the signal proceeds (2 timeframes agree).
2. **Given** the 5m trend is bearish but the 1h and 4h trends are bullish, **When** a 5m SELL signal is generated, **Then** the signal is rejected (only 1 timeframe agrees, minimum is 2).
3. **Given** the system just started and only the 5m timeframe has been analyzed, **When** a 5m signal is generated, **Then** the signal proceeds (graceful degradation when not enough timeframes have data yet).
4. **Given** multi-timeframe confirmation is disabled via configuration, **When** any signal is generated, **Then** the confirmation check is skipped.

---

### User Story 5 - Trade Opportunity Score Gate (Priority: P2)

As a system operator, I want a composite "opportunity score" that evaluates overall trade quality before a signal is sent. This score should combine trend strength, volatility conditions, pattern confidence, prediction confidence, sentiment alignment, indicator agreement, and multi-timeframe agreement into a single metric with a configurable threshold.

**Why this priority**: Individual quality checks may pass while the overall setup is still weak. A composite score catches trades that pass individual gates but lack overall conviction.

**Independent Test**: Create scenarios with varying input quality levels and verify that signals below the threshold are rejected while signals above pass through.

**Acceptance Scenarios**:

1. **Given** all quality components are strong (high trend strength, good pattern, LSTM agrees, sentiment aligned, MTF agrees), **When** the opportunity score is computed, **Then** it exceeds the threshold (0.55) and the signal proceeds.
2. **Given** indicators are mixed (weak pattern, low trend strength, no sentiment), **When** the opportunity score is computed, **Then** it falls below the threshold and the signal is rejected.
3. **Given** the opportunity score feature is disabled via configuration, **When** any signal is generated, **Then** the opportunity score gate is skipped.

---

### User Story 6 - Improved Signal Message Format (Priority: P3)

As a trader receiving Telegram signal notifications, I want the message to include the risk-to-reward ratio, stop/take-profit distance in price units, position size with unit clarification, market context (trend, pattern, key indicators), and an AI-generated analysis section.

**Why this priority**: Presentation improvement that makes signals more actionable. Lower priority than the filtering logic but important for user experience.

**Independent Test**: Generate a signal and verify the Telegram message contains all required fields in the expected format.

**Acceptance Scenarios**:

1. **Given** a SELL signal is generated, **When** the Telegram message is formatted, **Then** it includes: direction, entry, SL with distance, TP with distance, R:R ratio, position size in ounces with approximate dollar risk, confidence percentage, trend direction, strongest pattern with confidence, RSI value, MACD direction, and AI analysis text.
2. **Given** no pattern is detected, **When** the message is formatted, **Then** the pattern line shows "None detected" instead of being omitted.

---

### User Story 7 - Entry vs Support/Resistance Warning (Priority: P3)

As a system operator reviewing logs, I want to see a warning when a SELL signal entry price is below support or a BUY signal entry is above resistance. This helps identify potential breakout-already-happened situations during post-trade review.

**Why this priority**: Informational logging only. Does not affect signal generation but aids monitoring and system tuning.

**Independent Test**: Generate a SELL signal where entry < support and verify a warning appears in the log file.

**Acceptance Scenarios**:

1. **Given** a SELL signal with entry price below support, **When** the signal is generated, **Then** a warning log is emitted stating entry is below support.
2. **Given** a BUY signal with entry price above resistance, **When** the signal is generated, **Then** a warning log is emitted stating entry is above resistance.
3. **Given** a signal where entry is between support and resistance, **When** the signal is generated, **Then** no warning is emitted.

---

### Edge Cases

- What happens on cold start when only one timeframe has been analyzed? Multi-timeframe confirmation degrades gracefully and allows signals through.
- What happens when all patterns are NEUTRAL direction? No filtering occurs; all NEUTRAL patterns are preserved.
- What happens when the LSTM model is not loaded (failed to load weights)? The prediction agreement gate is bypassed when the LSTM is unavailable, falling back to existing behavior.
- What happens when the opportunity score components have missing data (e.g., no sentiment feed configured)? Missing components default to 0.0 for their contribution, and the score is computed from available data.
- What happens when all new quality gates are disabled via configuration? The system behaves identically to the current version with no regressions.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST NOT broadcast technical analysis indicator summaries to Telegram. Only approved trade signals are broadcast.
- **FR-002**: System MUST continue logging indicator summaries to log files for debugging purposes.
- **FR-003**: System MUST filter contradictory patterns by removing patterns whose direction opposes the strongest detected pattern's direction. NEUTRAL-direction patterns are always preserved.
- **FR-004**: System MUST reject trade signals when the LSTM prediction direction does not match the signal direction (including NEUTRAL predictions).
- **FR-005**: System MUST provide a configuration option to enable or disable the prediction agreement gate.
- **FR-006**: System MUST check trend direction agreement across multiple analyzed timeframes before allowing a signal, requiring a configurable minimum number of agreeing timeframes (default: 2).
- **FR-007**: System MUST allow signals through when insufficient timeframe data exists (cold start graceful degradation).
- **FR-008**: System MUST provide a configuration option to enable or disable multi-timeframe confirmation.
- **FR-009**: System MUST compute a composite opportunity score from trend strength, volatility regime, pattern confidence, prediction confidence, sentiment alignment, indicator agreement, and multi-timeframe agreement.
- **FR-010**: System MUST reject signals whose opportunity score falls below a configurable threshold (default: 0.55).
- **FR-011**: System MUST provide a configuration option to enable or disable the opportunity score gate.
- **FR-012**: Trade signal Telegram messages MUST include: direction, entry price, stop loss with distance, take profit with distance, risk-to-reward ratio, position size with unit and approximate risk in dollars, confidence, trend direction, strongest pattern with confidence, RSI value, MACD direction, and AI-generated analysis.
- **FR-013**: System MUST log a warning when a SELL signal entry is below support or a BUY signal entry is above resistance.
- **FR-014**: All new quality gates MUST be independently configurable (enable/disable) so the system can be tuned without code changes.

### Key Entities

- **OpportunityScore**: A composite quality metric combining 7 weighted components (trend strength, volatility regime, pattern confidence, prediction confidence, sentiment alignment, indicator agreement, multi-timeframe agreement) into a single score between 0.0 and 1.0.
- **PatternDetectionResult** (existing, modified): List of detected patterns filtered to remove directionally contradictory patterns. Retains strongest_confidence and strongest_direction from the highest-confidence non-conflicting pattern.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Telegram message volume decreases by at least 90% (from ~17 analysis messages per hour to only approved trade signals).
- **SC-002**: Zero instances of contradictory patterns (opposing BUY and SELL direction patterns) appearing simultaneously in pattern detection output.
- **SC-003**: Zero trade signals generated where the LSTM prediction direction disagrees with the signal direction (when prediction agreement is enabled).
- **SC-004**: 100% of generated signals have at least the configured minimum number of timeframes agreeing on trend direction (when multi-timeframe confirmation is enabled and sufficient timeframe data exists).
- **SC-005**: 100% of generated signals have an opportunity score at or above the configured threshold (when the opportunity score gate is enabled).
- **SC-006**: All existing system tests continue to pass with new features enabled at their default configuration values.

## Assumptions

- The LSTM prediction model produces meaningful directional predictions (BUY/SELL/NEUTRAL). If the model consistently outputs NEUTRAL, the prediction agreement gate will effectively block all trades, which is the intended conservative behavior.
- The existing chart analysis state persists across scheduler cycles because the chart analysis component is instantiated once at system startup. This is leveraged for multi-timeframe consensus queries.
- The market data provider continues to provide OHLC data without bid/ask spread information. Spread filtering is excluded from scope.
- Position sizing is already correctly implemented as risk-based sizing in troy ounces. No changes to position sizing logic are needed.
- All new configuration parameters have sensible defaults that enable the new features, so the system immediately benefits from improved filtering upon deployment.
- The system's existing 4-timeframe architecture (5m, 15m, 1h, 4h) provides sufficient timeframe diversity for meaningful cross-timeframe confirmation.

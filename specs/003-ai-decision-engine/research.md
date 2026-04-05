# Research: AI Decision Engine (003)

**Date**: 2026-03-30 | **Status**: Complete

## R1: LSTM Architecture for Financial Time Series

**Decision**: Single-layer LSTM with 64 hidden units, sequence length 60, dropout 0.2

**Rationale**: Financial time series prediction does not benefit from deep LSTM stacks due to noise-to-signal ratio. A single-layer LSTM with moderate hidden size balances learning capacity with overfitting risk. Sequence length of 60 (≈60 candles) captures intra-day patterns on 1h timeframe without excessive memory. Dropout 0.2 provides regularization without excessive information loss.

**Alternatives considered**:
- GRU (simpler, similar performance on financial data) — rejected for consistency with constitution specification of LSTM
- Transformer encoder (attention-based) — rejected due to higher memory/compute requirements conflicting with local-first constraint
- Multi-layer LSTM (2-3 layers) — rejected because deeper networks overfit more on noisy financial data without significant accuracy gains

**Input features** (per timestep): OHLC prices (4), RSI (1), MACD line/signal/histogram (3), EMA 20/50/200 (3), BB upper/middle/lower (3), ATR (1) = **15 features**

**Output**: 3 values — direction logit (sigmoid → BUY/SELL/NEUTRAL), volatility estimate (normalized), trend strength (0-1)

**Training approach**: Walk-forward cross-validation with 80/20 expanding window. Minimum training window: 6 months of 1h candles (≈4,380 bars). Adam optimizer, lr=0.001, batch_size=32, max 100 epochs with early stopping (patience=10).

## R2: XGBoost Feature Engineering and Training

**Decision**: XGBoost binary classifier with ~25 tabular features, walk-forward cross-validation

**Rationale**: XGBoost excels at tabular data with mixed feature types. Binary classification (BUY/SELL probability) with calibrated probabilities via Platt scaling. Constitution specifies XGBoost for probability scoring.

**Alternatives considered**:
- LightGBM (slightly faster training) — rejected for consistency with constitution
- Random Forest (simpler, less prone to overfitting) — rejected because XGBoost handles feature interactions better
- Neural network ensemble — rejected due to complexity and local-first compute constraints

**Feature vector composition** (~25 features):
- Technical indicators: RSI, MACD (3 components), EMA ratios (close/EMA20, close/EMA50, close/EMA200), BB position, ATR normalized (9)
- Pattern detections: breakout, triangle, double_top, double_bottom, head_shoulders, range confidences (6)
- Sentiment: macro_score, headline_count, is_blackout flag (3)
- LSTM prediction: direction, confidence, volatility, trend_strength (4)
- Derived: indicator_agreement_ratio, trend_direction_encoded, price_vs_support, price_vs_resistance (4)

**Training approach**: Walk-forward CV with minimum 6 months training window. Hyperparameters: max_depth=6, n_estimators=200, learning_rate=0.1, subsample=0.8. Probability calibration via CalibratedClassifierCV.

## R3: GPT-OSS-20B for Signal Explanation (via Ollama)

**Decision**: `openai/gpt-oss-20b` (21B total params, 3.6B active MoE) served locally via Ollama

**Rationale**: GPT-OSS-20B is OpenAI's open-weight MoE model (Apache 2.0). With only 3.6B active parameters per token it delivers strong reasoning quality at practical latency. Running via Ollama decouples model management from the trading system — Ollama handles loading, quantization, and memory, while our code makes simple HTTP calls to `localhost:11434`. This eliminates the need for `transformers` pipeline loading and in-process VRAM management.

**Alternatives considered**:
- gpt2-medium (355M) — rejected because output quality is too low for structured financial reasoning
- gpt2-xl (1.5B) — rejected for same quality concerns
- LLaMA/Mistral quantized via transformers — rejected because Ollama provides a simpler, more maintainable integration path
- Direct transformers loading of GPT-OSS-20B — rejected because Ollama handles quantization, memory, and serving more efficiently than in-process loading

**Prompt template structure**:
```
Market Analysis Summary:
Asset: XAU/USD | Direction: {direction} | Confidence: {probability:.0%}
Technical: {trend_direction} trend, RSI={rsi:.0f}, MACD {macd_signal}
Patterns: {patterns_summary}
Sentiment: {sentiment_summary} (score: {macro_score:+.2f})
Prediction: {prediction_direction} with {prediction_confidence:.0%} confidence

Explain why this is a {direction} opportunity:
```

**Max generation length**: 150 tokens (approximately 2-3 sentences). Temperature: 0.7 for variety with coherence.

**Integration**: HTTP POST to Ollama `/api/generate` endpoint. Model name configurable via `OLLAMA_MODEL` env var (default: `gpt-oss:20b`). Timeout: 30 seconds. Ollama must be running separately (`ollama serve`).

## R4: Pattern Detection Algorithm Design

**Decision**: Rule-based detectors using swing point analysis on OHLC data

**Rationale**: Constitution §8 specifies "initial implementation must be rule-based." Rule-based detectors are deterministic, testable, and require no training data. Each pattern returns a confidence score 0.0-1.0 based on how closely the price action matches the ideal pattern geometry.

**Pattern definitions**:
- **Breakout**: Price closes above resistance (or below support) with volume confirmation. Confidence based on magnitude of break vs ATR.
- **Triangle**: Converging trendlines (higher lows + lower highs) over minimum 10 bars. Confidence based on number of touches and convergence tightness.
- **Double top/bottom**: Two peaks (or troughs) within 2% of each other, separated by at least 10 bars. Confidence based on price symmetry and volume pattern.
- **Head and shoulders**: Three peaks with middle highest, neckline break. Confidence based on symmetry of shoulders and neckline penetration.
- **Trading range**: Price oscillating between support and resistance for 20+ bars. Confidence based on number of touches and range tightness.

**Lookback window**: 50 bars minimum for pattern detection. Swing point detection uses n=5 (5 bars each side).

## R5: Clarity Score Computation

**Decision**: Weighted composite of three factors: indicator agreement (50%), pattern confidence (30%), data completeness (20%)

**Rationale**: Indicator agreement is weighted highest because it reflects the broadest consensus of market state. Pattern confidence provides signal-specific support. Data completeness penalizes timeframes with missing candles that could produce unreliable analysis.

**Indicator agreement calculation**: Count of indicators agreeing with the majority direction divided by total indicators. Indicators considered: RSI direction (>50 bullish, <50 bearish), MACD histogram sign, EMA alignment (20>50>200 bullish), BB position (above middle bullish). Range: 0.0 to 1.0.

**Pattern confidence**: Maximum confidence among all detected patterns for that timeframe. Range: 0.0 to 1.0. If no patterns detected, defaults to 0.0.

**Data completeness**: `1.0 - (missing_bars / expected_bars)`. A timeframe with no gaps scores 1.0. Any gap reduces the score proportionally.

## R6: Weighted Formula Fallback

**Decision**: Linear combination with configurable weights, defaults: indicators=0.30, patterns=0.20, sentiment=0.25, prediction=0.25

**Rationale**: Equal-ish weighting provides a balanced baseline when XGBoost is unavailable. Indicators weighted slightly higher because they are always available (unlike prediction or sentiment which may use neutral defaults). These weights are configurable so the operator can tune them based on observed performance.

**Formula**: `probability = (0.30 * indicator_score) + (0.20 * max_pattern_confidence) + (0.25 * abs(macro_score)) + (0.25 * prediction_confidence)`

Where:
- `indicator_score` = clarity score indicator agreement component (0.0-1.0)
- `max_pattern_confidence` = highest pattern confidence (0.0-1.0)
- `abs(macro_score)` = absolute value of sentiment macro score, clamped to 0.0-1.0
- `prediction_confidence` = LSTM prediction confidence (0.0-1.0), defaults to 0.0 if unavailable

**Direction determination** (fallback): Majority vote of indicator trend direction, LSTM prediction direction, and sentiment polarity (positive→BUY, negative→SELL). Ties → NO_TRADE.

## R7: Model Memory Management

**Decision**: Sequential model loading with unloading between inference types; GPT-OSS-20B offloaded to Ollama

**Rationale**: With in-process models (FinBERT ~1GB + LSTM ~200MB + XGBoost ~100MB = ~1.3GB), memory is manageable. GPT-OSS-20B runs as a separate Ollama process (~16GB managed by Ollama), keeping the trading system's memory footprint low. The existing ModelManager handles FinBERT/LSTM/XGBoost; explanation generation is a simple HTTP call to Ollama.

**Loading order per cycle**: LSTM → unload → XGBoost (kept in memory, small) → if threshold met: HTTP call to Ollama for explanation (no in-process loading). FinBERT is loaded by the news agent separately.

**Alternatives considered**:
- Load GPT-OSS-20B in-process via transformers — rejected because Ollama manages memory and quantization more efficiently
- Keep all models in memory — rejected due to RAM constraints for in-process models

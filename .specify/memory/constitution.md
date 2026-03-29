<!--
  Sync Impact Report
  ==================
  Version change: 1.0.0 → 1.1.0
  Modified principles:
    - Replaced "AI Decision Engine" (generic LLM/statistical) with specific model architecture (FinBERT, LSTM, XGBoost, GPT-2B OSS)
    - Added "Local-First Architecture" as a new core constraint
  Added sections:
    - Section 2: Local-First Architecture (CPU/GPU, offline, low memory)
    - Section 4-6: AI Model Architecture with FinBERT, LSTM, XGBoost, GPT-2B OSS
    - Section 6: Model Pipeline (specific data flow through models)
    - Section 13: Backtesting (explicit vectorbt/backtrader)
    - Section 17: Scalability roadmap
  Removed sections:
    - Generic "AI Decision Engine" description (replaced by specific models)
    - LLM abstraction for sentiment (OpenAI/Claude/keyword) — replaced by FinBERT
  Templates requiring updates:
    - .specify/templates/plan-template.md — needs model architecture section
    - specs/001-core-system-risk/plan.md — Phase 1 unaffected (no ML models)
    - docs/implementation_plan.md — Phase 2 (FinBERT), Phase 3 (XGBoost/LSTM/GPT-2B), tech stack
  Follow-up TODOs:
    - Update implementation_plan.md Phase 2 and Phase 3
    - Update requirements.txt when ML phases begin
    - Add models/ package to project structure
-->

# AI Market Intelligence & Trading Signal System Constitution

**Version**: 1.1.0 | **Ratified**: 2026-03-26 | **Last Amended**: 2026-03-28

## 1. Purpose

This constitution defines the core principles, architecture rules, development
workflow, and safety constraints for the AI Market Intelligence System.

The system analyzes financial markets and generates probability-based trading
signals by combining:

- Technical market analysis
- Financial news sentiment analysis
- Machine learning prediction models
- Strict risk management

The system initially focuses on **XAU/USD (Gold)** and later expands to
**forex and stocks**.

The system must be able to **run entirely on a local computer** without
requiring cloud infrastructure.

## 2. Local-First Architecture

The system must be designed to operate **fully locally on a personal computer**.

All models must be able to run **offline** after initial installation.

The system must avoid dependencies that require permanent cloud services.

The architecture must support:

- CPU execution
- Optional GPU acceleration if available
- Low memory usage where possible

Local components include:

- Market data collector
- ML inference models
- Signal engine
- Database storage
- Telegram interface

External APIs are allowed only for **market data and news retrieval**.

## 3. Core System Objectives

The system must:

1. Monitor financial markets in near real-time
2. Analyze price charts using technical indicators
3. Analyze financial news and social sentiment
4. Predict market direction probabilities
5. Generate BUY or SELL signals when high-probability opportunities appear
6. Apply strict risk management rules
7. Deliver signals via Telegram
8. Track signal performance
9. Support historical backtesting and strategy optimization

The system prioritizes **signal accuracy and risk control over signal frequency**.

## 4. AI Model Architecture

The system uses a **hybrid multi-model intelligence architecture**.

Each model has a specialized role.

The selected models are:

- **FinBERT** — financial sentiment analysis
- **XGBoost** — signal probability scoring
- **LSTM** — market time series prediction
- **GPT-2B OSS** — reasoning and signal explanation

These models operate together to generate trading signals.

## 5. Model Responsibilities

### 5.1 FinBERT — Financial Sentiment Analysis

FinBERT is responsible for analyzing financial text.

Inputs:

- Financial news
- Twitter/X posts
- Macroeconomic headlines

Outputs:

- Sentiment classification (Bullish, Bearish, Neutral)
- Confidence score

FinBERT is used because it is specifically trained on **financial language**.

### 5.2 LSTM — Market Time Series Prediction

LSTM models analyze historical market data.

Inputs:

- OHLC price data
- Technical indicators
- Volatility measures

Outputs:

- Predicted price direction
- Predicted volatility
- Trend strength

The LSTM learns patterns in historical price behavior.

Typical prediction horizon: 5–30 candles.

### 5.3 XGBoost — Signal Probability Model

XGBoost is responsible for **combining multiple signals into a probability
score**.

Inputs:

- Indicator values
- Pattern detection results
- Sentiment score
- LSTM prediction
- Volatility metrics

Output:

- Probability that the market will move in a given direction

XGBoost is used because it performs extremely well on **tabular financial data**.

### 5.4 GPT-2B OSS — Reasoning and Signal Explanation

The GPT-2B model is used for:

- Reasoning about signals
- Explaining trade decisions
- Generating human-readable signal summaries

Inputs:

- Indicator analysis
- Sentiment results
- Probability model output

Outputs:

- Trade explanation text

GPT-2B is not used for raw prediction but for **interpretation and explanation**.

## 6. Model Pipeline

The AI pipeline operates as follows:

```
Market Data → Technical Indicators → Pattern Detection
News Data   → FinBERT Sentiment Analysis
Market Data → LSTM Prediction

All features → XGBoost Probability Model

If probability exceeds threshold:
  → GPT-2B generates explanation
  → Risk Manager evaluates trade
  → Telegram signal is sent
```

## 7. Technical Analysis Engine

Indicators required:

- RSI, MACD, EMA (20, 50, 200), Bollinger Bands, ATR

The system must also compute:

- Support levels
- Resistance levels
- Trend strength
- Breakout signals

All indicators MUST use reproducible mathematical logic.

## 8. Pattern Detection

The system must detect common market patterns.

Supported patterns include:

- Breakouts
- Triangles
- Double tops
- Double bottoms
- Head and shoulders
- Range trading

Initial implementation must be rule-based.

## 9. Risk Management

Risk rules are mandatory. Risk management MUST be applied to every signal
without exception.

Non-negotiable rules:

- Maximum risk per trade: **1% of capital**
- Maximum daily risk: **3% of capital**
- Maximum simultaneous open positions: **2**
- Stop loss formula: **Entry − 1.5 × ATR**
- Take profit must satisfy: **Risk Reward ≥ 1.8**

Any signal that violates these rules MUST be rejected. There are no overrides
for risk rules.

## 10. Safety Controls

The system must implement and enforce these safety mechanisms at all times:

- **Kill switch**: automatically disable signal generation if daily losses
  exceed **5%**
- **Position limits**: enforce the 2-position maximum at system level
- **Economic event protection**: trading should be paused during major
  macroeconomic announcements (Fed announcements, Non-Farm Payroll, CPI reports)

Safety controls MUST NOT be bypassed during normal operation.

## 11. Signal Delivery

Signals must be delivered via Telegram.

Each signal must include:

- Asset
- Direction (BUY or SELL)
- Entry price
- Stop Loss
- Take Profit
- Confidence score
- Explanation

The Telegram bot MUST support commands:

- `/status` — system health
- `/last_signal` — most recent signal
- `/performance` — tracked metrics
- `/kill` — emergency stop

The bot MUST broadcast signals automatically when generated. Commands MUST
only be accepted from the configured chat ID.

## 12. Performance Tracking

The system must track signal performance.

Metrics include:

- Total signals
- Win rate
- Profit factor
- Maximum drawdown
- Average reward/risk

Data must be stored locally in **SQLite**.

## 13. Backtesting

The system must support historical backtesting.

Backtesting must evaluate:

- Profitability
- Risk metrics
- Drawdown
- Strategy stability

Backtesting libraries: **vectorbt**, **backtrader**.

## 14. Technology Stack

The system must be implemented in Python.

Required libraries:

- pandas, numpy, ta
- scikit-learn, xgboost
- torch, transformers
- requests, feedparser
- apscheduler, python-telegram-bot
- vectorbt
- python-dotenv

The system must run on a **local machine** with optional GPU acceleration.

## 15. Execution Loop

The system must run on a scheduled loop.

Recommended frequency: every 5 minutes, with per-timeframe intervals
(5min/15min/1h/4h).

Typical cycle:

1. Collect market data
2. Compute indicators
3. Detect patterns
4. Collect news
5. Run FinBERT sentiment
6. Run LSTM prediction
7. Compute XGBoost probability
8. Apply risk management
9. Generate signal (GPT-2B explanation if approved)
10. Send Telegram alert
11. Log performance

## 16. Development Workflow

Development follows a **spec-driven architecture**.

Roles:

- **Claude** — architecture planning and review
- **GLM5** — implementation of specifications

Workflow:

1. Specifications created
2. Tasks generated
3. GLM5 writes code
4. Claude reviews logic and architecture
5. Testing and validation

### Quality Gates

- Every agent MUST have unit tests
- Integration tests MUST verify agent-to-agent data flow
- Risk management rules MUST be validated with edge-case tests
- Backtesting MUST pass before strategy changes are accepted

## 17. Scalability

The architecture must support future upgrades:

- Multi-asset trading
- Portfolio management
- Reinforcement learning strategies
- Semi-automatic trade execution
- Cloud deployment

## 18. Guiding Principles

1. **Signal quality is more important than signal frequency**
2. **Risk management is mandatory — no exceptions**
3. **All trade decisions must be explainable**
4. **The system must remain modular and extensible**
5. **Local execution must always be supported**
6. **Spec-driven development — no ad-hoc coding**
7. **Traceability from raw data to final signal**

## Governance

This constitution is the highest-authority document for the AI Market
Intelligence & Trading Signal System. All specifications, plans, and
implementations MUST comply with the principles defined here.

### Amendment Procedure

1. Propose the change with rationale
2. Evaluate impact on existing agents and specifications
3. Update the constitution with a version bump
4. Propagate changes to dependent templates and specs
5. Document the change in the Sync Impact Report

### Versioning Policy

- **MAJOR**: removal or redefinition of a core principle
- **MINOR**: new principle or materially expanded guidance
- **PATCH**: clarifications, wording, non-semantic refinements

### Compliance

All code reviews and PRs MUST verify compliance with this constitution.
Non-compliant implementations MUST be flagged and corrected before merge.

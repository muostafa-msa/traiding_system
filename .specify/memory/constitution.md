<!--
  Sync Impact Report
  ==================
  Version change: N/A (initial) → 1.0.0
  Modified principles: N/A (initial creation)
  Added sections:
    - 6 Core Principles
    - System Architecture & Technical Requirements
    - Risk Management & Safety Controls
    - Development Workflow & Execution
    - Governance
  Removed sections: N/A
  Templates requiring updates:
    - .specify/templates/plan-template.md — ✅ compatible (Constitution Check section exists)
    - .specify/templates/spec-template.md — ✅ compatible (no constitution-specific refs)
    - .specify/templates/tasks-template.md — ✅ compatible (phase structure supports agent tasks)
    - .specify/templates/commands/*.md — ✅ no command files exist yet
  Follow-up TODOs: None
-->

# AI Market Intelligence & Trading Signal System Constitution

## Core Principles

### I. Signal Quality Over Frequency

Every trading signal MUST meet a minimum probability threshold before
generation. The system MUST NOT generate signals to fill a quota or
maintain activity. Fewer high-confidence signals are always preferred
over many low-confidence ones. All signals MUST include a confidence
score and reasoning summary. Signals below threshold MUST be silently
discarded.

### II. Modular Multi-Agent Architecture

The system MUST be composed of specialized, single-responsibility agents:

- **Market Data Agent** — collects price data from external APIs
- **Chart Analysis Agent** — computes technical indicators (RSI, MACD,
  EMA 20/50/200, Bollinger Bands, ATR)
- **Pattern Detection Agent** — identifies chart patterns (breakout,
  triangle, double top/bottom, head and shoulders, trading ranges)
- **News Agent** — collects financial news and RSS feeds
- **Sentiment Analysis Agent** — classifies news sentiment (Bullish,
  Bearish, Neutral) with confidence scores
- **Signal Decision Agent** — combines all inputs into a probabilistic
  trade decision
- **Risk Management Agent** — enforces position sizing, stop loss, and
  risk-reward rules
- **Signal Delivery Agent** — formats and sends signals via Telegram
- **Performance Tracking Agent** — records outcomes and computes metrics

Each agent MUST communicate through structured data interfaces. Agents
MUST NOT create circular dependencies. Each agent MUST be independently
testable.

### III. Mandatory Risk Management

Risk management MUST be applied to every signal without exception.

Non-negotiable rules:

- Maximum risk per trade: **1% of capital**
- Maximum daily risk: **3% of capital**
- Maximum simultaneous open positions: **2**
- Stop loss formula: **Entry − 1.5 × ATR**
- Minimum risk-reward ratio: **1.8:1**

Any signal that violates these rules MUST be rejected. There are no
overrides for risk rules.

### IV. Safety Controls Always Active

The system MUST implement and enforce these safety mechanisms at all
times:

- **Kill switch**: automatically disable signal generation if daily loss
  exceeds **5%**
- **Position limits**: enforce the 2-position maximum at system level
- **News blackout**: suppress trading during major macroeconomic events
  (Fed announcements, Non-Farm Payroll, CPI reports)

Safety controls MUST NOT be bypassed during normal operation.

### V. Traceability and Explainability

Every trading decision MUST be traceable from raw data to final signal.
Each signal MUST include:

- Asset and direction (BUY/SELL)
- Entry price, stop loss, take profit
- Confidence score (probability)
- Reasoning summary explaining why the signal was generated

Performance MUST be tracked with: total signals, win rate, profit factor,
drawdown, and strategy accuracy. All performance data MUST be persisted
in SQLite.

### VI. Spec-Driven Development

All development MUST follow a specification-first workflow:

1. Specifications are created and reviewed
2. Implementation tasks are generated from specs
3. Code is written against the specification
4. Architecture and logic are reviewed
5. Tests validate the implementation

No feature or agent MUST be implemented without a prior specification.
The constitution supersedes ad-hoc decisions.

## System Architecture & Technical Requirements

### Asset Scope

- **Initial asset**: XAU/USD (Gold vs USD)
- **Future expansion**: major forex pairs, selected stocks
- The system MUST be designed to scale to at least **10 monitored assets**

### Data Sources

Market data providers (one or more of):

- TwelveData
- Polygon
- AlphaVantage

News sources:

- Twitter/X
- Financial news APIs
- RSS feeds

News collection MUST prioritize: gold, inflation, interest rates, US
dollar, geopolitical events.

### Technical Analysis

Minimum required indicators:

- RSI, MACD, EMA (20/50/200), Bollinger Bands, ATR

The system MUST also estimate:

- Support and resistance levels
- Trend direction
- Breakout probability

All indicators MUST use reproducible mathematical logic.

### Pattern Detection

Initial supported patterns (rule-based):

- Breakout, triangle formations, double top/bottom, head and shoulders,
  trading ranges

Future versions may introduce ML or computer vision models.

### AI Decision Engine

The decision engine MUST combine:

- Technical indicator signals
- Pattern detection results
- Sentiment analysis
- Market volatility

The AI reasoning layer may use LLM reasoning, statistical scoring, or
weighted indicator models. Precision and risk control MUST take priority
over signal frequency.

### Signal Format

Every signal MUST contain: asset, direction, entry price, stop loss,
take profit, confidence score, and reasoning summary. Formatting MUST
be human-readable.

### Telegram Interface

The bot MUST support these commands:

- `/status` — system health
- `/last_signal` — most recent signal
- `/performance` — tracked metrics
- `/kill` — emergency stop

The bot MUST broadcast signals automatically when generated.

### Technology Stack

- **Language**: Python
- **Core libraries**: pandas, numpy, ta, requests, apscheduler,
  python-telegram-bot, vectorbt
- **Storage**: SQLite
- **Deployment**: local computer (early development)

## Risk Management & Safety Controls

### Execution Loop

The system MUST operate on a scheduled loop (recommended: every 5
minutes). Each cycle:

1. Collect market data
2. Compute indicators
3. Detect patterns
4. Collect news
5. Analyze sentiment
6. Generate signal probability
7. Evaluate risk rules
8. Send signal (if approved)
9. Log performance

### Backtesting

The system MUST support historical strategy testing evaluating:

- Signal accuracy, profitability, drawdown, risk metrics

Libraries: vectorbt, backtrader. Backtesting MUST allow strategy
optimization.

### Scalability

The architecture MUST support future upgrades:

- Multi-asset monitoring
- Reinforcement learning strategies
- Portfolio optimization
- Semi-automatic trading execution
- Cloud deployment

## Development Workflow & Execution

### Roles

- **Claude** — architecture design, planning, code review
- **GLM5** — implementation of specifications

### Workflow

1. Specifications are created (spec-driven)
2. Implementation tasks are generated
3. GLM5 writes code against specs
4. Claude reviews architecture and logic
5. Tests validate the system

### Quality Gates

- Every agent MUST have unit tests
- Integration tests MUST verify agent-to-agent data flow
- Risk management rules MUST be validated with edge-case tests
- Backtesting MUST pass before strategy changes are accepted

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

**Version**: 1.0.0 | **Ratified**: 2026-03-26 | **Last Amended**: 2026-03-26

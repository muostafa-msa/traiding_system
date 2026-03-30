# Implementation Plan: Sentiment Intelligence (FinBERT)

**Branch**: `002-finbert-sentiment` | **Date**: 2026-03-29 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/002-finbert-sentiment/spec.md`

## Summary

Add financial news sentiment analysis to the trading system using FinBERT (local model). Collect headlines from RSS feeds, classify sentiment (Bullish/Bearish/Neutral), compute aggregate macro score, detect news blackout events, and integrate blackout protection into the risk pipeline. Includes model lifecycle management (lazy loading, device detection, caching) as infrastructure for future ML models.

## Technical Context

**Language/Version**: Python 3.12
**Primary Dependencies**: torch (>=2.0), transformers (>=4.30), feedparser (6.0.11, already installed)
**Storage**: SQLite (existing — add `content_hash` column to news table, `blackout_until` to account_state)
**Testing**: pytest, pytest-asyncio (existing)
**Target Platform**: Linux (local machine, CPU default, optional CUDA/MPS GPU)
**Project Type**: Background service (scheduled pipeline)
**Performance Goals**: 20 headlines classified in <30s on CPU (SC-001)
**Constraints**: <1.5 GB additional RAM for FinBERT; local-first (offline inference after setup); no external API for sentiment
**Scale/Scope**: Single asset (XAU/USD), 3-10 RSS feeds, ~50-200 headlines/day

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| FinBERT for financial sentiment (Section 5.1) | PASS | Using `ProsusAI/finbert` exactly as specified |
| Local-first architecture (Section 2) | PASS | Model downloaded once, inference offline. Only RSS feeds are external |
| CPU execution default (Section 2) | PASS | Device auto-detection with CPU fallback; `MODEL_DEVICE=cpu` override |
| Risk management on every signal (Section 9) | PASS | Blackout flag integrated into risk agent evaluation pipeline |
| Economic event protection (Section 10) | PASS | News blackout via keyword detection (Fed, NFP, CPI) — FR-007, FR-008 |
| Agent unit tests (Section 16) | PASS | Test plan includes test_finbert.py, test_sentiment.py |
| No circular dependencies | PASS | `models/` imports only `core/`; `agents/` imports `models/` + `data/` + `core/` |
| Frozen dataclass contracts (Section implied) | PASS | NewsItem, SentimentResult as frozen dataclasses in core/types.py |

**Post-design re-check**: All gates still pass. No violations.

## Project Structure

### Documentation (this feature)

```text
specs/002-finbert-sentiment/
├── plan.md              # This file
├── spec.md              # Feature specification
├── research.md          # Technology research findings
├── data-model.md        # Entity model and schema changes
├── quickstart.md        # Setup and verification guide
├── contracts/
│   └── agent-contracts.md  # Inter-agent data flow contracts
└── checklists/
    └── requirements.md  # Spec quality checklist
```

### Source Code (repository root)

```text
models/                       # NEW package — ML model management
├── __init__.py
├── model_manager.py          # Device detection, lazy loading, caching
└── finbert.py                # FinBERT wrapper (load, classify, batch)

data/
├── news_data.py              # NEW — RSS collector, keyword filter, dedup

agents/
├── sentiment_agent.py        # NEW — wraps FinBERT model for headline classification
├── news_agent.py             # NEW — orchestrates: collect → classify → blackout → aggregate
└── risk_agent.py             # MODIFIED — add blackout check rule

core/
├── types.py                  # MODIFIED — add NewsItem, SentimentResult dataclasses
├── config.py                 # MODIFIED — add RSS, model, blackout config fields
└── scheduler.py              # MODIFIED — integrate news collection into cycle

storage/
└── database.py               # MODIFIED — add content_hash column, blackout_until, news CRUD

setup_models.py               # NEW — download FinBERT weights

tests/
├── test_finbert.py           # NEW — FinBERT classification tests
└── test_sentiment.py         # NEW — sentiment agent + news agent tests
```

**Structure Decision**: Follows existing multi-package layout from Phase 1. New `models/` package per implementation plan. All new code follows the established dependency direction: `main -> scheduler -> agents -> models/data/analysis -> core/types`.

## Dependency Graph (additions in bold)

```
core/types.py              <-- imported by everything
core/config.py             <-- imported by everything
core/logger.py             <-- imported by everything
**models/model_manager.py  <-- config, logger**
**models/finbert.py        <-- model_manager, types**
storage/database.py        <-- types, config
data/market_data.py        <-- types, config, logger
**data/news_data.py        <-- types, config, logger**
analysis/indicators.py     <-- types
**agents/sentiment_agent.py <-- finbert, types**
**agents/news_agent.py     <-- news_data, sentiment_agent, database, types**
agents/risk_agent.py       <-- types, config, database
core/scheduler.py          <-- ALL agents, database (orchestrator)
main.py                    <-- config, scheduler, telegram_bot, database, logger
**setup_models.py          <-- transformers (standalone script)**
```

No circular dependencies introduced.

# Data Model: Sentiment Intelligence (FinBERT)

**Feature**: `002-finbert-sentiment` | **Date**: 2026-03-29

## New Frozen Dataclasses (`core/types.py`)

### NewsItem

Represents a single collected news headline before classification.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| source | str | Non-empty | RSS feed source name |
| headline | str | Non-empty | Headline text |
| url | str | Optional (may be empty) | Article URL |
| published_at | datetime | UTC timezone | Publication timestamp |
| raw_text | str | Optional | Full article text if available |

### SentimentResult

Classification output for a single headline.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| classification | str | One of: "Bullish", "Bearish", "Neutral" | Mapped from FinBERT output |
| confidence | float | 0.0 - 1.0 | Highest class probability from softmax |
| positive_score | float | 0.0 - 1.0 | FinBERT positive (Bullish) probability |
| negative_score | float | 0.0 - 1.0 | FinBERT negative (Bearish) probability |
| neutral_score | float | 0.0 - 1.0 | FinBERT neutral probability |

**Label mapping**: FinBERT outputs `positive` -> `Bullish`, `negative` -> `Bearish`, `neutral` -> `Neutral`

### MacroSentiment (not frozen — aggregation result)

Aggregate sentiment state for the current period.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| macro_score | float | -1.0 to +1.0 | Mean of (direction * confidence) over 4h window |
| headline_count | int | >= 0 | Number of headlines in window |
| sentiments | list[SentimentResult] | | Individual headline classifications |
| is_blackout | bool | | True if trigger keyword detected within blackout duration |
| blackout_activated_at | datetime or None | UTC | Timestamp when blackout was activated |

**Macro score formula**: `mean(direction_sign * confidence)` where `direction_sign` = +1 (Bullish), -1 (Bearish), 0 (Neutral)

## Database Schema Changes

### news table (existing — add `content_hash` column)

The `news` table already exists from Phase 1. Add one column:

| Column | Type | Constraint | Description |
|--------|------|------------|-------------|
| content_hash | TEXT | UNIQUE | SHA-256 hash of normalized headline for deduplication |

All other columns remain unchanged:
- `id`, `source`, `headline`, `url`, `published_at`, `classification`, `confidence`, `collected_at`

### account_state table (existing — add `blackout_until` column)

Add one column to support time-based blackout expiry:

| Column | Type | Constraint | Description |
|--------|------|------------|-------------|
| blackout_until | TIMESTAMP | Nullable | UTC timestamp when blackout expires; NULL = no blackout |

## AppConfig Extensions

New configuration fields for Phase 2:

| Field | Type | Default | Env Var | Description |
|-------|------|---------|---------|-------------|
| rss_feed_urls | str | "" | RSS_FEED_URLS | Comma-separated feed URLs |
| rss_keywords | str | "gold,inflation,fed,interest rate,usd,war,oil,cpi,nfp" | RSS_KEYWORDS | Comma-separated filter keywords |
| blackout_keywords | str | "fed,fomc,nfp,non-farm,cpi,consumer price,interest rate decision" | BLACKOUT_KEYWORDS | Trigger keywords |
| blackout_duration_hours | float | 4.0 | BLACKOUT_DURATION_HOURS | Hours before blackout auto-clears |
| sentiment_window_hours | float | 4.0 | SENTIMENT_WINDOW_HOURS | Rolling window for macro score |
| finbert_model_path | str | "models/finbert" | FINBERT_MODEL_PATH | Local FinBERT weights directory |
| model_device | str | "auto" | MODEL_DEVICE | Device override: auto/cpu/cuda/mps |

## Entity Relationships

```
RSS Feeds (external)
    |
    v
NewsItem (collected) --[classified by]--> SentimentResult (per headline)
    |                                          |
    |                                          v
    +---[persisted to]---> news table     MacroSentiment (aggregated)
                                               |
                                               v
                                          RiskAgent (blackout check)
```

## State Transitions

### Blackout State Machine

```
INACTIVE --[trigger keyword detected]--> ACTIVE (blackout_until = now + duration)
ACTIVE --[current_time > blackout_until]--> INACTIVE (blackout_until = NULL)
ACTIVE --[new trigger keyword detected]--> ACTIVE (blackout_until = now + duration, reset timer)
```

### Headline Processing Pipeline

```
Fetched --[keyword filter]--> Filtered --[dedup check]--> Unique --[FinBERT]--> Classified --[persisted]--> Stored
```

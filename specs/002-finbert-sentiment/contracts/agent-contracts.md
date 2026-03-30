# Agent Contracts: Sentiment Intelligence (FinBERT)

**Feature**: `002-finbert-sentiment` | **Date**: 2026-03-29

## Inter-Agent Data Flow

```
data/news_data.py          -> list[NewsItem]
agents/sentiment_agent.py  -> list[SentimentResult]  (wraps models/finbert.py)
agents/news_agent.py       -> MacroSentiment          (orchestrates news_data + sentiment_agent)
agents/risk_agent.py       <- MacroSentiment.is_blackout (new rejection rule)
```

## Contract: NewsCollector (data/news_data.py)

**Input**: RSS feed URLs (from config), keyword list (from config)
**Output**: `list[NewsItem]`

- Fetches all configured RSS feeds
- Filters headlines by keyword match (case-insensitive, any keyword in headline)
- Deduplicates by SHA-256 content hash
- Returns only new, unique, keyword-matched headlines
- On feed failure: logs warning, skips feed, continues

## Contract: SentimentAgent (agents/sentiment_agent.py)

**Input**: `list[NewsItem]`
**Output**: `list[SentimentResult]`

- Loads FinBERT via ModelManager (lazy, cached)
- Classifies each headline: Bullish/Bearish/Neutral with confidence
- Maps FinBERT labels: positive->Bullish, negative->Bearish, neutral->Neutral
- Returns one SentimentResult per NewsItem (same order)
- If model unavailable: returns empty list, logs warning

## Contract: NewsAgent (agents/news_agent.py)

**Input**: AppConfig, Database
**Output**: `MacroSentiment`

- Orchestrates: collect news -> classify sentiment -> detect blackout -> aggregate
- Calls NewsCollector to get headlines
- Calls SentimentAgent to classify
- Persists classified headlines to database
- Computes macro score from 4-hour rolling window
- Detects blackout keywords in current batch
- Returns MacroSentiment with all fields populated
- If no headlines: returns macro_score=0.0, is_blackout=False (or existing blackout state)

## Contract: ModelManager (models/model_manager.py)

**Input**: Model name/path, device preference
**Output**: Loaded model + tokenizer (cached)

- Auto-detects device: CUDA -> MPS -> CPU
- Respects MODEL_DEVICE config override
- Lazy loading: first call loads, subsequent calls return cache
- Provides `get_model(name)` and `get_tokenizer(name)` methods
- Logs device selection and load time

## Contract: RiskAgent Update (agents/risk_agent.py)

**New rule** inserted between existing rules 4 (max positions) and 5 (RR ratio):

```
Current order:
1. kill_switch_active -> REJECT
2. daily_loss > 5% -> ACTIVATE KILL SWITCH, REJECT
3. daily_risk_used + 1% > 3% -> REJECT
4. open_positions >= 2 -> REJECT
5. [NEW] news_blackout active -> REJECT ("News blackout period")
6. risk_reward_ratio < 1.8 -> REJECT
```

The blackout check queries `account_state.blackout_until`:
- If `blackout_until` is not NULL and `blackout_until > now()`: reject with "News blackout period"
- Otherwise: proceed to next check

## Contract: setup_models.py

**Input**: None (reads config for model paths)
**Output**: Downloaded model weights on disk

- Downloads FinBERT from Hugging Face Hub
- Saves to configured `finbert_model_path` (default: `models/finbert/`)
- Creates directory structure if needed
- Skips download if weights already exist (checks for `config.json`)
- Reports success/failure with clear messages

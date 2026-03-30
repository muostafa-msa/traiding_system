# Quickstart: Sentiment Intelligence (FinBERT)

**Feature**: `002-finbert-sentiment` | **Prerequisites**: Phase 1 (core-system-risk) completed

## Setup

### 1. Install new dependencies

```bash
pip install torch transformers
```

Or add to requirements.txt:
```
torch>=2.0.0
transformers>=4.30.0
```

### 2. Download FinBERT model weights

```bash
python setup_models.py
```

This downloads `ProsusAI/finbert` (~440 MB) to `models/finbert/`. Subsequent runs skip the download.

### 3. Configure RSS feeds

Add to `.env`:

```bash
# RSS News Feeds (comma-separated URLs)
RSS_FEED_URLS=https://www.kitco.com/rss/lo_news.xml,https://feeds.reuters.com/reuters/businessNews,https://www.fxstreet.com/rss/news

# Keywords for headline filtering
RSS_KEYWORDS=gold,inflation,fed,interest rate,usd,war,oil,cpi,nfp

# Blackout trigger keywords
BLACKOUT_KEYWORDS=fed,fomc,nfp,non-farm,cpi,consumer price,interest rate decision

# Blackout duration in hours
BLACKOUT_DURATION_HOURS=4.0

# Sentiment rolling window in hours
SENTIMENT_WINDOW_HOURS=4.0

# Model settings
FINBERT_MODEL_PATH=models/finbert
MODEL_DEVICE=auto
```

## Run

```bash
python main.py
```

The system now collects news headlines during each scheduled cycle, classifies sentiment via FinBERT, and computes an aggregate macro score.

## Verify

### 1. Check news collection

After one cycle, query the database:

```bash
sqlite3 storage/trading.db "SELECT headline, classification, confidence FROM news ORDER BY collected_at DESC LIMIT 5;"
```

Expected: Headlines with Bullish/Bearish/Neutral classification and confidence scores.

### 2. Check sentiment in logs

```bash
grep "macro_score" logs/trading.log | tail -5
```

Expected: Macro score values between -1.0 and +1.0.

### 3. Test blackout (optional)

If a headline contains Fed/NFP/CPI keywords, check:

```bash
sqlite3 storage/trading.db "SELECT blackout_until FROM account_state LIMIT 1;"
```

Expected: A future UTC timestamp (blackout active) or NULL (no blackout).

### 4. Run tests

```bash
pytest tests/test_finbert.py tests/test_sentiment.py -v
```

## Troubleshooting

- **"FinBERT model not found"**: Run `python setup_models.py` to download weights.
- **RSS feed errors in logs**: Check that feed URLs are valid and reachable. Update `RSS_FEED_URLS` in `.env`.
- **High memory usage**: FinBERT requires ~1-1.5 GB RAM. Ensure at least 4 GB available.
- **CUDA not detected**: Set `MODEL_DEVICE=cpu` in `.env` to force CPU mode.

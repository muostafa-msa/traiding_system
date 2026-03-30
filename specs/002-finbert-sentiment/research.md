# Research: Sentiment Intelligence (FinBERT)

**Feature**: `002-finbert-sentiment` | **Date**: 2026-03-29

## 1. FinBERT Model Loading and Inference

**Decision**: Use `transformers.pipeline("text-classification")` with `ProsusAI/finbert`, `return_all_scores=True`, `batch_size=8`, `device=-1` for CPU.

**Rationale**: The pipeline abstraction handles tokenization, batching, padding, and softmax in one call. For CPU batch inference on short headlines (10-30 tokens), this is faster and less error-prone than manual DataLoader setup.

**Details**:
- Model: `AutoModelForSequenceClassification.from_pretrained("ProsusAI/finbert")`
- Tokenizer: `AutoTokenizer.from_pretrained("ProsusAI/finbert")`
- Max sequence length: 512 tokens (headlines never approach this)
- Output labels: `"positive"`, `"negative"`, `"neutral"` -> mapped to Bullish/Bearish/Neutral
- Truncation: `truncation=True, max_length=512` handles edge case
- Local storage: `model.save_pretrained("models/finbert")` + `tokenizer.save_pretrained("models/finbert")` for offline operation
- Batch inference: Pass list of strings to pipeline; it handles batching internally

**Alternatives considered**:
- Raw `model(**inputs)` loop: More control but unnecessary boilerplate
- `optimum` quantized inference: Better throughput but adds dependency for no practical gain (SC-001 easily met)
- ONNX export: Better CPU speed but overkill for Phase 2

## 2. RSS Feed Collection via feedparser

**Decision**: Use `feedparser.parse()` with `requests` prefetch for timeout control. Check `feed.bozo` for errors. Simple sequential loop over feed URLs.

**Rationale**: `feedparser` is already in requirements.txt. Its "never raise" contract makes error handling trivial. The `requests` prefetch pattern gives timeout control that feedparser lacks natively.

**Details**:
- Standard fields: `entry.title` (headline), `entry.link` (URL), `entry.published_parsed` (time)
- Error handling: `feedparser.parse()` never raises; sets `feed.bozo = True` on failure. Empty `entries` on network error.
- Timeout: Fetch with `requests.get(url, timeout=10)` first, then `feedparser.parse(response.text)`
- Multiple feeds: Sequential loop is fine for 3-10 feeds (total <30s)

**Alternatives considered**:
- Async `aiohttp` concurrent fetching: Adds complexity; unnecessary for <10 feeds
- `httpx` with manual XML parsing: Reinvents feedparser

## 3. PyTorch Device Detection

**Decision**: Priority chain: CUDA -> MPS -> CPU. Config override via `MODEL_DEVICE` env var (values: `auto`, `cpu`, `cuda`, `mps`).

**Rationale**: CUDA GPUs are faster than MPS for BERT inference. CPU is guaranteed fallback. MPS included for macOS developer support.

**Details**:
- `torch.cuda.is_available()` — NVIDIA GPU with CUDA runtime
- `torch.backends.mps.is_available()` — Apple Silicon M1/M2/M3
- For transformers pipeline: `device=0` (CUDA), `device="mps"` (MPS), `device=-1` (CPU)
- Existing `AppConfig` already has no model device field — need to add `model_device: str = "auto"`

## 4. Headline Deduplication

**Decision**: SHA-256 hash of normalized headline text (`headline.strip().lower()`). Database UNIQUE constraint on `content_hash` column with `INSERT OR IGNORE`.

**Rationale**: SHA-256 is collision-resistant and standard for content addressing. Database-level UNIQUE provides a robust second layer. Performance is immeasurable for headline-length strings.

**Details**:
- Normalize: lowercase + strip whitespace before hashing
- In-memory pre-check: Build `set` of hashes per cycle to skip redundant FinBERT calls
- DB enforcement: Add `content_hash TEXT` column to news table with UNIQUE constraint
- Use `INSERT OR IGNORE` to silently discard duplicates at persistence time

**Alternatives considered**:
- MD5: Functionally equivalent but carries deprecation reputation
- `entry.id` from feedparser: Unreliable — varying or absent IDs across feeds
- Fuzzy dedup (edit distance): Overkill for literal duplicates

## 5. Financial RSS Feed Sources

**Decision**: Curated set of free feeds stored as `RSS_FEED_URLS` env var (comma-separated).

**Recommended feeds**:

| Source | URL | Relevance |
|--------|-----|-----------|
| Kitco Gold News | `https://www.kitco.com/rss/lo_news.xml` | Gold-specific (highest signal for XAU/USD) |
| Reuters Business | `https://feeds.reuters.com/reuters/businessNews` | Broad macro, Fed, rates |
| Investing.com Gold | `https://www.investing.com/rss/news_301.rss` | Gold commodities |
| FXStreet News | `https://www.fxstreet.com/rss/news` | Forex + macro, gold analysis |
| CNBC Economy | `https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=20910258` | US macro, Fed statements |

**Notes**:
- Feed URLs change periodically; stored in `.env` for user configurability
- Investing.com may require User-Agent header to avoid 403
- No API keys required for any of these feeds
- ForexFactory has no public RSS; high-impact events detected via keyword scanning (FR-007)

**Alternatives considered**:
- Bloomberg RSS: No longer public
- Financial Times RSS: Requires subscription
- Twitter/X: Not RSS, requires paid API
- Alpha Vantage News API: Requires key; redundant

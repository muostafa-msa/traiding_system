# Feature Specification: Sentiment Intelligence (FinBERT)

**Feature Branch**: `002-finbert-sentiment`
**Created**: 2026-03-29
**Status**: Draft
**Input**: Phase 2 from implementation plan — RSS news collection, FinBERT local sentiment scoring, news blackout detection, and sentiment agent integration for XAU/USD.

## Clarifications

### Session 2026-03-29

- Q: When/how does the news blackout period end? → A: Blackout clears automatically after a configurable duration (default 4 hours).
- Q: What time window defines "recent headlines" for macro score aggregation? → A: Rolling 4-hour window.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Receive Sentiment-Enriched Market Analysis (Priority: P1)

As a trader monitoring XAU/USD, I want the system to automatically collect financial news, classify each headline's sentiment (Bullish/Bearish/Neutral), and compute an aggregate macro sentiment score, so that I can factor market sentiment into my trading decisions without manually scanning news feeds.

The system collects headlines from configured RSS feeds, filters by gold/macro keywords, runs each headline through a local FinBERT model to classify sentiment with confidence, and computes an aggregate macro score ranging from -1.0 (strongly bearish) to +1.0 (strongly bullish). The sentiment results are persisted in the database and made available to downstream agents.

**Why this priority**: Sentiment analysis is the core value of this phase. Without it, the system relies solely on technical indicators. Adding FinBERT-powered sentiment gives the trader a second independent signal source — news-driven market context — which directly feeds into the XGBoost decision engine in Phase 3.

**Independent Test**: Configure RSS feed URLs in `.env`, start the system, trigger a news collection cycle, and verify that the database contains classified news headlines with sentiment labels and confidence scores, and that an aggregate macro score is computed.

**Acceptance Scenarios**:

1. **Given** RSS feed URLs are configured and the FinBERT model is downloaded, **When** a news collection cycle runs, **Then** the system fetches headlines from all configured feeds, filters by relevant keywords, classifies each headline as Bullish/Bearish/Neutral with a confidence score, and stores results in the news table.
2. **Given** multiple classified headlines exist within the last 4 hours, **When** the aggregate sentiment is computed, **Then** a macro score between -1.0 and +1.0 is returned, calculated as the mean of (sentiment_direction * confidence) across all headlines in that rolling window.
3. **Given** no new headlines are available from RSS feeds, **When** a news collection cycle runs, **Then** the system logs the absence and returns a neutral macro score (0.0) without errors.
4. **Given** the FinBERT model has not been downloaded yet, **When** the system starts, **Then** it logs a clear warning that sentiment analysis is unavailable and degrades gracefully (skips sentiment scoring rather than crashing).

---

### User Story 2 - Block Signals During High-Impact News Events (Priority: P2)

As a trader, I want the system to detect high-impact macroeconomic news events (Fed announcements, NFP, CPI releases) and automatically enter a "news blackout" period during which no new trading signals are generated, so that I am protected from volatile price swings around major news releases.

The system scans collected headlines for blackout trigger keywords (Fed, FOMC, NFP, Non-Farm Payroll, CPI, Consumer Price Index, interest rate decision). When a blackout-triggering headline is detected, the system flags a blackout period and the risk agent rejects all new signals until the blackout clears.

**Why this priority**: News blackout is a critical safety feature. Major economic releases cause extreme volatility that makes technical signals unreliable. The constitution's risk management rules require protecting the trader from such events. However, it depends on the news collection pipeline from US1.

**Independent Test**: Inject a headline containing "Federal Reserve interest rate decision" into the news pipeline, verify the blackout flag activates, submit a synthetic trade signal, and confirm it is rejected with reason "News blackout period".

**Acceptance Scenarios**:

1. **Given** a collected headline contains a blackout trigger keyword (e.g., "Fed", "NFP", "CPI"), **When** the news agent processes it, **Then** the blackout flag is set to active.
2. **Given** the blackout flag is active, **When** the risk agent evaluates any trade signal, **Then** the signal is rejected with reason "News blackout period".
3. **Given** the blackout was activated more than the configured duration ago (default 4 hours), **When** the next news collection cycle runs, **Then** the blackout flag is cleared and signals are evaluated normally.
4. **Given** no blackout-triggering headlines are present in the current collection period, **When** the news agent runs, **Then** the blackout flag remains inactive and signals are evaluated normally.

---

### User Story 3 - One-Time Model Setup (Priority: P3)

As a developer setting up the system, I want a single setup command that downloads the FinBERT model weights locally, so that I can prepare the system for sentiment analysis without manually managing model files.

A setup script downloads the FinBERT model from Hugging Face, stores it in a local directory, and verifies the download succeeded. Subsequent runs detect the existing weights and skip re-download.

**Why this priority**: This is a prerequisite for US1 but is a one-time operation, not ongoing system behavior. It enables the local-first architecture by ensuring all model weights are available offline after initial setup.

**Independent Test**: Run the setup script on a fresh installation, verify the model files exist in the expected directory, run it again and verify it completes instantly without re-downloading.

**Acceptance Scenarios**:

1. **Given** the system has internet access and no local model weights, **When** the setup script runs, **Then** FinBERT model weights are downloaded and stored locally.
2. **Given** FinBERT weights already exist locally, **When** the setup script runs, **Then** it detects existing weights and skips the download.
3. **Given** the download fails (network error), **When** the setup script runs, **Then** it reports a clear error message indicating what failed and how to retry.

---

### User Story 4 - Manage Model Lifecycle Efficiently (Priority: P4)

As a system operator, I want the ML models to be loaded lazily (only when needed) and to support both CPU and GPU execution automatically, so that the system uses resources efficiently and works on any hardware without manual configuration.

A model manager handles device detection (CPU/CUDA/MPS), lazy model loading on first use, and optional model unloading between cycles to conserve memory. Models are cached after first load to avoid repeated initialization overhead.

**Why this priority**: Resource management is foundational infrastructure for all ML models. While only FinBERT is used in Phase 2, the model manager will serve LSTM, XGBoost, and GPT-2B in Phase 3. Building it now prevents rework.

**Independent Test**: Start the system on a CPU-only machine, trigger sentiment analysis, verify FinBERT loads on CPU. If GPU is available, verify automatic GPU detection. Monitor memory usage before and after model loading.

**Acceptance Scenarios**:

1. **Given** no ML model has been loaded yet, **When** sentiment analysis is requested for the first time, **Then** the FinBERT model is loaded on the best available device (GPU if available, CPU otherwise).
2. **Given** the FinBERT model was previously loaded, **When** sentiment analysis is requested again, **Then** the cached model is reused without reloading.
3. **Given** the system is configured to use CPU only, **When** a model is loaded, **Then** it runs on CPU regardless of GPU availability.

---

### Edge Cases

- What happens when an RSS feed URL is unreachable? The system MUST log the failure, skip that feed, and continue processing other configured feeds without crashing.
- What happens when a headline is too long for FinBERT's token limit (512 tokens)? The system MUST truncate the input to fit within the model's maximum sequence length.
- What happens when duplicate headlines appear across multiple RSS feeds? The system MUST deduplicate by headline content hash before classification to avoid redundant processing and inflated sentiment scores.
- What happens when the FinBERT model returns very low confidence for a classification? The system MUST still include the result but weight it by confidence in the aggregate score, naturally reducing its impact.
- What happens when the model weights directory does not exist? The setup script MUST create the directory structure automatically.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST collect headlines from one or more configurable RSS feed URLs at regular intervals.
- **FR-002**: System MUST filter collected headlines using configurable keywords relevant to gold and macroeconomic events (gold, inflation, fed, interest rate, usd, war, oil, cpi, nfp).
- **FR-003**: System MUST deduplicate headlines by content hash to prevent processing the same headline multiple times.
- **FR-004**: System MUST classify each filtered headline as Bullish, Bearish, or Neutral using the FinBERT model with a confidence score between 0.0 and 1.0.
- **FR-005**: System MUST compute an aggregate macro sentiment score as the mean of (sentiment_direction * confidence) across headlines from the last 4 hours (rolling window), producing a value between -1.0 and +1.0.
- **FR-006**: System MUST persist all collected and classified news items in the database with source, headline, URL, publication time, classification, and confidence.
- **FR-007**: System MUST detect news blackout conditions by scanning headlines for configurable trigger keywords (Fed, FOMC, NFP, CPI, and related terms).
- **FR-008**: System MUST integrate the blackout flag into the risk evaluation pipeline so that all signals are rejected during a blackout period.
- **FR-013**: System MUST automatically clear the news blackout after a configurable duration (default 4 hours) from activation time.
- **FR-009**: System MUST provide a setup mechanism to download FinBERT model weights locally for offline operation.
- **FR-010**: System MUST support automatic device detection (CPU, CUDA, MPS) for model inference, defaulting to CPU when no GPU is available.
- **FR-011**: System MUST load ML models lazily (on first use) and cache them for subsequent inference calls within the same session.
- **FR-012**: System MUST degrade gracefully when FinBERT weights are not available — logging a warning and skipping sentiment analysis rather than crashing.

### Key Entities

- **NewsItem**: A collected headline with source, text, URL, and publication timestamp. Represents raw input before classification.
- **SentimentResult**: The classification output for a single headline — sentiment direction (Bullish/Bearish/Neutral), confidence score, and optional reasoning. Linked to a NewsItem.
- **MacroSentiment**: The aggregate sentiment state for the current period — macro score (-1.0 to +1.0), headline count, blackout flag, and individual headline sentiments.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Sentiment classification completes for a batch of 20 headlines in under 30 seconds on CPU hardware.
- **SC-002**: FinBERT classification accuracy matches the published model benchmark (>85% on financial text) when tested with known-label headline samples.
- **SC-003**: News collection, deduplication, and classification cycle completes without errors for at least 95% of scheduled runs over a 24-hour period.
- **SC-004**: News blackout is activated within one collection cycle of a trigger headline appearing in any configured RSS feed.
- **SC-005**: System memory usage increases by no more than 1.5 GB after loading the FinBERT model, consistent with the model's published size.
- **SC-006**: Model setup script downloads and verifies FinBERT weights in under 5 minutes on a standard broadband connection.

## Assumptions

- RSS feeds provide timely financial headlines relevant to gold and macroeconomic events. Feed selection and URL configuration is the user's responsibility.
- The host machine has at least 4 GB of available RAM to accommodate FinBERT model loading alongside the existing system.
- Internet connectivity is required only for initial model download (via setup script) and ongoing RSS feed fetching. Sentiment inference runs fully offline.
- The existing Phase 1 database schema already includes the `news` table with the required columns — no schema migration is needed.
- FinBERT's published tokenizer handles headline-length financial text well; no custom fine-tuning is needed for this use case.
- The news collection interval aligns with the existing scheduler's cycle intervals (5min/15min/1h/4h) rather than introducing a separate schedule.
- Phase 1 infrastructure (config, logger, database, scheduler, types) is complete and stable.

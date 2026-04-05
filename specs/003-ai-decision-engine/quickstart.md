# Quickstart: AI Decision Engine (003)

**Branch**: `003-ai-decision-engine`

## Prerequisites

- Phase 1 (core infrastructure) and Phase 2 (FinBERT sentiment) fully implemented
- Python 3.12 with existing dependencies installed
- At least 8 GB RAM available

## New Dependencies

```bash
pip install scikit-learn xgboost
```

torch and transformers are already installed from Phase 2.

## Setup

1. **Setup models** (one-time — downloads FinBERT, checks Ollama connectivity):

```bash
python setup_models.py
```

2. **Install and start Ollama** (for GPT-OSS-20B explanations — optional, template fallback used if unavailable):

```bash
ollama serve          # start Ollama server
ollama pull gpt-oss:20b  # pull the explanation model
```

3. **Verify installation**:

```bash
python -c "import xgboost; import sklearn; print('Dependencies OK')"
```

## Running

### Normal operation (untrained models — uses fallback scoring)

```bash
python main.py
```

The system will:
- Run pattern detection on all timeframes
- Use weighted-formula fallback for probability scoring (XGBoost not yet trained)
- Use template-based explanations (GPT-OSS-20B via Ollama when available, template fallback otherwise)
- Emit signals when probability >= 0.68

### Training models (offline, after collecting historical data)

```bash
# Train LSTM on historical CSV data
python -m models.lstm_model --train --data data/historical/xauusd_1h.csv

# Train XGBoost on historical CSV data
python -m models.xgboost_model --train --data data/historical/xauusd_1h.csv
```

After training, restart the system to use trained models instead of fallbacks.

## Testing

```bash
# Run all Phase 3 tests
pytest tests/test_patterns.py tests/test_lstm.py tests/test_xgboost.py tests/test_explanation_model.py tests/test_chart_agent.py tests/test_prediction_agent.py tests/test_signal_agent.py tests/test_signal_scoring.py -v

# Run full test suite
pytest tests/ -v
```

## Configuration (.env additions)

```bash
# Model paths (defaults shown)
LSTM_MODEL_PATH=models/lstm
XGBOOST_MODEL_PATH=models/xgboost

# Ollama (GPT-OSS-20B explanation generation)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=gpt-oss:20b

# Signal threshold (default: 0.68)
SIGNAL_THRESHOLD=0.68

# Fallback weights (defaults shown, must sum to 1.0)
FALLBACK_WEIGHT_INDICATORS=0.30
FALLBACK_WEIGHT_PATTERNS=0.20
FALLBACK_WEIGHT_SENTIMENT=0.25
FALLBACK_WEIGHT_PREDICTION=0.25

# Explanation generation settings
EXPLANATION_MAX_TOKENS=150
EXPLANATION_TEMPERATURE=0.7

# LSTM settings
LSTM_SEQUENCE_LENGTH=60

# Decision window for best-signal-wins (minutes)
DECISION_WINDOW_MINUTES=15
```

## Verification

Per implementation plan Phase 3 verification:
- Signals include XGBoost probability (or fallback probability with method indicator)
- GPT-OSS-20B reasoning appears in Telegram messages (or template fallback)
- NO_TRADE produced when probability < 0.68
- `pytest tests/ -v` passes all tests

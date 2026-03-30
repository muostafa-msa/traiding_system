from __future__ import annotations

from dataclasses import dataclass
import os

from dotenv import load_dotenv


@dataclass(frozen=True)
class AppConfig:
    market_data_provider: str
    market_data_api_key: str
    initial_capital: float
    telegram_bot_token: str
    telegram_chat_id: str
    signal_threshold: float
    max_risk_per_trade: float
    max_daily_risk: float
    max_open_positions: int
    kill_switch_threshold: float
    sl_atr_multiplier: float
    tp_atr_multiplier: float
    log_level: str
    db_path: str
    rss_feed_urls: str
    rss_keywords: str
    blackout_keywords: str
    blackout_duration_hours: float
    sentiment_window_hours: float
    finbert_model_path: str
    model_device: str

    def __post_init__(self):
        if not self.market_data_provider:
            raise ValueError("MARKET_DATA_PROVIDER is required")
        if self.initial_capital <= 0:
            raise ValueError(f"INITIAL_CAPITAL must be > 0, got {self.initial_capital}")


def load_config(env_path: str | None = None) -> AppConfig:
    load_dotenv(env_path)

    return AppConfig(
        market_data_provider=os.environ.get("MARKET_DATA_PROVIDER", ""),
        market_data_api_key=os.environ.get("MARKET_DATA_API_KEY", ""),
        initial_capital=float(os.environ.get("INITIAL_CAPITAL", "0")),
        telegram_bot_token=os.environ.get("TELEGRAM_BOT_TOKEN", ""),
        telegram_chat_id=os.environ.get("TELEGRAM_CHAT_ID", ""),
        signal_threshold=float(os.environ.get("SIGNAL_THRESHOLD", "0.68")),
        max_risk_per_trade=float(os.environ.get("MAX_RISK_PER_TRADE", "0.01")),
        max_daily_risk=float(os.environ.get("MAX_DAILY_RISK", "0.03")),
        max_open_positions=int(os.environ.get("MAX_OPEN_POSITIONS", "2")),
        kill_switch_threshold=float(os.environ.get("KILL_SWITCH_THRESHOLD", "0.05")),
        sl_atr_multiplier=float(os.environ.get("SL_ATR_MULTIPLIER", "1.5")),
        tp_atr_multiplier=float(os.environ.get("TP_ATR_MULTIPLIER", "3.0")),
        log_level=os.environ.get("LOG_LEVEL", "INFO"),
        db_path=os.environ.get("DB_PATH", "storage/trading.db"),
        rss_feed_urls=os.environ.get("RSS_FEED_URLS", ""),
        rss_keywords=os.environ.get(
            "RSS_KEYWORDS", "gold,inflation,fed,interest rate,usd,war,oil,cpi,nfp"
        ),
        blackout_keywords=os.environ.get(
            "BLACKOUT_KEYWORDS",
            "fed,fomc,nfp,non-farm,cpi,consumer price,interest rate decision",
        ),
        blackout_duration_hours=float(os.environ.get("BLACKOUT_DURATION_HOURS", "4.0")),
        sentiment_window_hours=float(os.environ.get("SENTIMENT_WINDOW_HOURS", "4.0")),
        finbert_model_path=os.environ.get("FINBERT_MODEL_PATH", "models/finbert"),
        model_device=os.environ.get("MODEL_DEVICE", "auto"),
    )

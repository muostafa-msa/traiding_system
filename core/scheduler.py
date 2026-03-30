from __future__ import annotations

import threading
import time
from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler

from analysis.indicators import compute_indicators
from agents.news_agent import NewsAgent
from agents.risk_agent import RiskAgent
from core.config import AppConfig
from core.logger import get_logger
from core.types import OHLCBar, TradeSignal
from data.market_data import MarketDataError, get_provider
from execution.signal_generator import format_indicator_summary, format_trade_signal
from execution.telegram_bot import TelegramBot
from models.model_manager import ModelManager
from storage.database import Database

logger = get_logger(__name__)

ASSET = "XAU/USD"
TIMEFRAMES = {
    "5min": 5,
    "15min": 15,
    "1h": 60,
    "4h": 240,
}

_active_cycles: dict[str, bool] = {}
_active_cycles_lock = threading.Lock()


class TradingScheduler:
    def __init__(self, config: AppConfig, database: Database, bot: TelegramBot):
        self._config = config
        self._db = database
        self._bot = bot
        self._provider = get_provider(config)
        self._risk_agent = RiskAgent(config, database)
        self._scheduler = BackgroundScheduler()
        self._historical_data: dict[str, list] = {}
        self._news_agent: NewsAgent | None = None
        if config.rss_feed_urls.strip():
            model_manager = ModelManager(config)
            self._news_agent = NewsAgent(config, database, model_manager)

    def startup_fetch(self) -> None:
        logger.info("Starting historical data fetch for %s", ASSET)
        for tf in TIMEFRAMES:
            bars = self._fetch_with_retry(ASSET, tf, 250)
            if bars:
                self._historical_data[tf] = bars
                logger.info("Fetched %d bars for %s %s", len(bars), ASSET, tf)
            else:
                logger.error(
                    "Failed to fetch historical data for %s %s after retries", ASSET, tf
                )

    def _fetch_with_retry(
        self,
        asset: str,
        timeframe: str,
        bars: int,
        max_retries: int = 5,
        base_delay: float = 1.0,
    ) -> list | None:
        delay = base_delay
        for attempt in range(max_retries):
            try:
                return self._provider.get_ohlc(asset, timeframe, bars)
            except MarketDataError as e:
                logger.warning(
                    "Fetch attempt %d/%d failed for %s %s: %s",
                    attempt + 1,
                    max_retries,
                    asset,
                    timeframe,
                    e,
                )
                if attempt < max_retries - 1:
                    sleep_time = min(delay, 60.0)
                    logger.info("Retrying in %.1fs...", sleep_time)
                    time.sleep(sleep_time)
                    delay = min(delay * 2, 60.0)
        return None

    def _validate_bars(self, bars: list[OHLCBar]) -> list[OHLCBar]:
        valid = []
        rejected = 0
        for bar in bars:
            try:
                if bar.high < max(bar.open, bar.close):
                    raise ValueError(
                        f"high {bar.high} < max(open,close) {max(bar.open, bar.close)}"
                    )
                if bar.low > min(bar.open, bar.close):
                    raise ValueError(
                        f"low {bar.low} > min(open,close) {min(bar.open, bar.close)}"
                    )
                if bar.volume < 0:
                    raise ValueError(f"negative volume {bar.volume}")
                valid.append(bar)
            except (ValueError, TypeError) as e:
                rejected += 1
                logger.warning("Rejecting malformed candle at %s: %s", bar.timestamp, e)
        if rejected > 0:
            logger.warning("Rejected %d/%d malformed candles", rejected, len(bars))
        return valid

    def run_cycle(self, timeframe: str) -> None:
        with _active_cycles_lock:
            if _active_cycles.get(timeframe):
                logger.warning(
                    "Cycle overlap detected for %s %s — skipped by max_instances=1",
                    ASSET,
                    timeframe,
                )
                return
            _active_cycles[timeframe] = True

        logger.info("Running cycle for %s %s", ASSET, timeframe)
        try:
            self._db.reset_daily_if_needed()

            bars = self._fetch_with_retry(ASSET, timeframe, 250)
            if not bars:
                logger.warning("Skipping cycle: no data for %s %s", ASSET, timeframe)
                return

            bars = self._validate_bars(bars)
            if len(bars) < 200:
                logger.warning(
                    "Skipping cycle: only %d valid bars (need 200) for %s %s",
                    len(bars),
                    ASSET,
                    timeframe,
                )
                return

            self._historical_data[timeframe] = bars

            indicators = compute_indicators(bars)

            message = format_indicator_summary(indicators, ASSET, timeframe)
            logger.info("Indicator summary for %s:\n%s", timeframe, message)

            self._bot.broadcast(message)

            self._run_news_agent()

            self._evaluate_signal_if_present(timeframe, indicators)

            self._bot.last_cycle_time = datetime.now(timezone.utc)
            logger.info("Cycle complete for %s %s", ASSET, timeframe)

        except Exception as e:
            logger.error(
                "Cycle error for %s %s: %s", ASSET, timeframe, e, exc_info=True
            )
        finally:
            with _active_cycles_lock:
                _active_cycles[timeframe] = False

    def _evaluate_signal_if_present(self, timeframe: str, indicators) -> None:
        pass

    def _run_news_agent(self) -> None:
        if self._news_agent is None:
            return
        try:
            result = self._news_agent.run()
            logger.info(
                "News sentiment: score=%.3f headlines=%d blackout=%s",
                result.macro_score,
                result.headline_count,
                result.is_blackout,
            )
        except Exception as e:
            logger.warning("News agent failed: %s", e)

    def process_signal(self, signal: TradeSignal) -> None:
        signal_id = self._db.save_signal(signal, "pending")
        logger.info(
            "Signal saved as pending (id=%d): %s %s",
            signal_id,
            signal.direction,
            signal.asset,
        )

        verdict = self._risk_agent.evaluate(signal)

        if verdict.approved:
            self._db.update_signal_status(signal_id, "approved")
            message = format_trade_signal(signal, verdict)
            self._bot.broadcast(message)
            logger.info("Signal approved and broadcast (id=%d)", signal_id)
        else:
            self._db.update_signal_status(signal_id, "rejected")
            logger.info(
                "Signal rejected (id=%d): %s", signal_id, verdict.rejection_reason
            )

    def start(self) -> None:
        for tf, interval_minutes in TIMEFRAMES.items():
            self._scheduler.add_job(
                self.run_cycle,
                "interval",
                minutes=interval_minutes,
                args=[tf],
                id=f"cycle_{tf}",
                max_instances=1,
                replace_existing=True,
            )
            logger.info("Scheduled %s cycle every %d minutes", tf, interval_minutes)

        self._scheduler.start()
        logger.info("Scheduler started with %d timeframes", len(TIMEFRAMES))

    def stop(self) -> None:
        self._scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")

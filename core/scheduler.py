from __future__ import annotations

import threading
import time
from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler

from agents.chart_agent import ChartAgent
from agents.news_agent import NewsAgent
from agents.prediction_agent import PredictionAgent
from agents.risk_agent import RiskAgent
from agents.signal_agent import SignalAgent
from core.config import AppConfig
from core.logger import get_logger
from core.types import (
    IndicatorResult,
    MacroSentiment,
    OHLCBar,
    TimeframeAnalysis,
    TradeSignal,
)
from data.market_data import MarketDataError, get_provider
from execution.signal_generator import format_indicator_summary, format_trade_signal
from execution.telegram_bot import TelegramBot
from agents.signal_agent import _patterns_summary
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

TF_DISPLAY_TO_SHORT = {
    "5min": "5m",
    "15min": "15m",
    "1h": "1h",
    "4h": "4h",
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
        self._model_manager = ModelManager(config)
        self._signal_agent = SignalAgent(config)
        self._chart_agent = ChartAgent()
        self._prediction_agent = PredictionAgent(config, self._model_manager)
        self._last_sentiment: MacroSentiment = MacroSentiment()
        self._news_agent: NewsAgent | None = None
        if config.rss_feed_urls.strip():
            self._news_agent = NewsAgent(config, database, self._model_manager)

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

            short_tf = TF_DISPLAY_TO_SHORT.get(timeframe, timeframe)
            analysis = self._chart_agent.analyze(bars, short_tf)

            message = format_indicator_summary(analysis.indicators, ASSET, timeframe)
            logger.info("Indicator summary for %s:\n%s", timeframe, message)

            self._run_news_agent()

            self._evaluate_signal_if_present(analysis)

            self._bot.last_cycle_time = datetime.now(timezone.utc)
            logger.info("Cycle complete for %s %s", ASSET, timeframe)

        except Exception as e:
            logger.error(
                "Cycle error for %s %s: %s", ASSET, timeframe, e, exc_info=True
            )
        finally:
            with _active_cycles_lock:
                _active_cycles[timeframe] = False

    def _evaluate_signal_if_present(self, analysis: TimeframeAnalysis) -> None:
        prediction = self._prediction_agent.predict(analysis.bars, analysis.indicators)

        logger.info(
            "AUDIT prediction: timeframe=%s direction=%s confidence=%.4f "
            "volatility=%.4f trend_strength=%.4f horizon=%d",
            analysis.timeframe,
            prediction.direction,
            prediction.confidence,
            prediction.volatility,
            prediction.trend_strength,
            prediction.horizon_bars,
        )

        decision = self._signal_agent.decide(
            analysis,
            self._last_sentiment,
            prediction,
            mtf_agreement_fraction=self._compute_mtf_fraction(analysis),
        )

        if decision.direction == "NO_TRADE":
            logger.info(
                "AUDIT no_trade: timeframe=%s probability=%.4f method=%s "
                "clarity=%.3f threshold=%.2f",
                analysis.timeframe,
                decision.probability,
                decision.scoring_method,
                analysis.clarity.composite,
                self._config.signal_threshold,
            )
            return

        if self._config.mtf_confirmation_enabled:
            if not self._check_mtf_agreement(decision.direction, analysis):
                logger.info(
                    "AUDIT mtf_rejected: direction=%s timeframe=%s",
                    decision.direction,
                    analysis.timeframe,
                )
                return

        last_bar = analysis.bars[-1]
        entry_price = last_bar.close
        atr = analysis.indicators.atr
        if decision.direction == "BUY":
            stop_loss = entry_price - self._config.sl_atr_multiplier * atr
            take_profit = entry_price + self._config.tp_atr_multiplier * atr
        else:
            stop_loss = entry_price + self._config.sl_atr_multiplier * atr
            take_profit = entry_price - self._config.tp_atr_multiplier * atr

        signal = TradeSignal(
            asset=ASSET,
            direction=decision.direction,
            entry_price=entry_price,
            stop_loss=round(stop_loss, 2),
            take_profit=round(take_profit, 2),
            probability=decision.probability,
            reasoning=decision.explanation,
            timeframe=analysis.timeframe,
            timestamp=datetime.now(timezone.utc),
        )

        logger.info(
            "AUDIT signal_generated: asset=%s direction=%s entry=%.2f sl=%.2f tp=%.2f "
            "prob=%.4f method=%s clarity=%.3f timeframe=%s",
            signal.asset,
            signal.direction,
            signal.entry_price,
            signal.stop_loss,
            signal.take_profit,
            signal.probability,
            decision.scoring_method,
            analysis.clarity.composite,
            analysis.timeframe,
        )
        self._log_sr_proximity(signal, analysis.indicators)
        self.process_signal(
            signal,
            indicators=analysis.indicators,
            patterns_summary=_patterns_summary(analysis.patterns),
        )

    def _log_sr_proximity(
        self, signal: TradeSignal, indicators: IndicatorResult
    ) -> None:
        if signal.direction == "SELL" and signal.entry_price < indicators.support:
            logger.warning(
                "Entry %.2f below support %.2f — breakout may have already occurred",
                signal.entry_price,
                indicators.support,
            )
        elif signal.direction == "BUY" and signal.entry_price > indicators.resistance:
            logger.warning(
                "Entry %.2f above resistance %.2f — breakout may have already occurred",
                signal.entry_price,
                indicators.resistance,
            )

    def _check_mtf_agreement(
        self, signal_direction: str, analysis: TimeframeAnalysis
    ) -> bool:
        consensus = self._chart_agent.get_trend_consensus(analysis.timeframe)
        target = "bullish" if signal_direction == "BUY" else "bearish"
        agreeing = consensus.get(target, 0)

        if consensus["total"] < self._config.mtf_min_agreeing_timeframes:
            logger.info(
                "AUDIT mtf_confirmation: ALLOWED (cold start) signal=%s "
                "consensus_total=%d < min=%d",
                signal_direction,
                consensus["total"],
                self._config.mtf_min_agreeing_timeframes,
            )
            return True

        if agreeing >= self._config.mtf_min_agreeing_timeframes:
            logger.info(
                "AUDIT mtf_confirmation: PASSED signal=%s target=%s agreeing=%d "
                "total=%d bullish=%d bearish=%d neutral=%d",
                signal_direction,
                target,
                agreeing,
                consensus["total"],
                consensus["bullish"],
                consensus["bearish"],
                consensus["neutral"],
            )
            return True

        logger.info(
            "AUDIT mtf_confirmation: REJECTED signal=%s target=%s agreeing=%d "
            "needed=%d total=%d bullish=%d bearish=%d neutral=%d",
            signal_direction,
            target,
            agreeing,
            self._config.mtf_min_agreeing_timeframes,
            consensus["total"],
            consensus["bullish"],
            consensus["bearish"],
            consensus["neutral"],
        )
        return False

    def _compute_mtf_fraction(self, analysis: TimeframeAnalysis) -> float:
        consensus = self._chart_agent.get_trend_consensus(analysis.timeframe)
        if consensus["total"] == 0:
            return 0.0
        return consensus["total"] / 4.0

    def _run_news_agent(self) -> None:
        if self._news_agent is None:
            return
        try:
            result = self._news_agent.run()
            self._last_sentiment = result
            logger.info(
                "News sentiment: score=%.3f headlines=%d blackout=%s",
                result.macro_score,
                result.headline_count,
                result.is_blackout,
            )
        except Exception as e:
            logger.warning("News agent failed: %s", e)

    def process_signal(
        self,
        signal: TradeSignal,
        indicators: object = None,
        patterns_summary: str | None = None,
    ) -> None:
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
            message = format_trade_signal(
                signal,
                verdict,
                indicators=indicators,
                patterns_summary=patterns_summary,
            )
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

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from agents.chart_agent import ChartAgent
from agents.signal_agent import assemble_features
from backtesting.engine import BacktestEngine
from backtesting.metrics import compute_metrics
from core.config import AppConfig
from core.logger import get_logger
from core.types import (
    MacroSentiment,
    OHLCBar,
    PricePrediction,
)
from models.model_manager import ModelManager
from models.xgboost_model import XGBoostWrapper
from storage.database import Database

logger = get_logger(__name__)


@dataclass
class WindowResult:
    train_period: str
    test_period: str
    is_metrics: dict
    oos_metrics: dict


@dataclass
class WalkForwardResult:
    windows: list[WindowResult] = field(default_factory=list)
    aggregate_oos_return: float = 0.0
    aggregate_oos_win_rate: float = 0.0
    is_vs_oos_divergence: float = 0.0


def create_windows(
    bars: list[OHLCBar],
    train_months: int = 3,
    test_months: int = 1,
) -> list[dict]:
    if not bars:
        raise ValueError("No bars provided for window splitting")

    first_ts: datetime = bars[0].timestamp
    last_ts: datetime = bars[-1].timestamp

    total_months = (last_ts.year - first_ts.year) * 12 + (
        last_ts.month - first_ts.month
    )
    min_months = train_months + test_months * 2
    if total_months < min_months:
        raise ValueError(
            f"{total_months} months of data found. Walk-forward requires at least "
            f"{min_months} months (2 full train+test windows)."
        )

    windows: list[dict] = []
    start_year = first_ts.year
    start_month = first_ts.month

    while True:
        train_start_year, train_start_month = start_year, start_month
        train_end_year, train_end_month = _add_months(
            train_start_year, train_start_month, train_months - 1
        )
        test_start_year, test_start_month = _add_months(
            train_start_year, train_start_month, train_months
        )
        test_end_year, test_end_month = _add_months(
            test_start_year, test_start_month, test_months - 1
        )

        train_start_dt = datetime(train_start_year, train_start_month, 1)
        train_end_dt = _month_end(train_end_year, train_end_month)
        test_start_dt = datetime(test_start_year, test_start_month, 1)
        test_end_dt = _month_end(test_end_year, test_end_month)

        if test_start_dt > last_ts:
            break

        train_bars = [b for b in bars if train_start_dt <= b.timestamp <= train_end_dt]
        test_bars = [b for b in bars if test_start_dt <= b.timestamp <= test_end_dt]

        if len(train_bars) < 200:
            start_year, start_month = _add_months(start_year, start_month, test_months)
            continue

        train_period = (
            f"{train_start_year}-{train_start_month:02d} \u2192 "
            f"{train_end_year}-{train_end_month:02d}"
        )
        test_period = f"{test_start_year}-{test_start_month:02d}"

        windows.append(
            {
                "train_bars": train_bars,
                "test_bars": test_bars,
                "train_period": train_period,
                "test_period": test_period,
            }
        )

        start_year, start_month = _add_months(start_year, start_month, test_months)

    if len(windows) < 2:
        raise ValueError(
            f"Only {len(windows)} window(s) created. Walk-forward requires at least 2 windows."
        )

    return windows


def _add_months(year: int, month: int, delta: int) -> tuple[int, int]:
    total = year * 12 + (month - 1) + delta
    return total // 12, total % 12 + 1


def _month_end(year: int, month: int) -> datetime:
    import calendar

    last_day = calendar.monthrange(year, month)[1]
    return datetime(year, month, last_day, 23, 59, 59)


class WalkForwardOptimizer:
    def __init__(
        self,
        config: AppConfig,
        database: Database,
        bars: list[OHLCBar],
        timeframe: str = "1h",
        initial_capital: float = 10000.0,
        sentiment_score: float = 0.0,
    ):
        self._config = config
        self._database = database
        self._bars = bars
        self._timeframe = timeframe
        self._initial_capital = initial_capital
        self._sentiment_score = sentiment_score

    def run(self, train_months: int = 3, test_months: int = 1) -> WalkForwardResult:
        windows = create_windows(self._bars, train_months, test_months)
        chart_agent = ChartAgent()
        model_manager = ModelManager(self._config)
        xgb = XGBoostWrapper(self._config)

        result = WalkForwardResult()
        is_returns: list[float] = []
        oos_returns: list[float] = []
        oos_wins: list[float] = []
        oos_total: list[int] = []

        for idx, window in enumerate(windows):
            logger.info(
                "Walk-forward window %d/%d: train=%s test=%s",
                idx + 1,
                len(windows),
                window["train_period"],
                window["test_period"],
            )

            train_bars = window["train_bars"]
            test_bars = window["test_bars"]

            features, labels = self._build_training_data(
                train_bars, chart_agent, model_manager
            )

            if features and labels:
                try:
                    xgb.train(features, labels)
                    logger.info("XGBoost retrained on window %d", idx + 1)
                except Exception as e:
                    logger.warning(
                        "XGBoost retrain failed for window %d: %s", idx + 1, e
                    )

            is_result = self._run_sub_backtest(train_bars)
            oos_result = self._run_sub_backtest(test_bars)

            is_metrics = compute_metrics(is_result)
            oos_metrics = compute_metrics(oos_result)

            result.windows.append(
                WindowResult(
                    train_period=window["train_period"],
                    test_period=window["test_period"],
                    is_metrics=is_metrics,
                    oos_metrics=oos_metrics,
                )
            )

            is_returns.append(is_metrics.get("total_return", 0.0))
            oos_returns.append(oos_metrics.get("total_return", 0.0))

            if not oos_metrics.get("no_trades", False):
                oos_wins.append(oos_metrics.get("win_rate", 0.0))
                oos_total.append(oos_metrics.get("total_trades", 0))

        if oos_returns:
            result.aggregate_oos_return = sum(oos_returns) / len(oos_returns)
        if oos_wins:
            result.aggregate_oos_win_rate = sum(oos_wins) / len(oos_wins)
        if is_returns and oos_returns:
            avg_is = sum(is_returns) / len(is_returns)
            avg_oos = sum(oos_returns) / len(oos_returns)
            result.is_vs_oos_divergence = abs(avg_is - avg_oos)

        return result

    def _build_training_data(
        self,
        train_bars: list[OHLCBar],
        chart_agent: ChartAgent,
        model_manager: ModelManager,
    ) -> tuple[list, list[int]]:
        features: list = []
        labels: list[int] = []
        horizon = 12
        threshold = 0.001

        for i in range(200, len(train_bars) - horizon):
            window = train_bars[max(0, i - 250) : i + 1]
            if len(window) < 200:
                continue

            try:
                analysis = chart_agent.analyze(window, self._timeframe)
            except Exception:
                continue

            sentiment = MacroSentiment(
                macro_score=self._sentiment_score,
                headline_count=0,
                is_blackout=False,
            )

            prediction = PricePrediction(
                direction="NEUTRAL",
                confidence=0.0,
                volatility=0.0,
                trend_strength=0.0,
                horizon_bars=12,
            )

            try:
                fv = assemble_features(analysis, sentiment, prediction)
            except Exception:
                continue

            current_close = train_bars[i].close
            future_close = train_bars[i + horizon].close
            change = (future_close - current_close) / current_close

            if change > threshold:
                label = 1
            elif change < -threshold:
                label = 0
            else:
                continue

            features.append(fv)
            labels.append(label)

        return features, labels

    def _run_sub_backtest(self, bars: list[OHLCBar]) -> object:
        from backtesting.engine import BacktestResult

        if len(bars) < 200:
            return BacktestResult(
                initial_capital=self._initial_capital,
                final_capital=self._initial_capital,
                start_date=bars[0].timestamp if bars else None,
                end_date=bars[-1].timestamp if bars else None,
                total_bars=len(bars),
            )

        engine = BacktestEngine(
            config=self._config,
            database=self._database,
            bars=bars,
            timeframe=self._timeframe,
            initial_capital=self._initial_capital,
            sentiment_score=self._sentiment_score,
            verbose=False,
        )
        return engine.run()

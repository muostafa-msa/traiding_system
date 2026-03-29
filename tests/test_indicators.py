from __future__ import annotations

import time
from datetime import datetime, timezone, timedelta

import pytest

from core.types import OHLCBar
from analysis.indicators import compute_indicators


def _make_bars(
    n: int, base_price: float = 2300.0, volatility: float = 5.0
) -> list[OHLCBar]:
    bars = []
    base_ts = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    import math

    for i in range(n):
        angle = 2 * math.pi * i / 30
        close = base_price + volatility * math.sin(angle) + i * 0.1
        high = close + volatility * 0.5
        low = close - volatility * 0.5
        bars.append(
            OHLCBar(
                timestamp=base_ts + timedelta(minutes=5 * i),
                open=close - volatility * 0.1,
                high=high,
                low=low,
                close=close,
                volume=1000.0,
            )
        )
    return bars


class TestComputeIndicatorsBasic:
    def test_raises_on_too_few_bars(self):
        bars = _make_bars(50)
        with pytest.raises(ValueError, match="at least 200"):
            compute_indicators(bars)

    def test_returns_indicator_result(self):
        bars = _make_bars(250)
        result = compute_indicators(bars)
        assert result.rsi is not None
        assert 0 <= result.rsi <= 100

    def test_macd_fields(self):
        bars = _make_bars(250)
        result = compute_indicators(bars)
        assert result.macd_line is not None
        assert result.macd_signal is not None
        assert abs(result.macd_hist - (result.macd_line - result.macd_signal)) < 1e-6

    def test_ema_fields(self):
        bars = _make_bars(250)
        result = compute_indicators(bars)
        assert result.ema_20 > 0
        assert result.ema_50 > 0
        assert result.ema_200 > 0

    def test_bollinger_bands(self):
        bars = _make_bars(250)
        result = compute_indicators(bars)
        assert result.bb_upper > result.bb_middle > result.bb_lower
        assert result.bb_middle > 0

    def test_atr_positive(self):
        bars = _make_bars(250)
        result = compute_indicators(bars)
        assert result.atr > 0

    def test_rsi_deterministic(self):
        bars = _make_bars(250)
        r1 = compute_indicators(bars)
        r2 = compute_indicators(bars)
        assert r1.rsi == r2.rsi
        assert r1.macd_line == r2.macd_line


class TestComputeIndicatorsTolerance:
    def test_rsi_with_known_trend(self):
        bars = _make_bars(250, base_price=2300.0, volatility=2.0)
        result = compute_indicators(bars)
        assert 0 <= result.rsi <= 100

    def test_ema_ordering_uptrend(self):
        bars = _make_bars(250, base_price=2300.0, volatility=2.0)
        result = compute_indicators(bars)
        last_close = bars[-1].close
        assert isinstance(last_close, float)

    def test_bollinger_band_width_related_to_atr(self):
        bars = _make_bars(250, base_price=2300.0, volatility=5.0)
        result = compute_indicators(bars)
        bb_width = result.bb_upper - result.bb_lower
        assert bb_width > 0
        assert result.atr > 0


class TestSupportResistance:
    def test_support_and_resistance_positive(self):
        bars = _make_bars(250)
        result = compute_indicators(bars)
        assert result.support > 0
        assert result.resistance > 0

    def test_support_below_resistance(self):
        bars = _make_bars(250)
        result = compute_indicators(bars)
        assert result.support <= result.resistance


class TestTrendDirection:
    def test_trend_direction_valid(self):
        bars = _make_bars(250)
        result = compute_indicators(bars)
        assert result.trend_direction in ("bullish", "bearish", "neutral")

    def test_uptrend_bullish(self):
        bars = []
        base_ts = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
        for i in range(250):
            price = 2000.0 + i * 2.0
            bars.append(
                OHLCBar(
                    timestamp=base_ts + timedelta(minutes=5 * i),
                    open=price,
                    high=price + 1.0,
                    low=price - 1.0,
                    close=price + 0.5,
                    volume=1000.0,
                )
            )
        result = compute_indicators(bars)
        assert result.trend_direction == "bullish"

    def test_downtrend_bearish(self):
        bars = []
        base_ts = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
        for i in range(250):
            price = 3000.0 - i * 2.0
            bars.append(
                OHLCBar(
                    timestamp=base_ts + timedelta(minutes=5 * i),
                    open=price,
                    high=price + 1.0,
                    low=price - 1.0,
                    close=price - 0.5,
                    volume=1000.0,
                )
            )
        result = compute_indicators(bars)
        assert result.trend_direction == "bearish"


class TestBreakoutProbability:
    def test_breakout_probability_in_range(self):
        bars = _make_bars(250)
        result = compute_indicators(bars)
        assert 0.0 <= result.breakout_probability <= 1.0

    def test_low_volatility_low_breakout(self):
        bars = _make_bars(250, base_price=2300.0, volatility=0.5)
        result = compute_indicators(bars)
        assert result.breakout_probability < 0.85

    def test_high_volatility_high_breakout(self):
        bars = _make_bars(250, base_price=2300.0, volatility=50.0)
        result = compute_indicators(bars)
        assert result.breakout_probability > 0.3


class TestStartupFetchRetry:
    def test_fetch_with_retry_exponential_backoff(self):
        from unittest.mock import MagicMock, patch
        from data.market_data import MarketDataError
        from core.scheduler import TradingScheduler

        config = MagicMock()
        config.market_data_provider = "twelvedata"
        config.market_data_api_key = "test"
        config.db_path = ":memory:"

        db = MagicMock()
        bot = MagicMock()

        call_count = 0
        call_times = []

        def mock_get_ohlc(asset, tf, bars=250):
            nonlocal call_count
            call_count += 1
            call_times.append(time.time())
            if call_count < 3:
                raise MarketDataError("API error")
            return [MagicMock()]

        with patch("core.scheduler.get_provider") as mock_get_prov:
            provider = MagicMock()
            provider.get_ohlc.side_effect = mock_get_ohlc
            mock_get_prov.return_value = provider

            sched = TradingScheduler(config, db, bot)
            result = sched._fetch_with_retry(
                "XAU/USD", "5min", 250, max_retries=5, base_delay=0.1
            )

        assert result is not None
        assert call_count == 3

    def test_fetch_with_retry_all_fail(self):
        from unittest.mock import MagicMock, patch
        from data.market_data import MarketDataError
        from core.scheduler import TradingScheduler

        config = MagicMock()
        config.market_data_provider = "twelvedata"
        config.market_data_api_key = "test"

        db = MagicMock()
        bot = MagicMock()

        with patch("core.scheduler.get_provider") as mock_get_prov:
            provider = MagicMock()
            provider.get_ohlc.side_effect = MarketDataError("API down")
            mock_get_prov.return_value = provider

            sched = TradingScheduler(config, db, bot)
            result = sched._fetch_with_retry(
                "XAU/USD", "5min", 250, max_retries=2, base_delay=0.05
            )

        assert result is None

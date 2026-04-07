from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone

import requests

from core.config import AppConfig
from core.logger import get_logger
from core.types import OHLCBar

logger = get_logger(__name__)

TF_MAP = {
    "5min": ("5min", "5min"),
    "15min": ("15min", "15min"),
    "1h": ("60min", "60min"),
    "4h": ("4h", "4h"),
}


class MarketDataError(Exception):
    pass


class MarketDataProvider(ABC):
    @abstractmethod
    def get_ohlc(
        self, asset: str, timeframe: str, bars: int = 250
    ) -> list[OHLCBar]: ...


class TwelveDataProvider(MarketDataProvider):
    TF_MAP = {"5min": "5min", "15min": "15min", "1h": "1h", "4h": "4h"}

    def __init__(self, api_key: str):
        self._api_key = api_key
        self._base_url = "https://api.twelvedata.com/time_series"

    def get_ohlc(self, asset: str, timeframe: str, bars: int = 250) -> list[OHLCBar]:
        symbol = asset
        interval = self.TF_MAP.get(timeframe)
        if interval is None:
            raise MarketDataError(f"Unsupported timeframe: {timeframe}")

        params = {
            "symbol": symbol,
            "interval": interval,
            "outputsize": bars,
            "apikey": self._api_key,
        }

        try:
            resp = requests.get(self._base_url, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as e:
            raise MarketDataError(f"TwelveData API error: {e}") from e

        if "status" in data and data["status"] == "error":
            raise MarketDataError(
                f"TwelveData API error: {data.get('message', 'unknown')}"
            )

        values = data.get("values", [])
        if not values:
            raise MarketDataError("TwelveData returned empty data")

        result = []
        for v in reversed(values):
            try:
                result.append(
                    OHLCBar(
                        timestamp=datetime.fromisoformat(v["datetime"]).replace(
                            tzinfo=timezone.utc
                        ),
                        open=float(v["open"]),
                        high=float(v["high"]),
                        low=float(v["low"]),
                        close=float(v["close"]),
                        volume=float(v.get("volume", 0)),
                    )
                )
            except (KeyError, ValueError) as e:
                logger.warning("Skipping malformed candle: %s", e)
                continue

        return result


class AlphaVantageProvider(MarketDataProvider):
    TF_MAP = {"5min": "5min", "15min": "15min", "1h": "60min", "4h": "60min"}

    def __init__(self, api_key: str):
        self._api_key = api_key
        self._base_url = "https://www.alphavantage.co/query"

    def get_ohlc(self, asset: str, timeframe: str, bars: int = 250) -> list[OHLCBar]:
        parts = asset.split("/")
        from_sym = parts[0] if len(parts) > 0 else asset
        to_sym = parts[1] if len(parts) > 1 else "USD"

        fn = (
            "TIME_SERIES_INTRADAY"
            if timeframe in ("5min", "15min", "1h", "4h")
            else "TIME_SERIES_DAILY"
        )
        interval = self.TF_MAP.get(timeframe, "60min")

        params = {
            "function": fn,
            "symbol": from_sym,
            "apikey": self._api_key,
            "outputsize": "full" if bars > 100 else "compact",
        }
        if fn == "TIME_SERIES_INTRADAY":
            params["interval"] = interval

        try:
            resp = requests.get(self._base_url, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as e:
            raise MarketDataError(f"AlphaVantage API error: {e}") from e

        if "Error Message" in data:
            raise MarketDataError(f"AlphaVantage error: {data['Error Message']}")
        if "Note" in data:
            raise MarketDataError("AlphaVantage rate limit reached")

        ts_key = None
        for key in data:
            if "Time Series" in key:
                ts_key = key
                break
        if ts_key is None:
            raise MarketDataError("AlphaVantage: no time series data in response")

        series = data[ts_key]
        result = []
        for ts_str in sorted(series.keys()):
            v = series[ts_str]
            try:
                result.append(
                    OHLCBar(
                        timestamp=datetime.fromisoformat(ts_str).replace(
                            tzinfo=timezone.utc
                        ),
                        open=float(v["1. open"]),
                        high=float(v["2. high"]),
                        low=float(v["3. low"]),
                        close=float(v["4. close"]),
                        volume=float(v.get("5. volume", 0)),
                    )
                )
            except (KeyError, ValueError) as e:
                logger.warning("Skipping malformed candle: %s", e)
                continue

        return result[-bars:]


class PolygonProvider(MarketDataProvider):
    TF_MAP = {"5min": "5", "15min": "15", "1h": "60", "4h": "240"}

    def __init__(self, api_key: str):
        self._api_key = api_key
        self._base_url = "https://api.polygon.io/v2/aggs/ticker"

    def get_ohlc(self, asset: str, timeframe: str, bars: int = 250) -> list[OHLCBar]:
        ticker = asset.replace("/", "").replace("XAU", "O:XAU").replace("USD", "USD")
        if not ticker.startswith("O:"):
            ticker = f"C:{ticker}"
        multiplier = self.TF_MAP.get(timeframe, "5")
        timespan = (
            "minute"
            if timeframe in ("5min", "15min")
            else "hour"
            if timeframe in ("1h", "4h")
            else "minute"
        )

        url = f"{self._base_url}/{ticker}/range/{multiplier}/{timespan}/prev"
        params = {
            "adjusted": "true",
            "limit": bars,
            "apiKey": self._api_key,
        }

        try:
            resp = requests.get(url, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as e:
            raise MarketDataError(f"Polygon API error: {e}") from e

        if data.get("status") == "ERROR":
            raise MarketDataError(f"Polygon error: {data.get('error', 'unknown')}")

        results = data.get("results", [])
        if not results:
            raise MarketDataError("Polygon returned empty data")

        ohlc_bars = []
        for v in results:
            try:
                ohlc_bars.append(
                    OHLCBar(
                        timestamp=datetime.fromtimestamp(
                            v["t"] / 1000, tz=timezone.utc
                        ),
                        open=float(v["o"]),
                        high=float(v["h"]),
                        low=float(v["l"]),
                        close=float(v["c"]),
                        volume=float(v.get("v", 0)),
                    )
                )
            except (KeyError, ValueError) as e:
                logger.warning("Skipping malformed candle: %s", e)
                continue

        return ohlc_bars


def get_provider(config: AppConfig) -> MarketDataProvider:
    name = config.market_data_provider.lower()
    providers = {
        "twelvedata": TwelveDataProvider,
        "alphavantage": AlphaVantageProvider,
        "polygon": PolygonProvider,
    }
    cls = providers.get(name)
    if cls is None:
        raise MarketDataError(
            f"Unknown provider: {name}. Supported: {list(providers.keys())}"
        )
    return cls(config.market_data_api_key)

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

from core.logger import get_logger
from core.types import OHLCBar

logger = get_logger(__name__)


def load_csv(path: str, format: str = "auto") -> list[OHLCBar]:
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"CSV file not found: {path}")

    with open(file_path, "r", newline="") as f:
        sample = f.read(4096)

    if not sample.strip():
        raise ValueError("CSV file is empty")

    try:
        dialect = csv.Sniffer().sniff(sample, delimiters="\t,")
    except csv.Error:
        dialect = "excel"

    with open(file_path, "r", newline="") as f:
        reader = csv.reader(f, dialect=dialect)
        rows = list(reader)

    if not rows:
        raise ValueError("CSV file is empty")
    if format == "auto":
        format = _detect_format(rows[0])
    if format == "generic":
        bars = _parse_generic(rows)
    elif format == "mt4":
        bars = _parse_mt4(rows)
    elif format == "tradingview":
        bars = _parse_tradingview(rows)
    else:
        raise ValueError(
            "Cannot detect CSV format. Expected MT4, TradingView, or generic OHLCV headers."
        )
    bars = _deduplicate(bars)
    bars.sort(key=lambda b: b.timestamp)
    if len(bars) < 200:
        raise ValueError(
            f"Only {len(bars)} valid bars found. Minimum 200 required for backtesting."
        )
    logger.info("Loaded %d bars from %s (format=%s)", len(bars), file_path.name, format)
    return bars


def _detect_format(header_row: list[str]) -> str:
    normalized = [h.strip().lower() for h in header_row]
    if any("<" in h for h in header_row):
        return "mt4"
    if normalized and normalized[0] == "time" and "open" in normalized:
        return "tradingview"
    if "datetime" in normalized or "date" in normalized:
        return "generic"
    header_raw = [h.strip() for h in header_row]
    if header_raw and "date" in header_raw[0].lower() and "time" in header_raw[0].lower():
        return "mt4"
    raise ValueError(
        "Cannot detect CSV format. Expected MT4, TradingView, or generic OHLCV headers."
    )


def _parse_generic(rows: list[list[str]]) -> list[OHLCBar]:
    bars: list[OHLCBar] = []
    header = [h.strip().lower() for h in rows[0]]
    dt_idx = _find_col(header, ["datetime", "date"])
    o_idx = _find_col(header, ["open"])
    h_idx = _find_col(header, ["high"])
    l_idx = _find_col(header, ["low"])
    c_idx = _find_col(header, ["close"])
    v_idx = _find_col(header, ["volume"], default=None)
    for row in rows[1:]:
        if not row or not row[0].strip():
            continue
        try:
            ts = _parse_datetime(row[dt_idx])
            bar = OHLCBar(
                timestamp=ts,
                open=float(row[o_idx]),
                high=float(row[h_idx]),
                low=float(row[l_idx]),
                close=float(row[c_idx]),
                volume=float(row[v_idx]) if v_idx is not None else 0.0,
            )
            bars.append(bar)
        except (ValueError, IndexError) as e:
            logger.warning("Skipping invalid row in generic CSV: %s", e)
            continue
    return bars


def _parse_mt4(rows: list[list[str]]) -> list[OHLCBar]:
    bars: list[OHLCBar] = []
    header = [h.strip().lower().strip("<>") for h in rows[0]]
    date_idx = _find_col(header, ["date"])
    time_idx = _find_col(header, ["time"])
    o_idx = _find_col(header, ["open"])
    h_idx = _find_col(header, ["high"])
    l_idx = _find_col(header, ["low"])
    c_idx = _find_col(header, ["close"])
    v_idx = _find_col(header, ["vol", "volume"], default=None)
    for row in rows[1:]:
        if not row or not row[0].strip():
            continue
        try:
            date_str = row[date_idx].strip()
            time_str = row[time_idx].strip()
            ts = datetime.strptime(f"{date_str} {time_str}", "%Y.%m.%d %H:%M")
            bar = OHLCBar(
                timestamp=ts,
                open=float(row[o_idx]),
                high=float(row[h_idx]),
                low=float(row[l_idx]),
                close=float(row[c_idx]),
                volume=float(row[v_idx]) if v_idx is not None else 0.0,
            )
            bars.append(bar)
        except (ValueError, IndexError) as e:
            logger.warning("Skipping invalid row in MT4 CSV: %s", e)
            continue
    return bars


def _parse_tradingview(rows: list[list[str]]) -> list[OHLCBar]:
    bars: list[OHLCBar] = []
    header = [h.strip().lower() for h in rows[0]]
    t_idx = _find_col(header, ["time"])
    o_idx = _find_col(header, ["open"])
    h_idx = _find_col(header, ["high"])
    l_idx = _find_col(header, ["low"])
    c_idx = _find_col(header, ["close"])
    v_idx = _find_col(header, ["volume"], default=None)
    for row in rows[1:]:
        if not row or not row[0].strip():
            continue
        try:
            ts = _parse_iso_datetime(row[t_idx])
            bar = OHLCBar(
                timestamp=ts,
                open=float(row[o_idx]),
                high=float(row[h_idx]),
                low=float(row[l_idx]),
                close=float(row[c_idx]),
                volume=float(row[v_idx]) if v_idx is not None else 0.0,
            )
            bars.append(bar)
        except (ValueError, IndexError) as e:
            logger.warning("Skipping invalid row in TradingView CSV: %s", e)
            continue
    return bars


def _find_col(header: list[str], names: list[str], default: int | None = None) -> int:
    for name in names:
        for i, h in enumerate(header):
            if h == name:
                return i
    if default is not None:
        return default
    raise ValueError(f"Column not found: expected one of {names}")


def _parse_datetime(value: str) -> datetime:
    value = value.strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d", "%Y/%m/%d %H:%M"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    raise ValueError(f"Cannot parse datetime: {value}")


def _parse_iso_datetime(value: str) -> datetime:
    from datetime import timezone

    value = value.strip()
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt.replace(tzinfo=None)
    except ValueError:
        pass
    return _parse_datetime(value)


def _deduplicate(bars: list[OHLCBar]) -> list[OHLCBar]:
    seen: dict[datetime, OHLCBar] = {}
    for bar in bars:
        seen[bar.timestamp] = bar
    return list(seen.values())

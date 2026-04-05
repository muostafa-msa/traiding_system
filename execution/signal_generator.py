from __future__ import annotations

from core.types import IndicatorResult, TradeSignal, RiskVerdict


def format_indicator_summary(
    indicators: IndicatorResult, asset: str = "XAU/USD", timeframe: str = "1h"
) -> str:
    trend_emoji = {"bullish": "🟢", "bearish": "🔴", "neutral": "🟡"}
    emoji = trend_emoji.get(indicators.trend_direction, "🟡")

    lines = [
        f"{emoji} GOLD TECHNICAL ANALYSIS ({timeframe})",
        f"Asset: {asset}",
        "",
        f"Trend: {indicators.trend_direction.upper()}",
        f"Breakout Probability: {indicators.breakout_probability:.0%}",
        "",
        "── Oscillators ──",
        f"RSI(14): {indicators.rsi:.1f}",
        f"MACD: {indicators.macd_line:.2f} / Signal: {indicators.macd_signal:.2f} / Hist: {indicators.macd_hist:.2f}",
        "",
        "── Moving Averages ──",
        f"EMA 20: {indicators.ema_20:.2f}",
        f"EMA 50: {indicators.ema_50:.2f}",
        f"EMA 200: {indicators.ema_200:.2f}",
        "",
        "── Volatility ──",
        f"BB Upper: {indicators.bb_upper:.2f}",
        f"BB Middle: {indicators.bb_middle:.2f}",
        f"BB Lower: {indicators.bb_lower:.2f}",
        f"ATR(14): {indicators.atr:.2f}",
        "",
        "── Key Levels ──",
        f"Support: {indicators.support:.2f}",
        f"Resistance: {indicators.resistance:.2f}",
    ]
    return "\n".join(lines)


def format_trade_signal(signal: TradeSignal, risk: RiskVerdict) -> str:
    dir_emoji = "🟢" if signal.direction == "BUY" else "🔴"
    lines = [
        f"{dir_emoji} GOLD SIGNAL",
        f"Asset: {signal.asset}",
        f"Direction: {signal.direction}",
        f"Entry: {signal.entry_price:.2f}",
        f"Stop Loss: {signal.stop_loss:.2f}",
        f"Take Profit: {signal.take_profit:.2f}",
        f"Position Size: {risk.position_size:.4f}",
        f"Confidence: {signal.probability:.0%}",
        "",
        f"── Analysis ──",
        f"{signal.reasoning}",
    ]
    return "\n".join(lines)

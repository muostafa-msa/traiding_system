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


def format_performance_summary(summary: dict) -> str:
    period_labels = {
        "daily": "Today",
        "weekly": "Last 7 Days",
        "monthly": "Last 30 Days",
        "all": "All Time",
    }
    label = period_labels.get(summary.get("period", "daily"), "Today")
    total_trades = summary.get("total_trades", 0)
    total_signals = summary.get("total_signals", 0)

    if total_trades == 0 and total_signals == 0:
        return (
            f"PERFORMANCE ({label})\n"
            f"\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2501\n"
            f"No trading activity.\n"
            f"Signals: 0 | Trades: 0"
        )

    pf = summary.get("profit_factor", 0.0)
    if pf == float("inf"):
        pf_str = "\u221e"
    else:
        pf_str = f"{pf:.2f}"

    net = summary.get("net_pnl", 0.0)
    sign = "+" if net >= 0 else ""
    net_str = f"{sign}{net:.2f}"

    wr = summary.get("win_rate", 0.0) * 100

    md = summary.get("max_drawdown", 0.0)
    tr = summary.get("total_return", 0.0)
    tr_sign = "+" if tr >= 0 else ""

    return (
        f"PERFORMANCE ({label})\n"
        f"\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2501\n"
        f"Signals: {total_signals}\n"
        f"Trades: {total_trades} ({summary.get('open_trades', 0)} open)\n"
        f"Wins: {summary.get('wins', 0)} | Losses: {summary.get('losses', 0)}\n"
        f"Win Rate: {wr:.1f}%\n"
        f"Profit Factor: {pf_str}\n"
        f"Net P&L: {net_str}\n"
        f"Sharpe Ratio: {summary.get('sharpe_ratio', 0.0):.2f}\n"
        f"Max Drawdown: {md:.1f}%\n"
        f"Total Return: {tr_sign}{tr:.1f}%"
    )


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

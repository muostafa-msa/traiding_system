# Contract: Telegram Trade Signal Message Format

**Feature**: 006-signal-quality-filters
**Date**: 2026-04-07

## Overview

Defines the format of trade signal messages broadcast to the Telegram channel.

## Message Template

```
{dir_emoji} XAU/USD {DIRECTION}
━━━━━━━━━━━━━━━━━━━━━━
Entry: {entry_price:.2f}
Stop Loss: {stop_loss:.2f} ({sl_distance_sign}{sl_distance:.2f})
Take Profit: {take_profit:.2f} ({tp_distance_sign}{tp_distance:.2f})
Risk:Reward: 1:{rr_ratio:.2f}

Position: {position_size:.2f} oz (~${dollar_risk:.0f} risk)
Confidence: {probability:.0%}

── Market Context ──
Trend: {trend_direction}
Pattern: {pattern_summary}
RSI: {rsi:.1f} | MACD: {macd_description}

── AI Analysis ──
{explanation_text}
```

## Field Definitions

| Field | Source | Format | Example |
|-------|--------|--------|---------|
| dir_emoji | signal.direction | emoji | "🔴" (SELL) or "🟢" (BUY) |
| DIRECTION | signal.direction | string | "SELL" or "BUY" |
| entry_price | signal.entry_price | 2 decimals | 4650.42 |
| stop_loss | signal.stop_loss | 2 decimals | 4657.07 |
| sl_distance | abs(stop_loss - entry_price) | signed, 2 decimals | +6.65 |
| take_profit | signal.take_profit | 2 decimals | 4636.84 |
| tp_distance | abs(take_profit - entry_price) | signed, 2 decimals | -13.58 |
| rr_ratio | tp_distance / sl_distance | 2 decimals | 2.04 |
| position_size | risk.position_size | 2 decimals | 15.04 |
| dollar_risk | position_size * sl_distance | integer | 100 |
| probability | signal.probability | percentage | 83% |
| trend_direction | indicators.trend_direction | capitalized | "Bearish" |
| pattern_summary | strongest pattern or "None detected" | type + confidence | "Double Top (86%)" |
| rsi | indicators.rsi | 1 decimal | 38.1 |
| macd_description | derived from macd_hist | string | "Bearish crossover" |
| explanation_text | signal.reasoning | multiline | AI-generated text |

## Behavior Rules

1. `sl_distance` sign: "+" for SELL (SL above entry), "-" for BUY (SL below entry)
2. `tp_distance` sign: "-" for SELL (TP below entry), "+" for BUY (TP above entry)
3. If no pattern detected: show "None detected" instead of omitting the line
4. If explanation_text is empty or unavailable: show "Analysis unavailable"
5. dollar_risk is approximate (position_size * price_distance_to_SL)

## Function Signature

```python
def format_trade_signal(
    signal: TradeSignal,
    risk: RiskVerdict,
    *,
    indicators: IndicatorResult | None = None,
    patterns_summary: str | None = None,
) -> str:
```

Keyword arguments with defaults ensure backward compatibility with existing callers.

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from backtesting.engine import BacktestResult

if TYPE_CHECKING:
    from backtesting.walk_forward import WalkForwardResult

_BORDER = "\u2550" * 45
_SEPARATOR = "\u2500" * 6


def compute_metrics(result: BacktestResult) -> dict:
    trades = result.trades
    if not trades:
        return {
            "total_trades": 0,
            "wins": 0,
            "losses": 0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "sharpe_ratio": 0.0,
            "max_drawdown": 0.0,
            "avg_reward_risk": 0.0,
            "total_return": 0.0,
            "no_trades": True,
        }

    wins = sum(1 for t in trades if t["pnl"] > 0)
    losses = sum(1 for t in trades if t["pnl"] <= 0)
    total = len(trades)
    win_rate = wins / total if total > 0 else 0.0

    gross_profit = sum(t["pnl"] for t in trades if t["pnl"] > 0)
    gross_loss = abs(sum(t["pnl"] for t in trades if t["pnl"] < 0))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

    equity_curve = _build_equity_curve(result)
    sharpe_ratio = _compute_sharpe(equity_curve)
    max_drawdown = _compute_max_drawdown(equity_curve)

    rr_ratios = []
    for t in trades:
        entry = t["entry_price"]
        sl = t["stop_loss"]
        tp = t["take_profit"]
        risk = abs(entry - sl)
        reward = abs(tp - entry)
        if risk > 0:
            rr_ratios.append(reward / risk)
    avg_rr = sum(rr_ratios) / len(rr_ratios) if rr_ratios else 0.0

    total_return = (
        (result.final_capital - result.initial_capital) / result.initial_capital
        if result.initial_capital > 0
        else 0.0
    )

    return {
        "total_trades": total,
        "wins": wins,
        "losses": losses,
        "win_rate": win_rate,
        "profit_factor": profit_factor,
        "sharpe_ratio": sharpe_ratio,
        "max_drawdown": max_drawdown,
        "avg_reward_risk": avg_rr,
        "total_return": total_return,
        "no_trades": False,
    }


def _build_equity_curve(result: BacktestResult) -> list[float]:
    curve = [result.initial_capital]
    equity = result.initial_capital
    for t in result.trades:
        equity += t["pnl"]
        curve.append(equity)
    return curve


def _compute_sharpe(equity_curve: list[float]) -> float:
    if len(equity_curve) < 2:
        return 0.0

    returns = []
    for i in range(1, len(equity_curve)):
        if equity_curve[i - 1] > 0:
            returns.append(equity_curve[i] / equity_curve[i - 1] - 1.0)

    if not returns:
        return 0.0

    mean_ret = sum(returns) / len(returns)
    variance = sum((r - mean_ret) ** 2 for r in returns) / len(returns)
    std_ret = math.sqrt(variance)

    if std_ret == 0:
        return 0.0

    return mean_ret / std_ret * math.sqrt(252)


def _compute_max_drawdown(equity_curve: list[float]) -> float:
    if len(equity_curve) < 2:
        return 0.0

    peak = equity_curve[0]
    max_dd = 0.0

    for val in equity_curve[1:]:
        if val > peak:
            peak = val
        dd = (peak - val) / peak if peak > 0 else 0.0
        if dd > max_dd:
            max_dd = dd

    return max_dd


def format_report(
    result: BacktestResult, metrics: dict, run_id: int, timeframe: str = "1h"
) -> str:
    lines: list[str] = []

    if metrics.get("no_trades"):
        lines.append(_BORDER)
        lines.append("  BACKTEST RESULTS: XAU/USD")
        if result.start_date is not None and result.end_date is not None:
            lines.append(
                f"  Period: {result.start_date.strftime('%Y-%m-%d')} \u2192 "
                f"{result.end_date.strftime('%Y-%m-%d')}"
            )
        lines.append(_BORDER)
        lines.append("")
        lines.append("  No trades generated.")
        lines.append("")
        lines.append("  Hint: Try lowering the signal threshold or using a")
        lines.append("        different sentiment score to generate more signals.")
        lines.append("")
        lines.append(f"  Run ID: {run_id} (saved to database)")
        lines.append(_BORDER)
        return "\n".join(lines)

    total_ret = metrics.get("total_return", 0.0)
    ret_sign = "+" if total_ret >= 0 else ""
    ret_color = "\033[32m" if total_ret >= 0 else "\033[31m"
    reset = "\033[0m"

    wins = metrics.get("wins", 0)
    losses = metrics.get("losses", 0)
    total_trades = metrics.get("total_trades", 0)
    win_pct = (wins / total_trades * 100) if total_trades > 0 else 0.0
    loss_pct = (losses / total_trades * 100) if total_trades > 0 else 0.0

    pf = metrics.get("profit_factor", 0.0)
    pf_str = f"{pf:.2f}" if pf != float("inf") else "INF"

    lines.append(_BORDER)
    lines.append(f"  BACKTEST RESULTS: XAU/USD ({timeframe})")
    if result.start_date is not None and result.end_date is not None:
        lines.append(
            f"  Period: {result.start_date.strftime('%Y-%m-%d')} \u2192 "
            f"{result.end_date.strftime('%Y-%m-%d')}"
        )
    lines.append(_BORDER)
    lines.append("")
    lines.append(f"  Initial Capital:    ${result.initial_capital:,.2f}")
    lines.append(f"  Final Capital:      ${result.final_capital:,.2f}")
    lines.append(f"  Total Return:       {ret_color}{ret_sign}{total_ret:.2%}{reset}")
    lines.append("")
    lines.append(f"  Total Trades:       {total_trades}")
    lines.append(f"  Wins:               {wins} ({win_pct:.1f}%)")
    lines.append(f"  Losses:             {losses} ({loss_pct:.1f}%)")
    lines.append("")
    lines.append(f"  Profit Factor:      {pf_str}")
    lines.append(f"  Sharpe Ratio:       {metrics.get('sharpe_ratio', 0.0):.2f}")
    lines.append(f"  Max Drawdown:       -{metrics.get('max_drawdown', 0.0):.2%}")
    lines.append(f"  Avg Reward/Risk:    {metrics.get('avg_reward_risk', 0.0):.1f}")
    lines.append("")
    lines.append(f"  Rejected Signals:   {result.rejected_signals}")
    lines.append(f"  Scoring Method:     {result.scoring_method}")
    lines.append("")
    lines.append(f"  Run ID: {run_id} (saved to database)")
    lines.append(_BORDER)

    return "\n".join(lines)


def format_walk_forward_report(
    wf_result: WalkForwardResult,
    run_id: int,
    train_months: int = 3,
    test_months: int = 1,
    timeframe: str = "1h",
) -> str:
    lines: list[str] = []
    num_windows = len(wf_result.windows)

    lines.append(_BORDER)
    lines.append(f"  WALK-FORWARD OPTIMIZATION: XAU/USD ({timeframe})")
    lines.append(
        f"  Windows: {num_windows} ({train_months}-month train / "
        f"{test_months}-month test)"
    )
    lines.append(_BORDER)
    lines.append("")
    lines.append(
        f"  {'Window':<8}{'Train Period':<22}{'Test Period':<22}"
        f"{'OOS Return':<12}{'OOS Win Rate':<12}"
    )
    lines.append(
        f"  {_SEPARATOR:<8}{_SEPARATOR:<22}{_SEPARATOR:<22}"
        f"{_SEPARATOR:<12}{_SEPARATOR:<12}"
    )

    for i, w in enumerate(wf_result.windows):
        oos_ret = w.oos_metrics.get("total_return", 0.0)
        oos_wr = w.oos_metrics.get("win_rate", 0.0)
        ret_sign = "+" if oos_ret >= 0 else ""
        lines.append(
            f"  {i + 1:<8}{w.train_period:<22}{w.test_period:<22}"
            f"{ret_sign}{oos_ret:.1%}{'':>5}{oos_wr:.1%}"
        )

    lines.append("")

    agg_ret_sign = "+" if wf_result.aggregate_oos_return >= 0 else ""
    ret_color = "\033[32m" if wf_result.aggregate_oos_return >= 0 else "\033[31m"
    reset = "\033[0m"

    lines.append(
        f"  Aggregate OOS Return:    "
        f"{ret_color}{agg_ret_sign}{wf_result.aggregate_oos_return:.1%}{reset}"
    )
    lines.append(f"  Aggregate OOS Win Rate:  {wf_result.aggregate_oos_win_rate:.1%}")

    div = wf_result.is_vs_oos_divergence
    if div > 0.20:
        assessment = "high overfitting risk"
    elif div > 0.10:
        assessment = "moderate overfitting risk"
    else:
        assessment = "low overfitting risk"
    lines.append(f"  IS vs OOS Divergence:    {div:.1%} ({assessment})")
    lines.append("")
    lines.append(f"  Run ID: {run_id} (saved to database)")
    lines.append(_BORDER)

    return "\n".join(lines)

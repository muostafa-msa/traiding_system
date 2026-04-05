from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import replace

from backtesting.engine import BacktestEngine
from backtesting.metrics import (
    compute_metrics,
    format_report,
    format_walk_forward_report,
)
from backtesting.walk_forward import WalkForwardOptimizer
from core.config import AppConfig, load_config
from core.logger import get_logger
from data.csv_loader import load_csv
from storage.database import Database

logger = get_logger(__name__)

_REQUIRED_ENV_DEFAULTS = {
    "MARKET_DATA_PROVIDER": "twelvedata",
    "MARKET_DATA_API_KEY": "",
    "INITIAL_CAPITAL": "10000",
    "DB_PATH": ":memory:",
}


def _ensure_env() -> None:
    for key, default in _REQUIRED_ENV_DEFAULTS.items():
        if key not in os.environ:
            os.environ[key] = default


def _patch_config(config: AppConfig, args: argparse.Namespace) -> AppConfig:
    overrides = {}
    if config.db_path == ":memory:":
        overrides["db_path"] = "data/backtest.db"
    return replace(config, **overrides) if overrides else config


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="backtesting.cli",
        description="Backtesting engine for the trading system",
    )
    parser.add_argument("csv_file", help="Path to CSV file with historical OHLCV data")
    parser.add_argument(
        "--capital",
        "-c",
        type=float,
        default=10000.0,
        help="Initial capital (default: 10000)",
    )
    parser.add_argument(
        "--timeframe",
        "-t",
        type=str,
        default="1h",
        help="Bar timeframe: 5min, 15min, 1h, 4h",
    )
    parser.add_argument(
        "--sentiment-score",
        "-s",
        type=float,
        default=0.0,
        help="Sentiment score [-1.0, 1.0]",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show per-trade details during replay",
    )
    parser.add_argument(
        "--walk-forward",
        "-w",
        action="store_true",
        help="Enable walk-forward optimization",
    )
    parser.add_argument(
        "--train-months",
        type=int,
        default=3,
        help="Training window months (walk-forward)",
    )
    parser.add_argument(
        "--test-months",
        type=int,
        default=1,
        help="Testing window months (walk-forward)",
    )

    args = parser.parse_args()

    _ensure_env()
    config = load_config()
    config = _patch_config(config, args)

    try:
        bars = load_csv(args.csv_file)
    except FileNotFoundError:
        print(f"Error: CSV file not found: {args.csv_file}")
        sys.exit(1)
    except ValueError as e:
        msg = str(e)
        if "Cannot detect" in msg:
            print(f"Error: {msg}")
            sys.exit(2)
        elif "valid bars" in msg.lower():
            print(f"Error: {msg}")
            sys.exit(3)
        elif "months" in msg.lower() or "window" in msg.lower():
            print(f"Error: {msg}")
            sys.exit(3)
        else:
            print(f"Error: {msg}")
            sys.exit(2)

    database = Database(config)

    try:
        if args.walk_forward:
            wf = WalkForwardOptimizer(
                config=config,
                database=database,
                bars=bars,
                timeframe=args.timeframe,
                initial_capital=args.capital,
                sentiment_score=args.sentiment_score,
            )

            wf_result = wf.run(args.train_months, args.test_months)

            parameters = json.dumps(
                {
                    "sentiment_score": args.sentiment_score,
                    "signal_threshold": config.signal_threshold,
                    "timeframe": args.timeframe,
                    "walk_forward": {
                        "enabled": True,
                        "train_months": args.train_months,
                        "test_months": args.test_months,
                        "windows": len(wf_result.windows),
                    },
                }
            )

            oos_returns = [
                w.oos_metrics.get("total_return", 0.0) for w in wf_result.windows
            ]
            avg_oos_return = sum(oos_returns) / len(oos_returns) if oos_returns else 0.0
            oos_win_rates = [
                w.oos_metrics.get("win_rate", 0.0)
                for w in wf_result.windows
                if not w.oos_metrics.get("no_trades", False)
            ]
            avg_oos_wr = (
                sum(oos_win_rates) / len(oos_win_rates) if oos_win_rates else 0.0
            )

            run_id = database.save_backtest_run(
                {
                    "csv_file": args.csv_file,
                    "asset": "XAU/USD",
                    "timeframe": args.timeframe,
                    "start_date": bars[0].timestamp.isoformat() if bars else "",
                    "end_date": bars[-1].timestamp.isoformat() if bars else "",
                    "initial_capital": args.capital,
                    "final_capital": args.capital,
                    "total_bars": len(bars),
                    "total_trades": 0,
                    "win_rate": avg_oos_wr,
                    "profit_factor": 0.0,
                    "sharpe_ratio": 0.0,
                    "max_drawdown": 0.0,
                    "avg_reward_risk": 0.0,
                    "total_return": avg_oos_return,
                    "rejected_signals": 0,
                    "parameters": parameters,
                    "scoring_method": "walk_forward",
                }
            )

            report = format_walk_forward_report(
                wf_result,
                run_id,
                args.train_months,
                args.test_months,
                timeframe=args.timeframe,
            )
            print(report)
        else:
            engine = BacktestEngine(
                config=config,
                database=database,
                bars=bars,
                timeframe=args.timeframe,
                initial_capital=args.capital,
                sentiment_score=args.sentiment_score,
                verbose=args.verbose,
            )

            result = engine.run()
            metrics = compute_metrics(result)

            parameters = json.dumps(
                {
                    "sentiment_score": args.sentiment_score,
                    "signal_threshold": config.signal_threshold,
                    "timeframe": args.timeframe,
                }
            )

            run_id = database.save_backtest_run(
                {
                    "csv_file": args.csv_file,
                    "asset": "XAU/USD",
                    "timeframe": args.timeframe,
                    "start_date": result.start_date.isoformat()
                    if result.start_date
                    else "",
                    "end_date": result.end_date.isoformat() if result.end_date else "",
                    "initial_capital": result.initial_capital,
                    "final_capital": result.final_capital,
                    "total_bars": result.total_bars,
                    "total_trades": metrics.get("total_trades", 0),
                    "win_rate": metrics.get("win_rate", 0.0),
                    "profit_factor": metrics.get("profit_factor", 0.0),
                    "sharpe_ratio": metrics.get("sharpe_ratio", 0.0),
                    "max_drawdown": metrics.get("max_drawdown", 0.0),
                    "avg_reward_risk": metrics.get("avg_reward_risk", 0.0),
                    "total_return": metrics.get("total_return", 0.0),
                    "rejected_signals": result.rejected_signals,
                    "parameters": parameters,
                    "scoring_method": result.scoring_method,
                }
            )

            for trade in result.trades:
                database.save_backtest_trade(
                    {
                        "run_id": run_id,
                        "direction": trade["direction"],
                        "entry_bar_index": trade["entry_bar_index"],
                        "exit_bar_index": trade["exit_bar_index"],
                        "entry_timestamp": trade["entry_timestamp"].isoformat(),
                        "exit_timestamp": trade["exit_timestamp"].isoformat(),
                        "entry_price": trade["entry_price"],
                        "exit_price": trade["exit_price"],
                        "stop_loss": trade["stop_loss"],
                        "take_profit": trade["take_profit"],
                        "position_size": trade["position_size"],
                        "pnl": trade["pnl"],
                        "pnl_percent": trade["pnl_percent"],
                        "exit_reason": trade["exit_reason"],
                        "probability": trade["probability"],
                    }
                )

            report = format_report(result, metrics, run_id, timeframe=args.timeframe)
            print(report)
    except ValueError as e:
        msg = str(e)
        if "months" in msg.lower() or "window" in msg.lower():
            print(f"Error: {msg}")
            sys.exit(3)
        print(f"Error: {msg}")
        sys.exit(1)
    except Exception as e:
        logger.error("Backtest failed: %s", e, exc_info=True)
        print(f"Error: {e}")
        sys.exit(1)
    finally:
        database.close()


if __name__ == "__main__":
    main()

from __future__ import annotations

import signal
import sys

from core.config import load_config
from core.logger import get_logger
from core.scheduler import TradingScheduler
from execution.telegram_bot import TelegramBot
from storage.database import Database


def main() -> None:
    config = load_config()
    logger = get_logger("main")
    logger.info("Starting trading system...")

    try:
        db = Database(config)
        db.get_account_state()
        logger.info("Database connection verified")
    except Exception as e:
        logger.critical("Database is inaccessible on startup: %s", e)
        print(f"FATAL: Cannot connect to database: {e}", file=sys.stderr)
        sys.exit(1)

    bot = TelegramBot(config, db)
    scheduler = TradingScheduler(config, db, bot)

    def shutdown(signum, frame):
        logger.info("Shutdown signal received (%s), stopping...", signum)
        scheduler.stop()
        bot.stop()
        db.close()
        logger.info("Trading system stopped")
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    scheduler.startup_fetch()
    bot.start()
    scheduler.start()

    logger.info("Trading system running. Press Ctrl+C to stop.")

    try:
        signal.pause()
    except AttributeError:
        import threading

        stop_event = threading.Event()
        try:
            stop_event.wait()
        except KeyboardInterrupt:
            shutdown(None, None)


if __name__ == "__main__":
    main()

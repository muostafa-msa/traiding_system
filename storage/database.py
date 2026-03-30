from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from core.config import AppConfig
from core.logger import get_logger
from core.types import AccountState, NewsItem, TradeSignal

logger = get_logger(__name__)

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset TEXT NOT NULL,
    direction TEXT NOT NULL,
    entry_price REAL NOT NULL,
    stop_loss REAL NOT NULL,
    take_profit REAL NOT NULL,
    probability REAL NOT NULL,
    timeframe TEXT NOT NULL,
    reasoning TEXT,
    technical_score REAL,
    pattern_score REAL,
    sentiment_score REAL,
    volatility_factor REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'pending'
);

CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    signal_id INTEGER NOT NULL REFERENCES signals(id),
    position_size REAL NOT NULL,
    entry_price REAL NOT NULL,
    exit_price REAL,
    pnl REAL,
    pnl_percent REAL,
    opened_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    closed_at TIMESTAMP,
    close_reason TEXT
);

CREATE TABLE IF NOT EXISTS performance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL UNIQUE,
    total_signals INTEGER DEFAULT 0,
    trades_taken INTEGER DEFAULT 0,
    wins INTEGER DEFAULT 0,
    losses INTEGER DEFAULT 0,
    gross_profit REAL DEFAULT 0.0,
    gross_loss REAL DEFAULT 0.0,
    net_pnl REAL DEFAULT 0.0,
    win_rate REAL DEFAULT 0.0,
    profit_factor REAL DEFAULT 0.0,
    max_drawdown REAL DEFAULT 0.0,
    sharpe_ratio REAL DEFAULT 0.0
);

CREATE TABLE IF NOT EXISTS news (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    headline TEXT NOT NULL,
    url TEXT,
    published_at TIMESTAMP,
    classification TEXT,
    confidence REAL,
    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    content_hash TEXT UNIQUE
);

CREATE TABLE IF NOT EXISTS account_state (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    capital REAL NOT NULL,
    open_positions INTEGER DEFAULT 0,
    daily_pnl REAL DEFAULT 0.0,
    kill_switch_active INTEGER DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    blackout_until TIMESTAMP
);
"""

_MIGRATION_SQL = [
    "ALTER TABLE news ADD COLUMN content_hash TEXT",
    "ALTER TABLE account_state ADD COLUMN blackout_until TIMESTAMP",
]


class Database:
    def __init__(self, config: AppConfig):
        self._db_path = config.db_path
        if self._db_path != ":memory:":
            Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self._db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(_SCHEMA_SQL)
        self._run_migrations()
        self._init_account_state(config.initial_capital)
        logger.info("Database initialized at %s", self._db_path)

    def _run_migrations(self) -> None:
        for sql in _MIGRATION_SQL:
            try:
                self._conn.execute(sql)
                self._conn.commit()
            except sqlite3.OperationalError:
                pass

    def _init_account_state(self, initial_capital: float) -> None:
        row = self._conn.execute("SELECT COUNT(*) FROM account_state").fetchone()
        if row[0] == 0:
            self._conn.execute(
                "INSERT INTO account_state (capital, open_positions, daily_pnl, kill_switch_active) VALUES (?, 0, 0.0, 0)",
                (initial_capital,),
            )
            self._conn.commit()

    def save_signal(self, signal: TradeSignal, status: str) -> int:
        cursor = self._conn.execute(
            """INSERT INTO signals (asset, direction, entry_price, stop_loss, take_profit,
               probability, timeframe, reasoning, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                signal.asset,
                signal.direction,
                signal.entry_price,
                signal.stop_loss,
                signal.take_profit,
                signal.probability,
                signal.timeframe,
                signal.reasoning,
                status,
            ),
        )
        self._conn.commit()
        return cursor.lastrowid

    def update_signal_status(self, signal_id: int, status: str) -> None:
        self._conn.execute(
            "UPDATE signals SET status = ? WHERE id = ?", (status, signal_id)
        )
        self._conn.commit()

    def get_last_signal(self, asset: str) -> dict | None:
        row = self._conn.execute(
            "SELECT * FROM signals WHERE asset = ? ORDER BY id DESC LIMIT 1",
            (asset,),
        ).fetchone()
        return dict(row) if row else None

    def open_trade(
        self, signal_id: int, position_size: float, entry_price: float
    ) -> int:
        cursor = self._conn.execute(
            "INSERT INTO trades (signal_id, position_size, entry_price) VALUES (?, ?, ?)",
            (signal_id, position_size, entry_price),
        )
        self._conn.commit()
        return cursor.lastrowid

    def close_trade(self, trade_id: int, exit_price: float, reason: str) -> None:
        trade = self._conn.execute(
            """SELECT t.entry_price, t.position_size, s.direction
               FROM trades t JOIN signals s ON t.signal_id = s.id
               WHERE t.id = ?""",
            (trade_id,),
        ).fetchone()
        if trade is None:
            logger.warning("Trade %d not found for closing", trade_id)
            return
        entry = trade["entry_price"]
        size = trade["position_size"]
        direction = trade["direction"]
        sign = 1 if direction == "BUY" else -1
        pnl = (exit_price - entry) * size * sign
        pnl_pct = ((exit_price - entry) / entry) * 100 * sign
        self._conn.execute(
            "UPDATE trades SET exit_price = ?, pnl = ?, pnl_percent = ?, closed_at = ?, close_reason = ? WHERE id = ?",
            (
                exit_price,
                pnl,
                pnl_pct,
                datetime.now(timezone.utc).isoformat(),
                reason,
                trade_id,
            ),
        )
        self._conn.commit()

    def get_open_positions_count(self) -> int:
        row = self._conn.execute(
            "SELECT COUNT(*) FROM trades WHERE closed_at IS NULL"
        ).fetchone()
        return row[0]

    def get_daily_pnl(self) -> float:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        row = self._conn.execute(
            "SELECT COALESCE(SUM(pnl), 0.0) FROM trades WHERE pnl IS NOT NULL AND DATE(closed_at) = ?",
            (today,),
        ).fetchone()
        return row[0]

    def get_account_state(self) -> AccountState:
        row = self._conn.execute(
            "SELECT * FROM account_state ORDER BY id LIMIT 1"
        ).fetchone()
        return AccountState(
            capital=row["capital"],
            open_positions=row["open_positions"],
            daily_pnl=row["daily_pnl"],
            kill_switch_active=bool(row["kill_switch_active"]),
            updated_at=datetime.fromisoformat(row["updated_at"])
            if row["updated_at"]
            else datetime.now(timezone.utc),
        )

    def update_account_state(self, **kwargs) -> None:
        if not kwargs:
            return
        has_updated_at = "updated_at" in kwargs
        sets = []
        vals = []
        for key, val in kwargs.items():
            if key == "kill_switch_active":
                sets.append(f"{key} = ?")
                vals.append(1 if val else 0)
            elif key == "updated_at":
                sets.append("updated_at = ?")
                vals.append(val if isinstance(val, str) else val.isoformat())
            else:
                sets.append(f"{key} = ?")
                vals.append(val)
        if not has_updated_at:
            sets.append("updated_at = ?")
            vals.append(datetime.now(timezone.utc).isoformat())
        self._conn.execute(f"UPDATE account_state SET {', '.join(sets)}", vals)
        self._conn.commit()

    def reset_daily_if_needed(self) -> None:
        state = self._conn.execute(
            "SELECT updated_at FROM account_state ORDER BY id LIMIT 1"
        ).fetchone()
        if state is None:
            return
        updated_str = state["updated_at"]
        if not updated_str:
            return
        updated_at = datetime.fromisoformat(updated_str)
        if isinstance(updated_at.tzinfo, type(None)):
            updated_at = updated_at.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        if updated_at.date() < now.date():
            self._conn.execute(
                "UPDATE account_state SET daily_pnl = 0.0, kill_switch_active = 0, updated_at = ?",
                (now.isoformat(),),
            )
            self._conn.commit()
            logger.info("Daily reset performed at UTC midnight")

    def get_daily_performance(self, date: str) -> dict:
        row = self._conn.execute(
            "SELECT * FROM performance WHERE date = ?", (date,)
        ).fetchone()
        if row:
            return dict(row)
        return {
            "date": date,
            "total_signals": 0,
            "trades_taken": 0,
            "wins": 0,
            "losses": 0,
            "gross_profit": 0.0,
            "gross_loss": 0.0,
            "net_pnl": 0.0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "max_drawdown": 0.0,
            "sharpe_ratio": 0.0,
        }

    def update_daily_performance(self, date: str, **kwargs) -> None:
        existing = self._conn.execute(
            "SELECT id FROM performance WHERE date = ?", (date,)
        ).fetchone()
        if existing:
            sets = []
            vals = []
            for key, val in kwargs.items():
                sets.append(f"{key} = ?")
                vals.append(val)
            vals.append(date)
            self._conn.execute(
                f"UPDATE performance SET {', '.join(sets)} WHERE date = ?", vals
            )
        else:
            cols = ["date"] + list(kwargs.keys())
            placeholders = ", ".join(["?"] * len(cols))
            vals = [date] + list(kwargs.values())
            self._conn.execute(
                f"INSERT INTO performance ({', '.join(cols)}) VALUES ({placeholders})",
                vals,
            )
        self._conn.commit()

    def save_news(
        self,
        item: NewsItem,
        classification: str,
        confidence: float,
        content_hash: str,
    ) -> None:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        self._conn.execute(
            """INSERT OR IGNORE INTO news
               (source, headline, url, published_at, classification, confidence, content_hash, collected_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                item.source,
                item.headline,
                item.url,
                item.published_at.isoformat(),
                classification,
                confidence,
                content_hash,
                now,
            ),
        )
        self._conn.commit()

    def get_recent_news(self, hours: float) -> list[dict]:
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        rows = self._conn.execute(
            """SELECT * FROM news
               WHERE collected_at >= ?
               ORDER BY collected_at DESC""",
            (cutoff,),
        ).fetchall()
        return [dict(r) for r in rows]

    def check_hash_exists(self, content_hash: str) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM news WHERE content_hash = ?", (content_hash,)
        ).fetchone()
        return row is not None

    def set_blackout_until(self, timestamp: datetime) -> None:
        self._conn.execute(
            "UPDATE account_state SET blackout_until = ?", (timestamp.isoformat(),)
        )
        self._conn.commit()

    def is_blackout_active(self) -> bool:
        row = self._conn.execute(
            "SELECT blackout_until FROM account_state ORDER BY id LIMIT 1"
        ).fetchone()
        if row is None or row["blackout_until"] is None:
            return False
        blackout_ts = datetime.fromisoformat(row["blackout_until"])
        if isinstance(blackout_ts.tzinfo, type(None)):
            blackout_ts = blackout_ts.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) < blackout_ts

    def clear_expired_blackout(self) -> None:
        row = self._conn.execute(
            "SELECT blackout_until FROM account_state ORDER BY id LIMIT 1"
        ).fetchone()
        if row is None or row["blackout_until"] is None:
            return
        blackout_ts = datetime.fromisoformat(row["blackout_until"])
        if isinstance(blackout_ts.tzinfo, type(None)):
            blackout_ts = blackout_ts.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) >= blackout_ts:
            self._conn.execute("UPDATE account_state SET blackout_until = NULL")
            self._conn.commit()

    def close(self) -> None:
        self._conn.close()

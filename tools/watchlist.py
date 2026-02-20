from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class WatchlistItem(BaseModel):
    id: Optional[int] = None
    ticker: str
    exchange: str
    alert_rules: Dict[str, Any] = Field(default_factory=dict)


class WatchlistManager:
    def __init__(self, db_path: str = "watchlist.db"):
        self.db_path = str(Path(db_path))
        self._lock = Lock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=5, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    @staticmethod
    def _normalize_symbol(value: str) -> str:
        cleaned = value.strip().upper()
        if not cleaned:
            raise ValueError("ticker/exchange cannot be empty")
        return cleaned

    def _init_db(self) -> None:
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS watchlist (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        ticker TEXT NOT NULL,
                        exchange TEXT NOT NULL,
                        alert_rules TEXT,
                        UNIQUE(ticker, exchange)
                    )
                    """
                )

    def add(self, ticker: str, exchange: str, rules: Optional[Dict[str, Any]] = None) -> int:
        ticker_symbol = self._normalize_symbol(ticker)
        exchange_symbol = self._normalize_symbol(exchange)
        rules_json = json.dumps(rules or {}, separators=(",", ":"))
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO watchlist (ticker, exchange, alert_rules)
                    VALUES (?, ?, ?)
                    ON CONFLICT(ticker, exchange) DO UPDATE SET
                        alert_rules = excluded.alert_rules
                    """,
                    (ticker_symbol, exchange_symbol, rules_json),
                )
                row = conn.execute(
                    "SELECT id FROM watchlist WHERE ticker = ? AND exchange = ?",
                    (ticker_symbol, exchange_symbol),
                ).fetchone()
                if row is None:
                    raise RuntimeError("Failed to persist watchlist item")
                return int(row["id"])

    def remove(self, ticker: str, exchange: str) -> bool:
        ticker_symbol = self._normalize_symbol(ticker)
        exchange_symbol = self._normalize_symbol(exchange)
        with self._lock:
            with self._connect() as conn:
                cursor = conn.execute(
                    "DELETE FROM watchlist WHERE ticker = ? AND exchange = ?",
                    (ticker_symbol, exchange_symbol),
                )
                return cursor.rowcount > 0

    def get_all(self) -> List[WatchlistItem]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, ticker, exchange, alert_rules FROM watchlist ORDER BY ticker ASC"
            ).fetchall()
            items: List[WatchlistItem] = []
            for row in rows:
                raw_rules = row["alert_rules"] or "{}"
                try:
                    alert_rules = json.loads(raw_rules)
                except json.JSONDecodeError:
                    alert_rules = {}
                items.append(
                    WatchlistItem(
                        id=row["id"],
                        ticker=row["ticker"],
                        exchange=row["exchange"],
                        alert_rules=alert_rules,
                    )
                )
            return items


watchlist_manager = WatchlistManager()

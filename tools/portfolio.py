from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import List, Optional

from pydantic import BaseModel, Field


class PortfolioItem(BaseModel):
    id: Optional[int] = None
    ticker: str
    exchange: str
    quantity: float
    avg_price: float
    added_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class PortfolioManager:
    def __init__(self, db_path: str = "portfolio.db"):
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
                    CREATE TABLE IF NOT EXISTS portfolio (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        ticker TEXT NOT NULL,
                        exchange TEXT NOT NULL,
                        quantity REAL NOT NULL,
                        avg_price REAL NOT NULL,
                        added_at TEXT,
                        UNIQUE(ticker, exchange)
                    )
                    """
                )

    def add_position(self, ticker: str, exchange: str, quantity: float, avg_price: float) -> int:
        if quantity <= 0:
            raise ValueError("quantity must be > 0")
        if avg_price <= 0:
            raise ValueError("avg_price must be > 0")

        ticker_symbol = self._normalize_symbol(ticker)
        exchange_symbol = self._normalize_symbol(exchange)
        timestamp = datetime.now(timezone.utc).isoformat()
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO portfolio (ticker, exchange, quantity, avg_price, added_at)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(ticker, exchange) DO UPDATE SET
                        quantity = excluded.quantity,
                        avg_price = excluded.avg_price,
                        added_at = excluded.added_at
                    """,
                    (ticker_symbol, exchange_symbol, float(quantity), float(avg_price), timestamp),
                )
                row = conn.execute(
                    "SELECT id FROM portfolio WHERE ticker = ? AND exchange = ?",
                    (ticker_symbol, exchange_symbol),
                ).fetchone()
                if row is None:
                    raise RuntimeError("Failed to persist portfolio position")
                return int(row["id"])

    def remove_position(self, ticker: str, exchange: str) -> bool:
        ticker_symbol = self._normalize_symbol(ticker)
        exchange_symbol = self._normalize_symbol(exchange)
        with self._lock:
            with self._connect() as conn:
                cursor = conn.execute(
                    "DELETE FROM portfolio WHERE ticker = ? AND exchange = ?",
                    (ticker_symbol, exchange_symbol),
                )
                return cursor.rowcount > 0

    def get_all(self) -> List[PortfolioItem]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, ticker, exchange, quantity, avg_price, added_at FROM portfolio ORDER BY ticker ASC"
            ).fetchall()
            return [PortfolioItem(**dict(row)) for row in rows]


portfolio_manager = PortfolioManager()

import sqlite3
import json
from typing import List, Optional
from pydantic import BaseModel

class WatchlistItem(BaseModel):
    id: Optional[int] = None
    ticker: str
    exchange: str
    alert_rules: Optional[str] = "{}" # JSON string of rules

class WatchlistManager:
    def __init__(self, db_path: str = "watchlist.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS watchlist (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticker TEXT NOT NULL,
                    exchange TEXT NOT NULL,
                    alert_rules TEXT,
                    UNIQUE(ticker, exchange)
                )
            """)

    def add(self, ticker: str, exchange: str, rules: dict = None) -> int:
        rules_json = json.dumps(rules or {})
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "INSERT OR REPLACE INTO watchlist (ticker, exchange, alert_rules) VALUES (?, ?, ?)",
                (ticker.upper(), exchange.upper(), rules_json)
            )
            return cursor.lastrowid

    def remove(self, ticker: str, exchange: str):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "DELETE FROM watchlist WHERE ticker = ? AND exchange = ?",
                (ticker.upper(), exchange.upper())
            )

    def get_all(self) -> List[WatchlistItem]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM watchlist")
            return [
                WatchlistItem(
                    id=row["id"],
                    ticker=row["ticker"],
                    exchange=row["exchange"],
                    alert_rules=row["alert_rules"]
                ) for row in cursor.fetchall()
            ]

watchlist_manager = WatchlistManager()

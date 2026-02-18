import sqlite3
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

class PortfolioItem(BaseModel):
    id: Optional[int] = None
    ticker: str
    exchange: str
    quantity: float
    avg_price: float
    added_at: str = datetime.now().isoformat()

class PortfolioManager:
    def __init__(self, db_path: str = "portfolio.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS portfolio (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticker TEXT NOT NULL,
                    exchange TEXT NOT NULL,
                    quantity REAL NOT NULL,
                    avg_price REAL NOT NULL,
                    added_at TEXT,
                    UNIQUE(ticker, exchange)
                )
            """)

    def add_position(self, ticker: str, exchange: str, quantity: float, avg_price: float):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO portfolio (ticker, exchange, quantity, avg_price, added_at) VALUES (?, ?, ?, ?, ?)",
                (ticker.upper(), exchange.upper(), quantity, avg_price, datetime.now().isoformat())
            )

    def remove_position(self, ticker: str, exchange: str):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "DELETE FROM portfolio WHERE ticker = ? AND exchange = ?",
                (ticker.upper(), exchange.upper())
            )

    def get_all(self) -> List[PortfolioItem]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM portfolio")
            return [PortfolioItem(**dict(row)) for row in cursor.fetchall()]

portfolio_manager = PortfolioManager()

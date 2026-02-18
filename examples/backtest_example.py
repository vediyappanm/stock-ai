"""Minimal backtest API example."""

from __future__ import annotations

import httpx


def main() -> None:
    payload = {"ticker": "AAPL", "exchange": "NASDAQ", "days": 30}
    response = httpx.post("http://127.0.0.1:8000/api/backtest", json=payload, timeout=30)
    response.raise_for_status()
    print(response.json())


if __name__ == "__main__":
    main()


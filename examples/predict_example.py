"""Minimal prediction API example."""

from __future__ import annotations

import httpx


def main() -> None:
    payload = {
        "query": "Predict AAPL tomorrow",
        "include_backtest": True,
        "include_sentiment": False,
    }
    response = httpx.post("http://127.0.0.1:8000/api/predict", json=payload, timeout=30)
    response.raise_for_status()
    print(response.json())


if __name__ == "__main__":
    main()


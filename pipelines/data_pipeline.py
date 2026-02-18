"""Data pipeline compatibility helpers."""

from __future__ import annotations

from tools.fetch_data import fetch_ohlcv_data
from tools.indicators import compute_indicators
from tools.ticker_resolver import resolve_ticker


def run_data_pipeline(stock: str, exchange: str | None = None):
    resolved = resolve_ticker(stock=stock, exchange=exchange)
    ohlcv = fetch_ohlcv_data(ticker_symbol=resolved.full_symbol, exchange=resolved.exchange)
    indicators = compute_indicators(ohlcv)
    return {"resolved": resolved, "ohlcv": ohlcv, "indicators": indicators}


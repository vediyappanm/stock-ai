"""Data pipeline compatibility helpers."""

from __future__ import annotations

from tools.fetch_data import fetch_ohlcv_data
from tools.indicators import compute_indicators
from tools.ticker_resolver import resolve_ticker
from tools.macro_features import fetch_macro_features


def run_data_pipeline(stock: str, exchange: str | None = None, include_macro: bool = True):
    resolved = resolve_ticker(stock=stock, exchange=exchange)
    ohlcv = fetch_ohlcv_data(ticker_symbol=resolved.full_symbol, exchange=resolved.exchange)

    macro_data = None
    if include_macro:
        macro_data = fetch_macro_features()

    indicators = compute_indicators(ohlcv, macro_data=macro_data)
    return {"resolved": resolved, "ohlcv": ohlcv, "indicators": indicators, "macro_data": macro_data}


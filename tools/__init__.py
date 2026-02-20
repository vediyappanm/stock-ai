"""Lazy exports for tools package to avoid import-time dependency cycles."""

from __future__ import annotations

from importlib import import_module
from typing import Dict, Tuple

_EXPORTS: Dict[str, Tuple[str, str]] = {
    "analyze_sentiment": ("tools.sentiment", "analyze_sentiment"),
    "compute_indicators": ("tools.indicators", "compute_indicators"),
    "fetch_ohlcv_data": ("tools.fetch_data", "fetch_ohlcv_data"),
    "generate_explanation": ("tools.explainer", "generate_explanation"),
    "get_health_status": ("tools.health_checker", "get_health_status"),
    "parse_query": ("tools.query_parser", "parse_query"),
    "predict_price": ("tools.predictor", "predict_price"),
    "resolve_ticker": ("tools.ticker_resolver", "resolve_ticker"),
    "run_backtest": ("tools.backtester", "run_backtest"),
}

__all__ = sorted(_EXPORTS.keys())


def __getattr__(name: str):
    if name not in _EXPORTS:
        raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
    module_name, attr_name = _EXPORTS[name]
    module = import_module(module_name)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value

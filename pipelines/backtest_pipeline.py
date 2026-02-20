"""Backtest-only pipeline."""

from __future__ import annotations

from schemas.request_schemas import BacktestRequest
from schemas.response_schemas import BacktestResult
from tools.backtester import run_backtest
from tools.fetch_data import fetch_ohlcv_data
from tools.indicators import compute_indicators
from tools.macro_features import fetch_macro_features
from tools.ticker_resolver import resolve_ticker


def execute_backtest_pipeline(request: BacktestRequest) -> BacktestResult:
    resolved = resolve_ticker(stock=request.ticker, exchange=request.exchange)
    ohlcv = fetch_ohlcv_data(ticker_symbol=resolved.full_symbol, exchange=resolved.exchange)
    macro_data = fetch_macro_features()
    indicators = compute_indicators(ohlcv, macro_data=macro_data)
    return run_backtest(indicators_df=indicators, days=request.days)


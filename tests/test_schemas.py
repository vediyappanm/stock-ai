"""Schema validation tests."""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from pydantic import ValidationError as PydanticValidationError

from schemas.request_schemas import (
    AnalyzeRequest,
    BacktestRequest,
    PortfolioRequest,
    PredictRequest,
    ScanRequest,
    WatchlistRequest,
)


def test_predict_request_accepts_query() -> None:
    req = PredictRequest(query="Predict AAPL tomorrow")
    assert req.query is not None


def test_predict_request_requires_input_source() -> None:
    with pytest.raises(PydanticValidationError):
        PredictRequest()


def test_predict_request_rejects_past_date() -> None:
    with pytest.raises(PydanticValidationError):
        PredictRequest(ticker="AAPL", target_date=date.today() - timedelta(days=1))


def test_backtest_request_limits_days() -> None:
    with pytest.raises(PydanticValidationError):
        BacktestRequest(ticker="AAPL", days=0)


def test_analyze_request_requires_ticker() -> None:
    with pytest.raises(PydanticValidationError):
        AnalyzeRequest(ticker="   ")


def test_scan_request_requires_source() -> None:
    with pytest.raises(PydanticValidationError):
        ScanRequest(preset=None, tickers=None)


def test_watchlist_action_must_be_valid() -> None:
    with pytest.raises(PydanticValidationError):
        WatchlistRequest(ticker="AAPL", exchange="NASDAQ", action="update")


def test_portfolio_add_requires_positive_quantity_and_price() -> None:
    with pytest.raises(PydanticValidationError):
        PortfolioRequest(ticker="AAPL", exchange="NASDAQ", action="add", quantity=0, avg_price=10)


def test_portfolio_remove_allows_default_quantity() -> None:
    req = PortfolioRequest(ticker="AAPL", exchange="NASDAQ", action="remove")
    assert req.action == "remove"

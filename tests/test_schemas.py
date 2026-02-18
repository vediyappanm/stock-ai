"""Schema validation tests."""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from pydantic import ValidationError as PydanticValidationError

from schemas.request_schemas import AnalyzeRequest, BacktestRequest, PredictRequest


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


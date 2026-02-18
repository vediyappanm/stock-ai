"""Integration-style endpoint tests with mocked dependencies."""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
from fastapi.testclient import TestClient

import api_server
from schemas.response_schemas import BacktestResult, PredictResponse, ResolvedTicker


client = TestClient(api_server.app)


def test_health_endpoint() -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    payload = response.json()
    assert "status" in payload
    assert "dependencies" in payload


def test_workflow_not_found() -> None:
    response = client.get("/api/workflow/missing-workflow-id")
    assert response.status_code == 404


def test_predict_endpoint(monkeypatch) -> None:
    target = date.today() + timedelta(days=2)
    mocked = PredictResponse(
        ticker="AAPL",
        exchange="NASDAQ",
        resolved_exchange="NASDAQ",
        target_date=target,
        prediction=200.0,
        lower_bound=190.0,
        upper_bound=210.0,
        confidence_level=0.80,
        explanation="Educational output only. Educational and research use only. Not financial advice.",
        workflow_id="wf-1",
    )
    monkeypatch.setattr(api_server, "execute_prediction_pipeline", lambda req: mocked)

    response = client.post("/api/predict", json={"ticker": "AAPL", "exchange": "NASDAQ"})
    assert response.status_code == 200
    data = response.json()
    assert data["ticker"] == "AAPL"
    assert data["workflow_id"] == "wf-1"


def test_predict_quick_endpoint(monkeypatch) -> None:
    target = date.today() + timedelta(days=2)
    mocked = PredictResponse(
        ticker="AAPL",
        exchange="NASDAQ",
        resolved_exchange="NASDAQ",
        target_date=target,
        prediction=200.0,
        lower_bound=190.0,
        upper_bound=210.0,
        confidence_level=0.80,
        explanation="Educational output only. Educational and research use only. Not financial advice.",
        workflow_id="wf-quick",
    )
    monkeypatch.setattr(api_server, "execute_prediction_pipeline", lambda req: mocked)

    response = client.post("/api/predict/quick", json={"ticker": "AAPL", "exchange": "NASDAQ"})
    assert response.status_code == 200
    data = response.json()
    assert data["workflow_id"] == "wf-quick"


def test_backtest_endpoint(monkeypatch) -> None:
    mocked = BacktestResult(
        mae=1.0,
        rmse=1.2,
        mape=0.8,
        directional_accuracy=60.0,
        actual_prices=[100.0, 101.0],
        predicted_prices=[99.5, 102.0],
        periods=2,
    )
    monkeypatch.setattr(api_server, "execute_backtest_pipeline", lambda req: mocked)

    response = client.post("/api/backtest", json={"ticker": "AAPL", "exchange": "NASDAQ", "days": 10})
    assert response.status_code == 200
    data = response.json()
    assert data["result"]["periods"] == 2


def test_analyze_endpoint(monkeypatch) -> None:
    monkeypatch.setattr(
        api_server,
        "resolve_ticker",
        lambda stock, exchange=None: ResolvedTicker(ticker="AAPL", exchange="NASDAQ", full_symbol="AAPL"),
    )
    monkeypatch.setattr(
        api_server,
        "fetch_ohlcv_data",
        lambda ticker_symbol, exchange: pd.DataFrame(
            {
                "Date": pd.date_range("2025-01-01", periods=210),
                "Open": [100.0] * 210,
                "High": [101.0] * 210,
                "Low": [99.0] * 210,
                "Close": [100.0 + i * 0.1 for i in range(210)],
                "Volume": [1000000] * 210,
            }
        ),
    )
    monkeypatch.setattr(api_server, "compute_indicators", lambda df: df.assign(SMA_20=100.0))

    response = client.post("/api/analyze", json={"ticker": "AAPL", "exchange": "NASDAQ"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["ticker"] == "AAPL"
    assert "indicators" in payload


def test_predict_validation_error() -> None:
    response = client.post("/api/predict", json={})
    assert response.status_code == 422
    assert response.json()["error_category"] == "VALIDATION_ERROR"

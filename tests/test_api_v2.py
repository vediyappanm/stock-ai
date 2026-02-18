"""Tests for api.py compatibility endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient

import api


client = TestClient(api.app)


def test_v2_predict(monkeypatch) -> None:
    monkeypatch.setattr(
        api.pipeline,
        "run_complete_prediction_orchestrated",
        lambda **kwargs: {"success": True, "ticker": "ABB.NS"},
    )
    response = client.post("/api/predict", json={"ticker": "ABB", "exchange": "NSE"})
    assert response.status_code == 200
    assert response.json()["success"] is True


def test_v2_predict_quick(monkeypatch) -> None:
    monkeypatch.setattr(
        api.pipeline,
        "run_quick_prediction",
        lambda **kwargs: {"success": True, "ticker": "ABB.NS"},
    )
    response = client.post("/api/predict/quick", json={"ticker": "ABB", "exchange": "NSE"})
    assert response.status_code == 200
    assert response.json()["success"] is True


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
    captured = {}

    def _mock_quick(**kwargs):
        captured.update(kwargs)
        return {"success": True, "ticker": "ABB.NS"}

    monkeypatch.setattr(
        api.pipeline,
        "run_quick_prediction",
        _mock_quick,
    )
    response = client.post("/api/predict/quick", json={"ticker": "ABB", "exchange": "NSE"})
    assert response.status_code == 200
    assert response.json()["success"] is True
    assert captured["stock_name"] == "ABB"
    assert captured["model_type"] == "random_forest"


def test_v2_predict_validation_error() -> None:
    response = client.post("/api/predict", json={})
    assert response.status_code == 422
    payload = response.json()
    assert payload["error_category"] == "validation_error"

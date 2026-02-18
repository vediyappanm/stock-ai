"""Additional unit coverage for core modules."""

from __future__ import annotations

from datetime import date, timedelta

from models.ensemble import combine_predictions, compute_prediction_interval
from schemas.response_schemas import Prediction
from tests.fixtures import create_synthetic_ohlcv
from tools.explainer import generate_explanation
from tools.indicators import INDICATOR_COLUMNS, compute_indicators


def test_indicator_set_complete() -> None:
    df = create_synthetic_ohlcv(rows=260, seed=1)
    out = compute_indicators(df)
    for column in INDICATOR_COLUMNS:
        assert column in out.columns


def test_ensemble_weighting_formula() -> None:
    value = combine_predictions(rf_prediction=100.0, lstm_prediction=200.0)
    assert value == 140.0


def test_prediction_interval_shape() -> None:
    low, high = compute_prediction_interval(point_estimate=100.0, residual_stds=[2.0, 3.0])
    assert low < 100.0 < high


def test_explanation_contains_disclaimer_and_interval() -> None:
    pred = Prediction(
        point_estimate=123.4,
        lower_bound=120.0,
        upper_bound=126.0,
        confidence_level=0.8,
        rf_prediction=124.0,
        lstm_prediction=122.0,
        feature_importance={"RSI_14": 0.4, "MACD": 0.3, "SMA_20": 0.2},
    )
    msg = generate_explanation(
        ticker="AAPL",
        exchange="NASDAQ",
        target_date=date.today() + timedelta(days=1),
        prediction=pred,
    )
    assert "Not financial advice" in msg
    assert "80% interval" in msg


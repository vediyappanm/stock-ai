"""Prediction combination and interval computation."""

from __future__ import annotations

import math

from typing import Iterable, Tuple

import numpy as np

from config.settings import settings


def combine_predictions(
    xgb_prediction: float | None = None,
    rf_prediction: float | None = None,
    lstm_prediction: float | None = None,
    volatility: float | None = None,
) -> float:
    """Weighted ensemble with dynamic volatility-based weighting.

    High volatility → favor LSTM (better at trends), Low volatility → favor XGB (stable model).
    Volatility parameter (e.g., 20-day rolling std) adjusts weights dynamically.
    """
    import math

    if rf_prediction is None or lstm_prediction is None:
        raise ValueError("rf_prediction and lstm_prediction are required")

    rf_value = float(rf_prediction)
    lstm_value = float(lstm_prediction)
    lstm_ok = (
        lstm_prediction is not None
        and math.isfinite(lstm_value)
        and lstm_value != 0.0
    )

    # Backward compatibility for older callers/tests that only provide RF+LSTM.
    if xgb_prediction is None:
        return float(0.6 * rf_value + 0.4 * lstm_value)

    xgb_value = float(xgb_prediction)

    # Dynamic weighting based on volatility
    if volatility is not None and volatility > 0:
        # Normalize volatility to [0, 1] range (assuming typical vol is 1-3%)
        vol_factor = min(volatility / 0.03, 1.0)  # Cap at 1.0
        # High vol → LSTM weight increases, XGB decreases
        xgb_w = settings.xgb_weight * (1 - 0.3 * vol_factor)
        lstm_w = settings.lstm_weight * (1 + 0.3 * vol_factor)
        rf_w = settings.rf_weight
        total = xgb_w + rf_w + lstm_w
        xgb_w, lstm_w, rf_w = xgb_w / total, lstm_w / total, rf_w / total
    else:
        # Use static weights
        xgb_w = settings.xgb_weight
        rf_w = settings.rf_weight
        lstm_w = settings.lstm_weight

    if lstm_ok:
        return float(xgb_w * xgb_value + rf_w * rf_value + lstm_w * lstm_value)
    else:
        # Redistribute LSTM weight equally between XGBoost and RF
        total_weight = xgb_w + rf_w
        adj_xgb = xgb_w / total_weight if total_weight > 0 else 0.5
        adj_rf = rf_w / total_weight if total_weight > 0 else 0.5
        return float(adj_xgb * xgb_value + adj_rf * rf_value)


def compute_prediction_interval(
    point_estimate: float,
    residual_stds: Iterable[float],
) -> Tuple[float, float]:
    """
    Compute 80% prediction interval using residual-based uncertainty.
    """
    std_values = [float(abs(v)) for v in residual_stds if v is not None]
    sigma = float(np.mean(std_values)) if std_values else 0.0
    margin = settings.z_score_80 * sigma
    return float(point_estimate - margin), float(point_estimate + margin)


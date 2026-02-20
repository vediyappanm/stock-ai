"""Metrics validation: measure improvement from upgrades (FinBERT, dynamic weights, etc)."""

from __future__ import annotations

import pandas as pd
import numpy as np
from typing import Dict, Tuple
import logging

logger = logging.getLogger(__name__)


def correlation_sentiment_returns(
    indicators_df: pd.DataFrame,
    sentiment_scores: list[float],
) -> float:
    """Measure correlation between sentiment and next-day returns."""
    if len(indicators_df) != len(sentiment_scores):
        return 0.0

    returns = indicators_df["Return_1d"].shift(-1).dropna()
    sentiment_arr = np.array(sentiment_scores[:-1])

    if len(returns) == 0 or len(sentiment_arr) == 0:
        return 0.0

    try:
        corr = np.corrcoef(sentiment_arr, returns)[0, 1]
        return float(corr) if np.isfinite(corr) else 0.0
    except Exception:
        return 0.0


def directional_accuracy(actual: list[float], predicted: list[float]) -> float:
    """Percentage of correct directional predictions."""
    if not actual or not predicted or len(actual) != len(predicted):
        return 0.0

    actual_arr = np.array(actual)
    pred_arr = np.array(predicted)

    actual_dir = np.sign(actual_arr[1:] - actual_arr[:-1])
    pred_dir = np.sign(pred_arr[1:] - pred_arr[:-1])

    accuracy = np.mean((actual_dir == pred_dir).astype(float)) * 100
    return float(accuracy)


def mae_mape(actual: list[float], predicted: list[float]) -> Tuple[float, float]:
    """Mean Absolute Error and Mean Absolute Percentage Error."""
    if not actual or not predicted or len(actual) != len(predicted):
        return 0.0, 0.0

    actual_arr = np.array(actual, dtype=float)
    pred_arr = np.array(predicted, dtype=float)

    mae = float(np.mean(np.abs(actual_arr - pred_arr)))
    mape = float(np.mean(np.abs((actual_arr - pred_arr) / np.clip(actual_arr, 1e-9, None))) * 100)

    return mae, mape


def volatility_adaptive_score(
    directional_acc: float,
    volatility_mean: float,
    target_vol: float = 0.02,
) -> float:
    """
    Score that adjusts for volatility regime.
    High vol environments are harder to predict -> lower target accuracy.
    """
    vol_factor = min(volatility_mean / target_vol, 2.0)
    adjusted_target = 55 / vol_factor  # Baseline 55% adjusted down for high vol
    spread = max(directional_acc - adjusted_target, 0)
    return min(100, 50 + spread)  # Score 0-100


def print_validation_report(
    model_name: str,
    actual_prices: list[float],
    predicted_prices: list[float],
    indicators_df: pd.DataFrame,
) -> Dict[str, float]:
    """Print and return validation metrics."""
    dir_acc = directional_accuracy(actual_prices, predicted_prices)
    mae, mape = mae_mape(actual_prices, predicted_prices)

    vol_20d = indicators_df["Vol_20d"].mean() if "Vol_20d" in indicators_df.columns else 0.0
    adaptive_score = volatility_adaptive_score(dir_acc, vol_20d)

    print(f"\n=== {model_name} Validation Metrics ===")
    print(f"Directional Accuracy: {dir_acc:.2f}%")
    print(f"MAE (Price Error): ${mae:.4f}")
    print(f"MAPE: {mape:.2f}%")
    print(f"Volatility (20d): {vol_20d:.4f}")
    print(f"Adaptive Score: {adaptive_score:.1f}/100")

    return {
        "directional_accuracy": dir_acc,
        "mae": mae,
        "mape": mape,
        "volatility": vol_20d,
        "adaptive_score": adaptive_score,
    }


def compare_sentiment_methods(
    headlines: list[str],
    vader_scores: list[float],
    finbert_scores: list[float],
) -> Dict[str, float]:
    """Compare sentiment methods on agreement and variance."""
    if not headlines or len(vader_scores) != len(finbert_scores):
        return {}

    vader_arr = np.array(vader_scores)
    finbert_arr = np.array(finbert_scores)

    agreement = float(np.mean((np.sign(vader_arr) == np.sign(finbert_arr)).astype(float)) * 100)
    rmse = float(np.sqrt(np.mean((vader_arr - finbert_arr) ** 2)))
    corr = float(np.corrcoef(vader_arr, finbert_arr)[0, 1]) if len(vader_arr) > 1 else 0.0

    print(f"\n=== Sentiment Method Comparison ===")
    print(f"Agreement (directional): {agreement:.1f}%")
    print(f"RMSE: {rmse:.4f}")
    print(f"Correlation: {corr:.3f}")

    return {"agreement": agreement, "rmse": rmse, "correlation": corr}

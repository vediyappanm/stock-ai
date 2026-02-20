"""Concept drift detection for model monitoring (Phase 4: Risk Management)."""

from __future__ import annotations

import numpy as np
from typing import Tuple
import logging
from scipy import stats

logger = logging.getLogger(__name__)


def kolmogorov_smirnov_test(
    residuals_train: list[float],
    residuals_recent: list[float],
    alpha: float = 0.05,
) -> Tuple[float, float, bool]:
    """
    Kolmogorov-Smirnov test: detect distribution shift in residuals.

    Returns:
    - statistic: KS test statistic (0-1, higher = more drift)
    - p_value: probability null hypothesis is true (p>0.05 = stable)
    - has_drift: True if p < alpha (drift detected)
    """
    if len(residuals_train) < 10 or len(residuals_recent) < 10:
        return 0.0, 1.0, False

    train_arr = np.array(residuals_train, dtype=float)
    recent_arr = np.array(residuals_recent, dtype=float)

    statistic, p_value = stats.ks_2samp(train_arr, recent_arr)

    has_drift = p_value < alpha

    if has_drift:
        logger.warning(f"Concept drift detected: KS stat={statistic:.3f}, p={p_value:.4f}")
    else:
        logger.info(f"Model stable: KS stat={statistic:.3f}, p={p_value:.4f}")

    return float(statistic), float(p_value), bool(has_drift)


def accuracy_decay_detection(
    daily_accuracies: list[float],
    window: int = 5,
    threshold: float = 0.55,
) -> Tuple[float, bool]:
    """
    Detect accuracy decay over rolling window.

    Returns:
    - recent_avg: average accuracy over recent window
    - needs_retraining: True if recent_avg < threshold
    """
    if len(daily_accuracies) < window:
        return 0.0, False

    recent_window = daily_accuracies[-window:]
    recent_avg = float(np.mean(recent_window))

    needs_retraining = recent_avg < threshold

    if needs_retraining:
        logger.warning(f"Accuracy decay: {recent_avg:.1%} < {threshold:.1%}. Retrain required.")
    else:
        logger.info(f"Accuracy stable: {recent_avg:.1%}")

    return recent_avg, needs_retraining


def model_stability_score(
    ks_p_value: float,
    recent_accuracy: float,
    baseline_accuracy: float = 0.58,
) -> float:
    """
    Composite stability score (0-100).
    - 100: Stable, good accuracy
    - 0: Severe drift or poor accuracy
    """
    drift_score = min(ks_p_value * 100, 100)  # Higher p = more stable
    accuracy_ratio = (recent_accuracy / baseline_accuracy) * 100 if baseline_accuracy > 0 else 0
    accuracy_score = min(accuracy_ratio, 100)

    composite = 0.6 * drift_score + 0.4 * accuracy_score

    return float(composite)


def retraining_schedule(
    stability_score: float,
    days_since_retrain: int,
) -> Tuple[str, int]:
    """
    Recommend retraining schedule based on stability.

    Returns:
    - action: "stable" | "monitor" | "retrain"
    - days_until_retrain: suggested days to next retrain
    """
    if stability_score >= 80:
        action = "stable"
        days = 14  # Retrain every 2 weeks if stable
    elif stability_score >= 60:
        action = "monitor"
        days = 7  # Retrain weekly if slightly degraded
    else:
        action = "retrain"
        days = 1  # Retrain daily if unstable

    return action, days


def alert_model_health(
    ks_p_value: float,
    recent_accuracy: float,
    stability_score: float,
) -> str:
    """Generate human-readable health alert."""
    alerts = []

    if ks_p_value < 0.05:
        alerts.append("WARNING: Concept drift detected (KS test p<0.05)")

    if recent_accuracy < 0.55:
        alerts.append(f"WARNING: Accuracy degraded to {recent_accuracy:.1%} (target 58%+)")

    if stability_score < 50:
        alerts.append("CRITICAL: Model stability score <50. Retrain immediately.")

    if not alerts:
        alerts.append(f"OK: Model healthy. Stability={stability_score:.0f}/100")

    return " | ".join(alerts)

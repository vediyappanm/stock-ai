"""Random Forest model wrapper for stock prediction."""

from __future__ import annotations

from dataclasses import dataclass
import logging
import warnings
from typing import Dict

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor

# Suppress sklearn parallel warnings
warnings.filterwarnings('ignore', message='.*sklearn.utils.parallel.*')
warnings.filterwarnings('ignore', category=UserWarning, module='sklearn.utils.parallel')

from config.settings import settings
from tools.error_handler import ModelError
from tools.indicators import INDICATOR_COLUMNS


FEATURE_COLUMNS = INDICATOR_COLUMNS + ["day_of_week", "day_of_month", "month"]
logger = logging.getLogger(__name__)


@dataclass
class RFTrainResult:
    model: RandomForestRegressor
    feature_importance: Dict[str, float]
    residual_std: float


class RandomForestModel:
    """Encapsulates RF train/predict with feature engineering."""

    def __init__(self) -> None:
        preferred_jobs = settings.rf_n_jobs if settings.rf_n_jobs != 0 else 1
        self.model = self._build_model(preferred_jobs)

    @staticmethod
    def _build_model(n_jobs: int) -> RandomForestRegressor:
        return RandomForestRegressor(
            n_estimators=settings.rf_n_estimators,
            max_depth=settings.rf_max_depth,
            random_state=settings.rf_random_state,
            n_jobs=n_jobs,
        )

    @staticmethod
    def _prepare(df: pd.DataFrame) -> pd.DataFrame:
        if len(df) < settings.min_rows_rf:
            raise ModelError(
                f"Insufficient rows for Random Forest: got {len(df)}, need at least {settings.min_rows_rf}.",
                failed_step="PREDICT_PRICE",
            )

        prepared = df.copy()
        prepared["Date"] = pd.to_datetime(prepared["Date"])
        prepared["day_of_week"] = prepared["Date"].dt.dayofweek
        prepared["day_of_month"] = prepared["Date"].dt.day
        prepared["month"] = prepared["Date"].dt.month
        clean = prepared.dropna(subset=FEATURE_COLUMNS + ["Close"]).reset_index(drop=True)
        if len(clean) < settings.min_rows_rf:
            raise ModelError(
                "Insufficient clean rows after feature preparation for Random Forest.",
                failed_step="PREDICT_PRICE",
            )
        return clean

    def train(self, df: pd.DataFrame) -> RFTrainResult:
        prepared = self._prepare(df)
        train_df = prepared.iloc[:-1]
        target = prepared["Close"].shift(-1).iloc[:-1]

        if train_df.empty:
            raise ModelError("Random Forest training set is empty.", failed_step="PREDICT_PRICE")

        x_train = train_df[FEATURE_COLUMNS]
        y_train = target
        try:
            self.model.fit(x_train, y_train)
        except (PermissionError, OSError) as exc:
            # Some Windows environments can block thread-pool primitives used by joblib.
            if self.model.n_jobs == 1:
                raise ModelError(
                    f"Random Forest training failed with single-thread fallback: {exc}",
                    failed_step="PREDICT_PRICE",
                ) from exc

            logger.warning(
                "Random Forest fit failed with n_jobs=%s; retrying with n_jobs=1. Error: %s",
                self.model.n_jobs,
                exc,
            )
            self.model = self._build_model(1)
            self.model.fit(x_train, y_train)

        in_sample = self.model.predict(x_train)
        residuals = y_train.to_numpy() - in_sample
        residual_std = float(np.std(residuals)) if len(residuals) > 1 else 0.0

        importance = {
            name: float(value)
            for name, value in zip(FEATURE_COLUMNS, self.model.feature_importances_)
        }
        return RFTrainResult(model=self.model, feature_importance=importance, residual_std=residual_std)

    def predict_next(self, df: pd.DataFrame) -> float:
        prepared = self._prepare(df)
        latest = prepared.iloc[[-1]][FEATURE_COLUMNS]
        prediction = self.model.predict(latest)[0]
        return float(prediction)

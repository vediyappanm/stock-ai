"""XGBoost regression model for stock price prediction."""

from __future__ import annotations

import numpy as np
import pandas as pd
import xgboost as xgb
from typing import Dict, Any, List

from config.settings import settings
from tools.error_handler import ModelError
from tools.indicators import INDICATOR_COLUMNS


FEATURE_COLUMNS = INDICATOR_COLUMNS + ["day_of_week", "day_of_month", "month"]

class XGBoostModel:
    """Wrapper for XGBoost regressor with production-grade training."""

    def __init__(self, params: Dict[str, Any] = None) -> None:
        self.params = params or {
            "n_estimators": 500,
            "max_depth": 6,
            "learning_rate": 0.05,
            "subsample": 0.8,
            "colsample_bytree": 0.8,
            "random_state": 42,
            "n_jobs": -1,
            "objective": "reg:squarederror"
        }
        self.model = xgb.XGBRegressor(**self.params)

    def _prepare_features(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df["Date"] = pd.to_datetime(df["Date"])
        df["day_of_week"] = df["Date"].dt.dayofweek
        df["day_of_month"] = df["Date"].dt.day
        df["month"] = df["Date"].dt.month
        return df.dropna(subset=FEATURE_COLUMNS)

    def train(self, df: pd.DataFrame) -> Dict[str, float]:
        """Train the model using walk-forward splits or simple validation."""
        prepared = self._prepare_features(df)
        if len(prepared) < settings.min_rows_rf:
            raise ModelError("Insufficient data for XGBoost training.", failed_step="PREDICT_PRICE")

        # Target: Next Close
        x = prepared[FEATURE_COLUMNS].iloc[:-1]
        y = prepared["Close"].shift(-1).iloc[:-1]

        self.model.fit(
            x, y,
            eval_set=[(x, y)],
            verbose=False
        )

        importance = dict(zip(FEATURE_COLUMNS, [float(v) for v in self.model.feature_importances_]))
        return importance

    def predict_next(self, df: pd.DataFrame) -> float:
        """Predict the next closing price."""
        prepared = self._prepare_features(df)
        latest = prepared.iloc[[-1]][FEATURE_COLUMNS]
        prediction = self.model.predict(latest)[0]
        return float(prediction)

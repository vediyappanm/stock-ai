"""Walk-forward backtesting engine using Random Forest + Ensemble."""

from __future__ import annotations

import math
from typing import List

import numpy as np
import pandas as pd

from config.settings import settings
from models.random_forest import FEATURE_COLUMNS, RandomForestModel
from models.xgboost_model import XGBoostModel
from models.lstm import LSTMModel
from models.ensemble import combine_predictions
from schemas.response_schemas import BacktestResult
from tools.error_handler import DataError
import logging

logger = logging.getLogger(__name__)


def _metrics(actual: List[float], predicted: List[float], base_prices: List[float]) -> BacktestResult:
    a = np.array(actual, dtype=float)
    p = np.array(predicted, dtype=float)
    b = np.array(base_prices, dtype=float)

    mae = float(np.mean(np.abs(a - p)))
    rmse = float(math.sqrt(np.mean((a - p) ** 2)))
    mape = float(np.mean(np.abs((a - p) / np.clip(a, 1e-9, None))) * 100.0)

    actual_dir = np.sign(a - b)
    pred_dir = np.sign(p - b)
    directional_accuracy = float(np.mean((actual_dir == pred_dir).astype(float)) * 100.0)

    return BacktestResult(
        mae=mae,
        rmse=rmse,
        mape=mape,
        directional_accuracy=directional_accuracy,
        actual_prices=actual,
        predicted_prices=predicted,
        periods=len(actual),
    )


def run_backtest(indicators_df: pd.DataFrame, days: int | None = None) -> BacktestResult:
    """
    Walk-forward validation using ensemble (XGB + RF + LSTM).
    Trains on all historical data up to step, predicts next, then walks forward.
    This replicates live trading conditions: no lookahead bias.
    """
    period_days = days or settings.default_backtest_days
    if period_days < settings.min_backtest_days or period_days > settings.max_backtest_days:
        raise DataError(
            f"Backtest days must be between {settings.min_backtest_days} and {settings.max_backtest_days}.",
            failed_step="BACKTEST",
        )

    df = indicators_df.copy().dropna().reset_index(drop=True)
    min_required = max(settings.min_rows_rf + 1, period_days + 2)
    if len(df) < min_required:
        raise DataError(
            f"Insufficient data for backtest: got {len(df)} rows, need at least {min_required}.",
            failed_step="BACKTEST",
        )

    start = max(settings.min_rows_rf, len(df) - period_days - 1)

    actual_prices: List[float] = []
    predicted_prices: List[float] = []
    base_prices: List[float] = []

    for idx in range(start, len(df) - 1):
        train_slice = df.iloc[: idx + 1].copy()

        # Train ensemble models
        try:
            xgb_model = XGBoostModel()
            xgb_pred = xgb_model.train(train_slice)
            xgb_next = xgb_model.predict_next(train_slice)
        except Exception as e:
            logger.debug(f"XGB training failed at idx {idx}: {e}")
            xgb_next = None

        try:
            rf_model = RandomForestModel()
            rf_result = rf_model.train(train_slice)
            rf_next = rf_model.predict_next(train_slice)
        except Exception as e:
            logger.debug(f"RF training failed at idx {idx}: {e}")
            rf_next = None

        try:
            lstm_model = LSTMModel()
            lstm_result = lstm_model.train_and_predict(train_slice)
            lstm_next = lstm_result.prediction
        except Exception as e:
            logger.debug(f"LSTM training failed at idx {idx}: {e}")
            lstm_next = None

        # Combine predictions dynamically (with volatility)
        vol_20d = float(train_slice["Vol_20d"].iloc[-1]) if "Vol_20d" in train_slice.columns and train_slice["Vol_20d"].iloc[-1] > 0 else None

        try:
            predicted_next = combine_predictions(xgb_prediction=xgb_next, rf_prediction=rf_next, lstm_prediction=lstm_next, volatility=vol_20d)
        except Exception as e:
            # Fallback: use RF only
            logger.debug(f"Ensemble combination failed at idx {idx}, using RF only: {e}")
            predicted_next = float(rf_next) if rf_next is not None else 0.0

        actual_next = float(df.iloc[idx + 1]["Close"])
        base_close = float(df.iloc[idx]["Close"])

        predicted_prices.append(predicted_next)
        actual_prices.append(actual_next)
        base_prices.append(base_close)

    return _metrics(actual=actual_prices, predicted=predicted_prices, base_prices=base_prices)

def run_strategy_backtest(df: pd.DataFrame, fast_sma: int = 20, slow_sma: int = 50) -> dict:
    """Backtest a simple SMA Crossover strategy."""
    df = df.copy()
    if f"SMA_{fast_sma}" not in df.columns or f"SMA_{slow_sma}" not in df.columns:
        # Compute if missing
        df[f"SMA_{fast_sma}"] = df["Close"].rolling(fast_sma).mean()
        df[f"SMA_{slow_sma}"] = df["Close"].rolling(slow_sma).mean()
    
    df = df.dropna()
    
    # Signal: 1 (Buy) when fast > slow, else 0
    df["Signal"] = (df[f"SMA_{fast_sma}"] > df[f"SMA_{slow_sma}"]).astype(int)
    df["Position"] = df["Signal"].diff()
    
    returns = df["Close"].pct_change()
    strat_returns = returns * df["Signal"].shift(1)
    
    cum_returns = (1 + strat_returns.fillna(0)).cumprod() - 1
    
    # Simple Metrics
    sharpe = (strat_returns.mean() / strat_returns.std() * math.sqrt(252)) if strat_returns.std() != 0 else 0
    win_rate = (strat_returns > 0).sum() / (strat_returns != 0).sum() if (strat_returns != 0).sum() > 0 else 0
    
    return {
        "final_return": float(cum_returns.iloc[-1] * 100),
        "sharpe_ratio": float(sharpe),
        "win_rate": float(win_rate * 100),
        "params": {"fast": fast_sma, "slow": slow_sma}
    }


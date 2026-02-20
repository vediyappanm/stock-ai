"""Prediction orchestrator for XGBoost, RF, LSTM, and ensemble outputs."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any

import joblib
import pandas as pd

import logging
from config.settings import settings
from models.ensemble import combine_predictions, compute_prediction_interval
from models.lstm import LSTMModel
from models.random_forest import RandomForestModel
from models.xgboost_model import XGBoostModel
from schemas.response_schemas import Prediction
from tools.error_handler import ModelError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _ModelPaths:
    xgb_file: Path
    rf_file: Path
    lstm_file: Path
    meta_file: Path


def _ensure_models_dir() -> Path:
    path = Path(settings.models_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _paths(symbol: str) -> _ModelPaths:
    safe = symbol.replace("/", "_")
    root = _ensure_models_dir()
    return _ModelPaths(
        xgb_file=root / f"{safe}_xgb.json",
        rf_file=root / f"{safe}_rf.joblib",
        lstm_file=root / f"{safe}_lstm.pt",
        meta_file=root / f"{safe}_meta.json",
    )


def _signature(df: pd.DataFrame) -> Dict[str, str]:
    last_date = pd.to_datetime(df["Date"]).max().date().isoformat()
    return {"last_date": last_date, "rows": str(len(df))}


def _load_meta(meta_file: Path) -> Dict[str, Any]:
    if not meta_file.exists():
        return {}
    try:
        return json.loads(meta_file.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_meta(meta_file: Path, payload: Dict[str, Any]) -> None:
    meta_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _can_reuse_models(paths: _ModelPaths, sig: Dict[str, str]) -> bool:
    if not all([paths.xgb_file.exists(), paths.rf_file.exists(), paths.lstm_file.exists()]):
        return False
    meta = _load_meta(paths.meta_file)
    return meta.get("last_date") == sig["last_date"] and meta.get("rows") == sig["rows"]


def predict_price(
    indicators_df: pd.DataFrame,
    resolved_symbol: str,
    model_type: str = "ensemble",
) -> Prediction:
    """
    Train/use cached models (XGB, RF, LSTM) and return complete prediction payload.
    """
    model_type = model_type.strip().lower()
    paths = _paths(resolved_symbol)
    sig = _signature(indicators_df)

    xgb_model = XGBoostModel()
    rf_model = RandomForestModel()
    
    xgb_prediction = 0.0
    rf_prediction = 0.0
    lstm_prediction = 0.0
    
    xgb_residual_std = 1.0
    rf_residual_std = 1.0
    lstm_residual_std = 1.0
    
    feature_importance: Dict[str, float] = {}

    loaded_from_cache = False
    if _can_reuse_models(paths, sig):
        try:
            # Detailed per-model exception logging
            try:
                xgb_model.model.load_model(str(paths.xgb_file))
                xgb_prediction = xgb_model.predict_next(indicators_df)
                logger.info(f"XGBoost model loaded from cache: {paths.xgb_file}")
            except Exception as e:
                logger.error(f"Failed to load XGBoost model from cache: {e}")
                raise ModelError(f"XGBoost cache load failed: {e}")
            
            try:
                rf_model.model = joblib.load(paths.rf_file)
                rf_prediction = rf_model.predict_next(indicators_df)
                logger.info(f"Random Forest model loaded from cache: {paths.rf_file}")
            except Exception as e:
                logger.error(f"Failed to load Random Forest model from cache: {e}")
                raise ModelError(f"Random Forest cache load failed: {e}")
            
            meta = _load_meta(paths.meta_file)
            # Ensure residual_std is never 0 or NaN to prevent interval collapse
            def safe_std(v):
                v = float(v)
                return 1.0 if not math.isfinite(v) or v <= 0 else v

            xgb_residual_std = safe_std(meta.get("xgb_residual_std", 1.0))
            rf_residual_std = safe_std(meta.get("rf_residual_std", 1.0))
            lstm_residual_std = safe_std(meta.get("lstm_residual_std", 1.0))
            feature_importance = meta.get("feature_importance", {})
            
            # 1. Use cached predictions from meta if non-zero/valid
            cached_lstm = meta.get("lstm_prediction", 0)
            if cached_lstm and not math.isnan(float(cached_lstm)) and float(cached_lstm) != 0:
                 lstm_prediction = float(cached_lstm)
                 logger.info(f"Using cached LSTM prediction: {lstm_prediction}")
            else:
                 # 2. If no valid cached prediction, try loading model to re-infer
                 try:
                     lstm_model = LSTMModel.from_checkpoint(paths.lstm_file)
                     lstm_prediction = lstm_model.train_and_predict(indicators_df).prediction
                     logger.info(f"LSTM prediction re-inferred from checkpoint: {lstm_prediction}")
                 except Exception as e:
                     # 3. If model load fails, trigger full retrain
                     raise ModelError(f"Cached LSTM invalid and re-inference failed: {e}")

            loaded_from_cache = True
            logger.info(f"All models successfully loaded from cache for {resolved_symbol}")
        except (ModelError, Exception) as e:
            # Atomic cache strategy: if any model fails, train all fresh
            logger.warning(f"Cache reuse failed for {resolved_symbol}, training fresh models: {e}")
            loaded_from_cache = False

    if not loaded_from_cache:
        # Train XGBoost
        xgb_importance = xgb_model.train(indicators_df)
        xgb_prediction = xgb_model.predict_next(indicators_df)
        xgb_residual_std = 1.0 # Approximate
        
        # Train RF
        rf_result = rf_model.train(indicators_df)
        rf_prediction = rf_model.predict_next(indicators_df)
        rf_residual_std = rf_result.residual_std
        
        # Train LSTM
        lstm_model = LSTMModel()
        lstm_result = lstm_model.train_and_predict(indicators_df)
        lstm_prediction = lstm_result.prediction
        lstm_residual_std = lstm_result.residual_std

        # Save
        xgb_model.model.save_model(str(paths.xgb_file))
        joblib.dump(rf_model.model, paths.rf_file)
        lstm_model.save_checkpoint(paths.lstm_file)
        
        feature_importance = xgb_importance # Primary
        
        _save_meta(
            paths.meta_file,
            {
                **sig,
                "xgb_residual_std": xgb_residual_std,
                "rf_residual_std": rf_residual_std,
                "lstm_residual_std": lstm_residual_std,
                "feature_importance": feature_importance,
                # Cache the predictions too
                "xgb_prediction": xgb_prediction,
                "rf_prediction": rf_prediction,
                "lstm_prediction": lstm_prediction,
            }
        )

    # Extract latest volatility for dynamic ensemble weighting
    vol_20d = None
    if "Vol_20d" in indicators_df.columns:
        vol_20d = float(indicators_df["Vol_20d"].iloc[-1]) if indicators_df["Vol_20d"].iloc[-1] > 0 else None

    if model_type == "random_forest":
        point = rf_prediction
        lower, upper = compute_prediction_interval(point, [rf_residual_std])
    elif model_type == "lstm":
        point = lstm_prediction
        lower, upper = compute_prediction_interval(point, [lstm_residual_std])
    elif model_type == "xgboost":
        point = xgb_prediction
        lower, upper = compute_prediction_interval(point, [xgb_residual_std])
    else:
        point = combine_predictions(xgb_prediction, rf_prediction, lstm_prediction, volatility=vol_20d)
        lower, upper = compute_prediction_interval(point, [xgb_residual_std, rf_residual_std, lstm_residual_std])

    def safe_f(v):
        try:
            v = float(v)
            return 0.0 if not math.isfinite(v) else v
        except (TypeError, ValueError):
            return 0.0

    # Log LSTM degradation (not a fatal error — ensemble will reroute)
    lstm_safe = safe_f(lstm_prediction)
    if lstm_safe == 0.0:
        logger.warning(
            f"LSTM degraded for {resolved_symbol}: lstm={lstm_prediction}. "
            f"Ensemble will use XGB+RF fallback (XGB={xgb_prediction:.2f}, RF={rf_prediction:.2f})."
        )

    # Final sanity check: only raise if the FINAL point is invalid
    # (meaning XGB and RF also failed, not just LSTM)
    final_point = safe_f(point)
    if final_point == 0.0:
        logger.error(
            f"Complete ensemble failure for {resolved_symbol}. "
            f"XGB={xgb_prediction}, RF={rf_prediction}, LSTM={lstm_prediction}"
        )
        raise ModelError(
            f"Prediction engine returned invalid price (0.0) for {resolved_symbol}. "
            "This may indicate insufficient training data or model convergence issues."
        )

    return Prediction(
        point_estimate=safe_f(point),
        lower_bound=safe_f(lower),
        upper_bound=safe_f(upper),
        confidence_level=settings.confidence_level,
        xgb_prediction=safe_f(xgb_prediction),
        rf_prediction=safe_f(rf_prediction),
        lstm_prediction=safe_f(lstm_prediction),
        feature_importance={k: safe_f(v) for k, v in feature_importance.items()},
    )

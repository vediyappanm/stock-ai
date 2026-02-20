"""Production-grade PyTorch LSTM with Multi-Feature Attention support."""

from __future__ import annotations

import math
import os
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Tuple, Dict, Any, List

import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler

import logging
from config.settings import settings
from tools.error_handler import ModelError
from tools.indicators import INDICATOR_COLUMNS

logger = logging.getLogger(__name__)

try:
    import torch
    import torch.nn as nn
except Exception:
    torch = None
    nn = None

def _set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    if torch is not None:
        torch.manual_seed(seed)

class Attention(nn.Module):
    """Temporal attention mechanism to weight historical time steps."""
    def __init__(self, hidden_dim: int):
        super().__init__()
        self.attn = nn.Linear(hidden_dim, 1)

    def forward(self, x):
        # x shape: (batch, seq_len, hidden_dim)
        weights = torch.softmax(self.attn(x), dim=1) # (batch, seq_len, 1)
        context = torch.sum(weights * x, dim=1)      # (batch, hidden_dim)
        return context, weights

class _PriceLSTM(nn.Module):
    def __init__(self, input_size: int) -> None:
        super().__init__()
        self.lstm = nn.LSTM(
            input_size=input_size, 
            hidden_size=settings.lstm_hidden_size_1, 
            num_layers=2,
            batch_first=True, 
            dropout=settings.lstm_dropout
        )
        self.attention = Attention(settings.lstm_hidden_size_1)
        self.fc = nn.Linear(settings.lstm_hidden_size_1, 1)

    def forward(self, x):
        # x: (batch, seq_len, features)
        out, _ = self.lstm(x) # (batch, seq_len, hidden)
        context, _ = self.attention(out) # (batch, hidden)
        return self.fc(context)

@dataclass
class LSTMTrainResult:
    prediction: float
    residual_std: float

class LSTMModel:
    """Multi-feature LSTM model for production stock price forecasting."""

    def __init__(self) -> None:
        if torch is None or nn is None:
            raise ModelError("Torch is not available.", failed_step="PREDICT_PRICE")
        _set_seed(settings.lstm_random_state)
        self.input_size = len(INDICATOR_COLUMNS)
        self.model = _PriceLSTM(input_size=self.input_size)
        self.scaler_x = MinMaxScaler()
        self.scaler_y = MinMaxScaler()
        self.device = torch.device("cpu")
        self.model.to(self.device)

    def _prepare_data(self, df: pd.DataFrame, is_training: bool = True) -> Tuple[np.ndarray, np.ndarray]:
        data_x = df[INDICATOR_COLUMNS].values
        data_y = df["Close"].values.reshape(-1, 1)

        if is_training:
            scaled_x = self.scaler_x.fit_transform(data_x)
            scaled_y = self.scaler_y.fit_transform(data_y)
        else:
            scaled_x = self.scaler_x.transform(data_x)
            scaled_y = self.scaler_y.transform(data_y)

        X, y = [], []
        seq_len = settings.lstm_sequence_length
        for i in range(seq_len, len(scaled_x)):
            X.append(scaled_x[i-seq_len : i])
            y.append(scaled_y[i])
        
        return np.array(X, dtype=np.float32), np.array(y, dtype=np.float32)

    def train_and_predict(self, df: pd.DataFrame) -> LSTMTrainResult:
        """Complete train+predict cycle for a single ticker."""
        if len(df) < settings.min_rows_lstm:
            return LSTMTrainResult(prediction=float(df["Close"].iloc[-1]), residual_std=1.0)

        X, y = self._prepare_data(df, is_training=True)
        X_tensor = torch.from_numpy(X).to(self.device)
        y_tensor = torch.from_numpy(y).to(self.device)

        criterion = nn.MSELoss()
        optimizer = torch.optim.Adam(self.model.parameters(), lr=settings.lstm_learning_rate)

        # Production training loop
        self.model.train()
        epochs = settings.lstm_epochs_dev if settings.is_dev_mode else settings.lstm_epochs_prod
        
        # Ensure data is valid
        if not np.isfinite(X).all() or not np.isfinite(y).all():
            logger.warning(f"LSTM training skipped: data contains non-finite values")
            return LSTMTrainResult(prediction=float(df["Close"].iloc[-1]), residual_std=1.0)
            
        for _ in range(epochs):
            optimizer.zero_grad()
            outputs = self.model(X_tensor)
            loss = criterion(outputs, y_tensor)
            if torch.isnan(loss):
                break
            loss.backward()
            # Gradient clipping for stability
            nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=1.0)
            optimizer.step()

        # Predict next step
        self.model.eval()
        with torch.no_grad():
            full_pred_scaled = self.model(X_tensor).cpu().numpy()
            residuals = y - full_pred_scaled
            res_std_scaled = float(np.std(residuals))

            latest_seq = torch.from_numpy(self.scaler_x.transform(df[INDICATOR_COLUMNS].tail(settings.lstm_sequence_length).values)).unsqueeze(0).to(self.device).float()
            next_scaled = self.model(latest_seq).cpu().numpy()
            next_price = self.scaler_y.inverse_transform(next_scaled)[0][0]

        # Denormalize residual std (roughly)
        y_range = self.scaler_y.data_max_[0] - self.scaler_y.data_min_[0]
        prediction = float(next_price)
        
        # Final sanity check for NaN
        if not math.isfinite(prediction):
            logger.warning("LSTM prediction resulted in NaN, using baseline fallback")
            return LSTMTrainResult(prediction=float(df["Close"].iloc[-1]), residual_std=1.0)
            
        return LSTMTrainResult(prediction=prediction, residual_std=float(res_std_scaled * y_range))

    def save_checkpoint(self, path: str | Path) -> None:
        """Save model state and scalers."""
        state = {
            "model_state": self.model.state_dict(),
            "scaler_x": self.scaler_x,
            "scaler_y": self.scaler_y
        }
        torch.save(state, str(path))

    @classmethod
    def from_checkpoint(cls, path: str | Path) -> "LSTMModel":
        instance = cls()
        # PyTorch 2.6+ defaults to weights_only=True. 
        # We need weights_only=False to load sklearn scalers stored in the checkpoint.
        state = torch.load(str(path), map_location="cpu", weights_only=False)
        instance.model.load_state_dict(state["model_state"])
        instance.scaler_x = state["scaler_x"]
        instance.scaler_y = state["scaler_y"]
        instance.model.eval()
        return instance


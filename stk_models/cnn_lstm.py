"""CNN-LSTM hybrid model for pattern recognition + temporal dependencies (Phase 3)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Tuple
import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler

logger = logging.getLogger(__name__)

try:
    import torch
    import torch.nn as nn
    from torch.optim import Adam
    _TORCH_AVAILABLE = True
except Exception:
    torch = None
    nn = None
    _TORCH_AVAILABLE = False


if _TORCH_AVAILABLE:
    class CNNLSTMNet(nn.Module):
        """1D CNN → LSTM → Dense for stock price prediction."""

        def __init__(self, input_size: int, cnn_filters: int = 32, lstm_hidden: int = 64):
            super().__init__()
            self.cnn = nn.Sequential(
                nn.Conv1d(in_channels=1, out_channels=cnn_filters, kernel_size=3, padding=1),
                nn.ReLU(),
            )
            self.pool = nn.MaxPool1d(kernel_size=2, stride=1, padding=1)

            self.lstm = nn.LSTM(
                input_size=cnn_filters,
                hidden_size=lstm_hidden,
                num_layers=2,
                batch_first=True,
                dropout=0.2,
            )

            self.fc = nn.Linear(lstm_hidden, 1)

        def forward(self, x):
            # x: (batch, seq_len, features)
            x_cnn = x.unsqueeze(1)         # (batch, 1, seq_len)
            x_cnn = self.cnn(x_cnn)        # (batch, filters, seq_len)
            x_cnn = self.pool(x_cnn)
            x_cnn = x_cnn.permute(0, 2, 1) # (batch, seq_len, filters)

            lstm_out, _ = self.lstm(x_cnn)
            lstm_final = lstm_out[:, -1, :]
            return self.fc(lstm_final)

    class CNNLSTMModel:
        """Wrapper for CNN-LSTM training and inference."""

        def __init__(self, seq_len: int = 20, cnn_filters: int = 32, lstm_hidden: int = 64):
            if not _TORCH_AVAILABLE:
                raise ImportError("PyTorch required for CNN-LSTM")
            self.seq_len = seq_len
            self.scaler = MinMaxScaler()
            self.model = CNNLSTMNet(input_size=seq_len, cnn_filters=cnn_filters, lstm_hidden=lstm_hidden)
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            self.model.to(self.device)

        def prepare_sequences(self, df: pd.DataFrame, feature_cols: list[str] | None = None) -> Tuple[np.ndarray, np.ndarray]:
            if feature_cols is None:
                feature_cols = ["Close"]
            data = df[feature_cols].values
            data_scaled = self.scaler.fit_transform(data)
            X, y = [], []
            for i in range(len(data_scaled) - self.seq_len):
                X.append(data_scaled[i : i + self.seq_len])
                y.append(data_scaled[i + self.seq_len, 0])
            return np.array(X), np.array(y)

        def train(self, df: pd.DataFrame, epochs: int = 50, batch_size: int = 32, lr: float = 0.001) -> float:
            X, y = self.prepare_sequences(df)
            if len(X) < batch_size:
                logger.warning("Insufficient data for CNN-LSTM training")
                return 0.0
            X_tensor = torch.FloatTensor(X).to(self.device)
            y_tensor = torch.FloatTensor(y).unsqueeze(1).to(self.device)
            optimizer = Adam(self.model.parameters(), lr=lr)
            criterion = nn.MSELoss()
            self.model.train()
            loss = None
            for epoch in range(epochs):
                optimizer.zero_grad()
                output = self.model(X_tensor)
                loss = criterion(output, y_tensor)
                loss.backward()
                optimizer.step()
                if (epoch + 1) % 10 == 0:
                    logger.debug(f"Epoch {epoch+1}/{epochs}, Loss={loss.item():.6f}")
            return float(loss.item()) if loss is not None else 0.0

        def predict(self, df: pd.DataFrame) -> float:
            X, _ = self.prepare_sequences(df)
            if len(X) == 0:
                return 0.0
            X_tensor = torch.FloatTensor(X[-1:]).to(self.device)
            self.model.eval()
            with torch.no_grad():
                pred_scaled = self.model(X_tensor).item()
            dummy = np.zeros((1, len(self.scaler.scale_)))
            dummy[0, 0] = pred_scaled
            return float(self.scaler.inverse_transform(dummy)[0, 0])

        def save_checkpoint(self, path: Path | str) -> None:
            torch.save({
                "model_state": self.model.state_dict(),
                "scaler_mean": self.scaler.mean_,
                "scaler_scale": self.scaler.scale_,
            }, path)

        @classmethod
        def load_checkpoint(cls, path: Path | str) -> "CNNLSTMModel":
            checkpoint = torch.load(path, map_location="cpu")
            model = cls()
            model.model.load_state_dict(checkpoint["model_state"])
            model.scaler.mean_ = checkpoint["scaler_mean"]
            model.scaler.scale_ = checkpoint["scaler_scale"]
            return model

else:
    class CNNLSTMModel:  # type: ignore[no-redef]
        """Stub — torch not available."""
        def __init__(self, *args, **kwargs):
            raise ImportError("PyTorch required for CNN-LSTM")

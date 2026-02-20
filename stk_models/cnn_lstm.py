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
except Exception:
    torch = None
    nn = None


class CNNLSTMNet(nn.Module):
    """1D CNN → LSTM → Dense for stock price prediction."""

    def __init__(self, input_size: int, cnn_filters: int = 32, lstm_hidden: int = 64):
        super().__init__()
        # 1D CNN: extract local patterns (2-5 day windows)
        self.cnn = nn.Conv1d(
            in_channels=1,
            out_channels=cnn_filters,
            kernel_size=3,
            padding=1,
            activation=nn.ReLU(),
        )
        self.pool = nn.MaxPool1d(kernel_size=2, stride=1, padding=1)

        # LSTM: capture long-term dependencies
        self.lstm = nn.LSTM(
            input_size=cnn_filters,
            hidden_size=lstm_hidden,
            num_layers=2,
            batch_first=True,
            dropout=0.2,
        )

        # Dense: final prediction
        self.fc = nn.Linear(lstm_hidden, 1)

    def forward(self, x):
        # x: (batch, seq_len, features)
        batch_size = x.shape[0]

        # CNN: (batch, seq_len, features) -> (batch, 1, seq_len, features)
        x_cnn = x.unsqueeze(1)
        x_cnn = self.cnn(x_cnn)  # (batch, filters, seq_len)
        x_cnn = self.pool(x_cnn)
        x_cnn = x_cnn.permute(0, 2, 1)  # (batch, seq_len, filters)

        # LSTM
        lstm_out, _ = self.lstm(x_cnn)  # (batch, seq_len, hidden)
        lstm_final = lstm_out[:, -1, :]  # (batch, hidden)

        # Dense
        return self.fc(lstm_final)


class CNNLSTMModel:
    """Wrapper for CNN-LSTM training and inference."""

    def __init__(self, seq_len: int = 20, cnn_filters: int = 32, lstm_hidden: int = 64):
        if torch is None or nn is None:
            raise ImportError("PyTorch required for CNN-LSTM")

        self.seq_len = seq_len
        self.scaler = MinMaxScaler()
        self.model = CNNLSTMNet(input_size=seq_len, cnn_filters=cnn_filters, lstm_hidden=lstm_hidden)
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model.to(self.device)

    def prepare_sequences(self, df: pd.DataFrame, feature_cols: list[str] | None = None) -> Tuple[np.ndarray, np.ndarray]:
        """Prepare sequences for training."""
        if feature_cols is None:
            feature_cols = ["Close"]

        data = df[feature_cols].values
        data_scaled = self.scaler.fit_transform(data)

        X, y = [], []
        for i in range(len(data_scaled) - self.seq_len):
            X.append(data_scaled[i : i + self.seq_len])
            y.append(data_scaled[i + self.seq_len, 0])  # Next close price

        return np.array(X), np.array(y)

    def train(self, df: pd.DataFrame, epochs: int = 50, batch_size: int = 32, lr: float = 0.001) -> float:
        """Train the CNN-LSTM model."""
        X, y = self.prepare_sequences(df)

        if len(X) < batch_size:
            logger.warning("Insufficient data for CNN-LSTM training")
            return 0.0

        X_tensor = torch.FloatTensor(X).to(self.device)
        y_tensor = torch.FloatTensor(y).unsqueeze(1).to(self.device)

        optimizer = Adam(self.model.parameters(), lr=lr)
        criterion = nn.MSELoss()

        self.model.train()
        for epoch in range(epochs):
            optimizer.zero_grad()
            output = self.model(X_tensor)
            loss = criterion(output, y_tensor)
            loss.backward()
            optimizer.step()

            if (epoch + 1) % 10 == 0:
                logger.debug(f"Epoch {epoch+1}/{epochs}, Loss={loss.item():.6f}")

        logger.info(f"CNN-LSTM trained: {epochs} epochs, final loss={loss.item():.6f}")
        return float(loss.item())

    def predict(self, df: pd.DataFrame) -> float:
        """Predict next price."""
        X, _ = self.prepare_sequences(df)

        if len(X) == 0:
            return 0.0

        X_tensor = torch.FloatTensor(X[-1:]).to(self.device)

        self.model.eval()
        with torch.no_grad():
            pred_scaled = self.model(X_tensor).item()

        # Inverse scale
        dummy = np.zeros((1, len(self.scaler.scale_)))
        dummy[0, 0] = pred_scaled
        pred_original = self.scaler.inverse_transform(dummy)[0, 0]

        return float(pred_original)

    def save_checkpoint(self, path: Path | str) -> None:
        """Save model checkpoint."""
        checkpoint = {
            "model_state": self.model.state_dict(),
            "scaler_mean": self.scaler.mean_,
            "scaler_scale": self.scaler.scale_,
        }
        torch.save(checkpoint, path)
        logger.info(f"CNN-LSTM checkpoint saved to {path}")

    @classmethod
    def load_checkpoint(cls, path: Path | str) -> CNNLSTMModel:
        """Load model checkpoint."""
        checkpoint = torch.load(path, map_location="cpu")
        model = cls()
        model.model.load_state_dict(checkpoint["model_state"])
        model.scaler.mean_ = checkpoint["scaler_mean"]
        model.scaler.scale_ = checkpoint["scaler_scale"]
        logger.info(f"CNN-LSTM checkpoint loaded from {path}")
        return model

"""Shared synthetic data fixtures for deterministic tests."""

from __future__ import annotations

import numpy as np
import pandas as pd


def create_synthetic_ohlcv(rows: int = 260, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    base = 100.0
    returns = rng.normal(0.0005, 0.01, size=rows)
    close = base * np.cumprod(1 + returns)
    open_ = close * (1 + rng.normal(0, 0.002, size=rows))
    high = np.maximum(open_, close) * (1 + rng.uniform(0.0, 0.01, size=rows))
    low = np.minimum(open_, close) * (1 - rng.uniform(0.0, 0.01, size=rows))
    volume = rng.integers(800_000, 2_000_000, size=rows)

    return pd.DataFrame(
        {
            "Date": pd.date_range("2024-01-01", periods=rows, freq="D"),
            "Open": open_,
            "High": high,
            "Low": low,
            "Close": close,
            "Volume": volume,
        }
    )


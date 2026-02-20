"""Technical indicator calculation utilities."""

from __future__ import annotations

import pandas as pd

try:
    from ta.momentum import RSIIndicator, StochasticOscillator, StochRSIIndicator, WilliamsRIndicator, CCIIndicator
    from ta.trend import MACD, SMAIndicator, ADXIndicator, PSARIndicator
    from ta.volatility import AverageTrueRange, BollingerBands, KeltnerChannels, DonchianChannels
    from ta.volume import OnBalanceVolumeIndicator, MFIIndicator
    _HAS_TA = True
except Exception:  # pragma: no cover - optional dependency fallback
    RSIIndicator = None
    StochasticOscillator = None
    MACD = None
    SMAIndicator = None
    AverageTrueRange = None
    BollingerBands = None
    OnBalanceVolumeIndicator = None
    StochRSIIndicator = None
    WilliamsRIndicator = None
    CCIIndicator = None
    ADXIndicator = None
    PSARIndicator = None
    KeltnerChannels = None
    DonchianChannels = None
    MFIIndicator = None
    _HAS_TA = False

from config.settings import settings
from tools.error_handler import DataError


INDICATOR_COLUMNS = [
    "SMA_20", "SMA_50", "SMA_200",
    "RSI_14", "Stoch_RSI", "Williams_R", "CCI_20",
    "MACD", "MACD_Signal", "MACD_Histogram",
    "ADX", "ADX_Pos", "ADX_Neg", "PSAR",
    "BB_Upper", "BB_Middle", "BB_Lower",
    "KC_Upper", "KC_Middle", "KC_Lower",
    "DC_Upper", "DC_Middle", "DC_Lower",
    "ATR_14", "OBV", "MFI_14", "VWAP",
    "Stochastic_K", "Stochastic_D",
    "Return_1d", "Return_3d", "Return_5d",
    "Vol_10d", "Vol_20d",
    "Price_Diff_1d", "Price_Diff_5d", "Price_Momentum_20",
    "VIX", "Yield_10Y", "Yield_2Y", "FedRate", "YieldCurveSlope", "VIXMomentum"
]


def _validate_input(df: pd.DataFrame) -> None:
    required = {"Date", "Open", "High", "Low", "Close", "Volume"}
    missing = required.difference(df.columns)
    if missing:
        raise DataError(
            f"Indicator input missing required OHLCV columns: {', '.join(sorted(missing))}",
            failed_step="COMPUTE_INDICATORS",
        )
    if len(df) < settings.min_rows_indicators:
        raise DataError(
            f"Insufficient data for indicators: got {len(df)} rows, need at least {settings.min_rows_indicators}.",
            failed_step="COMPUTE_INDICATORS",
        )


def compute_indicators(ohlcv: pd.DataFrame, macro_data: pd.DataFrame | None = None) -> pd.DataFrame:
    """
    Compute 40+ professional indicators + macro features for high-alpha ML feature engineering.
    macro_data: optional DataFrame with VIX, Yield_10Y, FedRate columns
    """
    _validate_input(ohlcv)
    df = ohlcv.copy().reset_index(drop=True)

    # Merge macro features if provided
    if macro_data is not None and not macro_data.empty:
        df["Date"] = pd.to_datetime(df["Date"])
        macro_data_copy = macro_data.copy()
        macro_data_copy["Date"] = pd.to_datetime(macro_data_copy["Date"])
        df = df.merge(macro_data_copy[["Date", "VIX", "Yield_10Y", "FedRate"]], on="Date", how="left")
        df[["VIX", "Yield_10Y", "FedRate"]] = df[["VIX", "Yield_10Y", "FedRate"]].ffill().fillna(0.0)
    else:
        # Initialize with zeros if not provided
        df["VIX"] = 0.0
        df["Yield_10Y"] = 0.0
        df["FedRate"] = 0.0

    close = df["Close"]
    high = df["High"]
    low = df["Low"]
    volume = df["Volume"]

    if _HAS_TA:
        # Moving Averages
        df["SMA_20"] = SMAIndicator(close=close, window=20).sma_indicator()
        df["SMA_50"] = SMAIndicator(close=close, window=50).sma_indicator()
        df["SMA_200"] = SMAIndicator(close=close, window=200).sma_indicator()

        # Momentum
        df["RSI_14"] = RSIIndicator(close=close, window=14).rsi()
        df["Stoch_RSI"] = StochRSIIndicator(close=close, window=14, smooth1=3, smooth2=3).stochrsi()
        df["Williams_R"] = WilliamsRIndicator(high=high, low=low, close=close, lbp=14).williams_r()
        df["CCI_20"] = CCIIndicator(high=high, low=low, close=close, window=20).cci()

        # MACD
        macd = MACD(close=close, window_fast=12, window_slow=26, window_sign=9)
        df["MACD"] = macd.macd()
        df["MACD_Signal"] = macd.macd_signal()
        df["MACD_Histogram"] = macd.macd_diff()

        # Trend (ADX, PSAR)
        adx_ind = ADXIndicator(high=high, low=low, close=close, window=14)
        df["ADX"] = adx_ind.adx()
        df["ADX_Pos"] = adx_ind.adx_pos()
        df["ADX_Neg"] = adx_ind.adx_neg()
        
        psar_ind = PSARIndicator(high=high, low=low, close=close)
        df["PSAR"] = psar_ind.psar()

        # Volatility (BB, KC, DC)
        bb = BollingerBands(close=close, window=20, window_dev=2)
        df["BB_Upper"] = bb.bollinger_hband()
        df["BB_Middle"] = bb.bollinger_mavg()
        df["BB_Lower"] = bb.bollinger_lband()
        
        kc = KeltnerChannels(high=high, low=low, close=close, window=20, window_atr=10)
        df["KC_Upper"] = kc.keltner_channel_hband()
        df["KC_Middle"] = kc.keltner_channel_mband()
        df["KC_Lower"] = kc.keltner_channel_lband()
        
        dc = DonchianChannels(high=high, low=low, close=close, window=20)
        df["DC_Upper"] = dc.donchian_channel_hband()
        df["DC_Middle"] = dc.donchian_channel_mband()
        df["DC_Lower"] = dc.donchian_channel_lband()

        # ATR & Volume
        df["ATR_14"] = AverageTrueRange(high=high, low=low, close=close, window=14).average_true_range()
        df["OBV"] = OnBalanceVolumeIndicator(close=close, volume=volume).on_balance_volume()
        df["MFI_14"] = MFIIndicator(high=high, low=low, close=close, volume=volume, window=14).money_flow_index()

        stoch = StochasticOscillator(high=high, low=low, close=close, window=14, smooth_window=3)
        df["Stochastic_K"] = stoch.stoch()
        df["Stochastic_D"] = stoch.stoch_signal()
    else:
        # Mini-fallback (Core indicators only for safety if ta is missing)
        df["SMA_20"] = close.rolling(20).mean()
        df["SMA_50"] = close.rolling(50).mean()
        df["SMA_200"] = close.rolling(200).mean()
        df["RSI_14"] = close.diff().clip(lower=0).rolling(14).mean() / close.diff().abs().rolling(14).mean() * 100
        df["MACD"] = close.ewm(span=12).mean() - close.ewm(span=26).mean()
        # Filling defaults for others in fallback
        for col in INDICATOR_COLUMNS:
            if col not in df.columns: df[col] = 0.0

    # Custom Engineering: VWAP
    df["VWAP"] = (volume * (high + low + close) / 3).cumsum() / volume.cumsum()

    # Custom Engineering: Returns & Volatility
    df["Return_1d"] = close.pct_change(1)
    df["Return_3d"] = close.pct_change(3)
    df["Return_5d"] = close.pct_change(5)
    df["Vol_10d"] = df["Return_1d"].rolling(10).std()
    df["Vol_20d"] = df["Return_1d"].rolling(20).std()

    # Non-Stationarity Handling: Price Differencing & Momentum
    # These reduce dependence on absolute price levels
    df["Price_Diff_1d"] = close.diff(1)
    df["Price_Diff_5d"] = close.diff(5)
    df["Price_Momentum_20"] = (close - close.shift(20)) / close.shift(20)  # 20-day momentum

    # Final cleanup — always apply to handle NaN/Inf from warmup periods
    import numpy as _np
    # Replace +/- inf first (e.g. VWAP on zero-volume days)
    df[INDICATOR_COLUMNS] = df[INDICATOR_COLUMNS].replace([_np.inf, -_np.inf], _np.nan)
    # Forward-fill, then backward-fill, then zero for any remaining gaps
    df[INDICATOR_COLUMNS] = df[INDICATOR_COLUMNS].ffill().bfill().fillna(0.0)

    return df


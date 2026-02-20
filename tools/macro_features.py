"""Macro economic features: VIX, 10Y yield, Fed rates."""

from __future__ import annotations

import pandas as pd
import logging

logger = logging.getLogger(__name__)

try:
    import yfinance as yf
    _HAS_YF = True
except Exception:
    _HAS_YF = False


def fetch_macro_features(start_date: str | None = None, end_date: str | None = None) -> pd.DataFrame:
    """
    Fetch macro features: VIX, 10Y yield, Fed rate, yield curve slope.
    Returns DataFrame with Date, VIX, Yield_10Y, FedRate, YieldCurveSlope columns.
    """
    if not _HAS_YF:
        logger.warning("yfinance not available for macro features")
        return pd.DataFrame()

    try:
        # VIX: ^VIX (market volatility index)
        vix = yf.download("^VIX", start=start_date, end=end_date, progress=False)
        vix = vix[["Close"]].rename(columns={"Close": "VIX"}).reset_index()

        # 10Y Treasury: ^TNX
        tnx = yf.download("^TNX", start=start_date, end=end_date, progress=False)
        tnx = tnx[["Close"]].rename(columns={"Close": "Yield_10Y"}).reset_index()

        # 2Y Treasury: ^TYX (for yield curve slope)
        tyx = yf.download("^TYX", start=start_date, end=end_date, progress=False)
        tyx = tyx[["Close"]].rename(columns={"Close": "Yield_2Y"}).reset_index()

        # Fed Funds Rate: ^IRX (13-week T-bill as proxy)
        irx = yf.download("^IRX", start=start_date, end=end_date, progress=False)
        irx = irx[["Close"]].rename(columns={"Close": "FedRate"}).reset_index()

        # Merge on Date
        macro = vix.merge(tnx, on="Date", how="outer").merge(tyx, on="Date", how="outer").merge(irx, on="Date", how="outer")
        macro = macro.sort_values("Date").reset_index(drop=True)

        # Calculate yield curve slope (10Y - 2Y spread)
        macro["YieldCurveSlope"] = macro["Yield_10Y"] - macro["Yield_2Y"]

        # VIX momentum (5-day rolling change)
        macro["VIXMomentum"] = macro["VIX"].diff(5)

        # Fill gaps with forward fill
        cols_to_fill = ["VIX", "Yield_10Y", "Yield_2Y", "FedRate", "YieldCurveSlope", "VIXMomentum"]
        macro[cols_to_fill] = macro[cols_to_fill].ffill().fillna(0.0)

        logger.info(f"Fetched macro features: {len(macro)} rows, {macro['Date'].min()} to {macro['Date'].max()}")
        return macro
    except Exception as e:
        logger.error(f"Failed to fetch macro features: {e}")
        return pd.DataFrame()


def merge_macro_features(ohlcv: pd.DataFrame, macro: pd.DataFrame | None = None) -> pd.DataFrame:
    """
    Merge macro features into OHLCV DataFrame on Date.
    If macro is None, fetches automatically.
    """
    if macro is None or macro.empty:
        macro = fetch_macro_features(
            start_date=ohlcv["Date"].min().strftime("%Y-%m-%d") if pd.api.types.is_datetime64_any_dtype(ohlcv["Date"]) else None,
            end_date=ohlcv["Date"].max().strftime("%Y-%m-%d") if pd.api.types.is_datetime64_any_dtype(ohlcv["Date"]) else None,
        )

    if macro.empty:
        return ohlcv

    # Ensure Date columns are datetime
    ohlcv_copy = ohlcv.copy()
    ohlcv_copy["Date"] = pd.to_datetime(ohlcv_copy["Date"])
    macro["Date"] = pd.to_datetime(macro["Date"])

    # Left join: preserve all stock data, add macro where available
    merged = ohlcv_copy.merge(macro[["Date", "VIX", "Yield_10Y", "FedRate"]], on="Date", how="left")

    # Forward fill macro gaps
    merged[["VIX", "Yield_10Y", "FedRate"]] = merged[["VIX", "Yield_10Y", "FedRate"]].ffill().fillna(0.0)

    return merged

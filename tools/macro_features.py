"""Macro economic features: VIX, 10Y yield, Fed rates."""

from __future__ import annotations

import pandas as pd
import logging

logger = logging.getLogger(__name__)

try:
    import yfinance as yf
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
    _HAS_YF = True
except Exception:
    _HAS_YF = False

from tools.yf_helper import get_yf_session

def fetch_macro_features(start_date: str | None = None, end_date: str | None = None) -> pd.DataFrame:
    """
    Fetch macro features: VIX, 10Y yield, Fed rate, yield curve slope.
    Returns DataFrame with Date, VIX, Yield_10Y, FedRate, YieldCurveSlope columns.
    """
    if not _HAS_YF:
        logger.warning("yfinance not available for macro features")
        return pd.DataFrame()

    session = get_yf_session()

    try:
        # Download each symbol separately and handle multi-index columns
        def download_and_clean(symbol: str, column_name: str):
            logger.info(f"Macro: fetching {symbol}")
            data = yf.download(symbol, start=start_date, end=end_date, progress=False, session=session)
            if data.empty:
                return pd.DataFrame(columns=["Date", column_name])
            
            # Handle multi-index columns from yfinance
            if isinstance(data.columns, pd.MultiIndex):
                data = data.droplevel(1, axis=1)  # Remove ticker level
            
            # Extract Close price and reset index
            if "Close" in data.columns:
                result = data[["Close"]].copy()
                result = result.rename(columns={"Close": column_name})
                result = result.reset_index()
                return result
            else:
                return pd.DataFrame(columns=["Date", column_name])

        # Download each macro indicator
        vix = download_and_clean("^VIX", "VIX")
        tnx = download_and_clean("^TNX", "Yield_10Y") 
        tyx = download_and_clean("^TYX", "Yield_2Y")
        irx = download_and_clean("^IRX", "FedRate")

        # Start with VIX as base, then merge others
        macro = vix.copy()
        
        if not tnx.empty:
            macro = macro.merge(tnx, on="Date", how="outer")
        else:
            macro["Yield_10Y"] = 0.0
            
        if not tyx.empty:
            macro = macro.merge(tyx, on="Date", how="outer")
        else:
            macro["Yield_2Y"] = 0.0
            
        if not irx.empty:
            macro = macro.merge(irx, on="Date", how="outer")
        else:
            macro["FedRate"] = 0.0

        macro = macro.sort_values("Date").reset_index(drop=True)

        # Ensure all required columns exist
        for col in ["VIX", "Yield_10Y", "Yield_2Y", "FedRate"]:
            if col not in macro.columns:
                macro[col] = 0.0

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

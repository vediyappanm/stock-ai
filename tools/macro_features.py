"""Macro economic features: VIX, 10Y yield, Fed rates.
Resilient to cloud IP blocks using direct Yahoo v8 chart API.
"""

from __future__ import annotations

import logging
import time
import httpx
import pandas as pd
from typing import Optional

logger = logging.getLogger(__name__)

def _fetch_macro_direct(symbol: str, start_date: str | None = None, end_date: str | None = None) -> Optional[pd.DataFrame]:
    """Resilient fetch for macro symbols using Yahoo v8 direct API."""
    try:
        # Convert dates to timestamps if provided
        now = int(time.time())
        from_ts = now - (365 * 86400) # Default 1 year
        to_ts = now
        
        if start_date:
            from_ts = int(time.mktime(time.strptime(start_date, "%Y-%m-%d")))
        if end_date:
            to_ts = int(time.mktime(time.strptime(end_date, "%Y-%m-%d")))

        url = f"https://query2.finance.yahoo.com/v8/finance/chart/{symbol}"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"}
        
        logger.info(f"Macro: direct fetch for {symbol}")
        resp = httpx.get(url, params={"period1": from_ts, "period2": to_ts, "interval": "1d"}, headers=headers, timeout=10)
        
        if resp.status_code == 200:
            res = resp.json().get("chart", {}).get("result", [None])[0]
            if res:
                ts = res.get("timestamp")
                quote = res["indicators"]["quote"][0]
                if ts and quote.get("close"):
                    df = pd.DataFrame({
                        "Date": pd.to_datetime(ts, unit="s").tz_localize(None),
                        "Close": quote["close"],
                        "Open": quote.get("open", quote["close"]),
                        "High": quote.get("high", quote["close"]),
                        "Low": quote.get("low", quote["close"])
                    })
                    return df
    except Exception as e:
        logger.debug(f"Macro direct fetch failed for {symbol}: {e}")
    return None

def fetch_macro_features(start_date: str | None = None, end_date: str | None = None) -> pd.DataFrame:
    """
    Fetch macro features: VIX, 10Y yield, Fed rate, yield curve slope.
    Returns DataFrame with Date, VIX, Yield_10Y, FedRate, YieldCurveSlope columns.
    """
    try:
        def get_cleaned_ext(symbol: str, col_name: str):
            df = _fetch_macro_direct(symbol, start_date, end_date)
            if df is None or df.empty:
                return pd.DataFrame(columns=["Date", col_name])
            return df[["Date", "Close"]].rename(columns={"Close": col_name})

        # Download each macro indicator
        vix = get_cleaned_ext("^VIX", "VIX")
        tnx = get_cleaned_ext("^TNX", "Yield_10Y") 
        tyx = get_cleaned_ext("^TYX", "Yield_2Y")
        irx = get_cleaned_ext("^IRX", "FedRate")

        # Start with VIX as base, then merge others
        macro = vix.copy()
        
        for df, col in [(tnx, "Yield_10Y"), (tyx, "Yield_2Y"), (irx, "FedRate")]:
            if not df.empty:
                if macro.empty:
                    macro = df
                else:
                    macro = macro.merge(df, on="Date", how="outer")
            else:
                if "Date" not in macro.columns:
                     macro = pd.DataFrame(columns=["Date", "VIX", "Yield_10Y", "Yield_2Y", "FedRate"])
                macro[col] = 0.0

        macro = macro.sort_values("Date").reset_index(drop=True)

        # Ensure all required columns exist
        for col in ["VIX", "Yield_10Y", "Yield_2Y", "FedRate"]:
            if col not in macro.columns:
                macro[col] = 0.0

        # Calculate yield curve slope (10Y - 2Y spread)
        macro["YieldCurveSlope"] = macro["Yield_10Y"] - macro["Yield_2Y"]
        macro["VIXMomentum"] = macro["VIX"].diff(5)

        # Fill gaps with forward fill
        cols_to_fill = ["VIX", "Yield_10Y", "Yield_2Y", "FedRate", "YieldCurveSlope", "VIXMomentum"]
        macro[cols_to_fill] = macro[cols_to_fill].ffill().fillna(0.0)

        logger.info(f"Fetched macro features: {len(macro)} rows")
        return macro
    except Exception as e:
        logger.error(f"Failed to fetch macro features: {e}")
        return pd.DataFrame()

def merge_macro_features(ohlcv: pd.DataFrame, macro: pd.DataFrame | None = None) -> pd.DataFrame:
    """Merge macro features into OHLCV DataFrame on Date."""
    if macro is None or macro.empty:
        # Avoid redundant calls during the same request if possible
        # For now, just fetch.
        macro = fetch_macro_features(
            start_date=ohlcv["Date"].min().strftime("%Y-%m-%d") if "Date" in ohlcv.columns else None,
            end_date=ohlcv["Date"].max().strftime("%Y-%m-%d") if "Date" in ohlcv.columns else None,
        )

    if macro.empty:
        return ohlcv

    ohlcv_copy = ohlcv.copy()
    ohlcv_copy["Date"] = pd.to_datetime(ohlcv_copy["Date"])
    macro["Date"] = pd.to_datetime(macro["Date"])

    macro_cols = ["Date", "VIX", "Yield_10Y", "FedRate", "Yield_2Y", "YieldCurveSlope", "VIXMomentum"]
    available_cols = [c for c in macro_cols if c in macro.columns]
    merged = ohlcv_copy.merge(macro[available_cols], on="Date", how="left")
    
    fill_cols = [c for c in available_cols if c != "Date"]
    merged[fill_cols] = merged[fill_cols].ffill().fillna(0.0)

    return merged

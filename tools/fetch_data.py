"""OHLCV data retrieval with cache-first behavior."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

import logging
import pandas as pd
try:
    import yfinance as yf
except Exception:  # pragma: no cover - optional dependency fallback
    yf = None

logger = logging.getLogger(__name__)

from stk_cache.cache_validator import get_cache_ttl
from stk_cache.data_store import CacheManager
from config.settings import settings
from tools.error_handler import DataError, NetworkError


def _normalize_ohlcv(df: pd.DataFrame, ticker: str = "Unknown") -> pd.DataFrame:
    if df.empty:
        raise DataError(f"No OHLCV data returned for ticker '{ticker}'.", failed_step="FETCH_DATA")

    clean = df.copy()
    
    # Handle MultiIndex columns from recent yfinance versions
    if isinstance(clean.columns, pd.MultiIndex):
        # Case 1: (Attribute, Ticker) -> take Attribute
        # Case 2: (Ticker, Attribute) -> take Attribute
        new_cols = []
        for col in clean.columns:
            if col[0] in ["Open", "High", "Low", "Close", "Volume", "Adj Close"]:
                new_cols.append(col[0])
            elif len(col) > 1 and col[1] in ["Open", "High", "Low", "Close", "Volume", "Adj Close"]:
                new_cols.append(col[1])
            else:
                new_cols.append(col[0]) # Fallback
        clean.columns = new_cols
        
    # Deduplicate columns if any exist (keep first)
    if not clean.columns.is_unique:
        clean = clean.loc[:, ~clean.columns.duplicated()]
    
    # If the index is already named "Date", reset_index will create a "Date" column.
    # Otherwise, it might be named "index" or something else.
    # If "Date" is already a column (from cache), reset_index might add another index column.
    if "Date" not in clean.columns and not isinstance(clean.index, pd.RangeIndex):
        clean = clean.reset_index()
    
    # Map any date-like column name to "Date"
    date_candidates = ["Date", "Datetime", "index", "Date_"]
    for cand in date_candidates:
        if cand in clean.columns and "Date" not in clean.columns:
            clean = clean.rename(columns={cand: "Date"})
            break
            
    # Some cache files have stringified tuples: "('Date', '')"
    for col in clean.columns:
        col_str = str(col)
        if "'Date'" in col_str and "Date" not in clean.columns:
            clean = clean.rename(columns={col: "Date"})
            break

    # If still no Date column, try renaming the first column if it's not a required one
    if "Date" not in clean.columns:
        # Check if first column looks like a date
        try:
             first_col = clean.columns[0]
             pd.to_datetime(clean[first_col].iloc[0])
             clean = clean.rename(columns={first_col: "Date"})
        except:
             pass

    if "Date" not in clean.columns:
        raise DataError("Could not find Date column in OHLCV data.", failed_step="FETCH_DATA")

    clean["Date"] = pd.to_datetime(clean["Date"], utc=False).dt.tz_localize(None)

    required = ["Open", "High", "Low", "Close", "Volume"]
    
    # Handle stringified tuples for OHLCV columns: "('Open', 'TCS.NS')"
    for col in clean.columns:
        col_str = str(col)
        for req in required:
            if req not in clean.columns:
                if f"'{req}'" in col_str or f'"{req}"' in col_str:
                    clean = clean.rename(columns={col: req})
                    break

    missing = [col for col in required if col not in clean.columns]
    if missing:
        raise DataError(
            f"OHLCV payload missing columns: {', '.join(missing)} (Available: {', '.join(map(str, clean.columns))})",
            failed_step="FETCH_DATA",
        )

    return clean[["Date", "Open", "High", "Low", "Close", "Volume"]].dropna().reset_index(drop=True)


def fetch_ohlcv_data(
    ticker_symbol: str,
    exchange: str,
    period: Optional[str] = None,
    days: Optional[int] = None,
    interval: str = "1d",
    cache_manager: Optional[CacheManager] = None,
) -> pd.DataFrame:
    """
    Fetch OHLCV data with cache-first policy.
    
    If 'period' is not provided, uses 'days' to calculate a suitable period.
    """
    if not period:
        if days:
            if days <= 250: period = "1y"
            elif days <= 500: period = "2y"
            elif days <= 1250: period = "5y"
            elif days <= 2500: period = "10y"
            else: period = "max"
        else:
            period = "2y"
            
    cache = cache_manager or CacheManager(cache_dir=settings.cache_dir)
    key = f"{ticker_symbol}_{exchange}"

    logger.info("Fetching OHLCV data for %s on %s (period=%s)", ticker_symbol, exchange, period)

    cached = cache.get(key)
    if cached is not None and cached.data is not None and not cached.data.empty:
        try:
            logger.info("Found cached data for %s", key)
            return _normalize_ohlcv(cached.data, ticker=ticker_symbol)
        except Exception:
            # If cached data is so corrupted it can't be normalized, fall through to re-download
            pass

    if yf is None:
        raise NetworkError(
            "yfinance dependency is not installed. Data fetch is unavailable.",
            failed_step="FETCH_DATA",
        )

    import requests
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36'
    })

    try:
        raw = yf.download(
            tickers=ticker_symbol,
            period=period,
            interval=interval,
            progress=False,
            auto_adjust=False,
            threads=False,
            session=session,
        )
        
        # Fallback to Ticker.history if download returns empty (common for some IP blocks or ticker types)
        if raw.empty:
            logger.info("yf.download returned empty for %s, trying Ticker.history fallback", ticker_symbol)
            ticker_obj = yf.Ticker(ticker_symbol, session=session)
            raw = ticker_obj.history(period=period, interval=interval)
            
    except Exception as exc:
        logger.warning("yf.download failed for %s, trying Ticker.history: %s", ticker_symbol, exc)
        try:
            ticker_obj = yf.Ticker(ticker_symbol, session=session)
            raw = ticker_obj.history(period=period, interval=interval)
        except Exception as inner_exc:
            raise NetworkError(
                f"Failed to fetch market data for {ticker_symbol}: {inner_exc}",
                failed_step="FETCH_DATA",
            ) from inner_exc

    clean = _normalize_ohlcv(raw, ticker=ticker_symbol)
    ttl = get_cache_ttl(exchange, datetime.now())
    cache.set(key=key, data=clean, ttl_minutes=ttl)
    return clean

"""OHLCV data retrieval with multi-source fallback.

Reliability Matrix:
  1. Cache   – Instant local retrieval
  2. Alpaca  – US Stocks (Immune to cloud IP blocks)
  3. Finnhub – Global/India (Cloud friendly)
  4. Yahoo v8 Direct – Direct JSON hit (Fail-soft)
  5. yfinance library – Local fallback
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta
from typing import Optional

import httpx
import pandas as pd

try:
    import yfinance as yf
except Exception:
    yf = None

from config.settings import settings
from stk_cache.cache_validator import get_cache_ttl
from stk_cache.data_store import CacheManager
from tools.error_handler import DataError
from tools.yf_helper import get_yf_session

logger = logging.getLogger(__name__)

_PERIOD_DAYS = {
    "1mo": 30, "3mo": 90, "6mo": 180,
    "1y": 365, "2y": 730, "5y": 1825, "10y": 3650, "max": 7300,
}


def _period_to_timestamps(period: str):
    days = _PERIOD_DAYS.get(period, 730)
    now = int(time.time())
    start = now - (days * 86400)
    return start, now


def _normalize_ohlcv(df: pd.DataFrame, ticker: str) -> pd.DataFrame:
    if df.empty:
        raise DataError(f"Empty data for '{ticker}'", failed_step="FETCH_DATA")

    clean = df.copy()
    if isinstance(clean.columns, pd.MultiIndex):
        clean.columns = [col[0] if isinstance(col, tuple) else col for col in clean.columns]

    # Date column discovery
    if "Date" not in clean.columns and not isinstance(clean.index, pd.RangeIndex):
        clean = clean.reset_index()
    
    for c in clean.columns:
        if str(c).lower() in ["date", "datetime", "timestamp", "t", "index"]:
            clean = clean.rename(columns={c: "Date"})
            break
            
    if "Date" not in clean.columns:
        clean["Date"] = clean.index # Last resort
        
    clean["Date"] = pd.to_datetime(clean["Date"], utc=True).dt.tz_localize(None)

    # OHLCV column discovery
    col_map = {
        "o": "Open", "h": "High", "l": "Low", "c": "Close", "v": "Volume",
        "open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume"
    }
    clean = clean.rename(columns=lambda x: col_map.get(str(x).lower(), x))
    
    # Ensure correct types
    cols = ["Open", "High", "Low", "Close", "Volume"]
    for col in cols:
        if col in clean.columns:
            clean[col] = pd.to_numeric(clean[col], errors='coerce')

    return clean[["Date", "Open", "High", "Low", "Close", "Volume"]].dropna().reset_index(drop=True)


# ─── ALPACA ──────────────────────────────────────────────────────────────────
def _fetch_alpaca(ticker: str, exchange: str, period: str) -> Optional[pd.DataFrame]:
    if exchange not in ["NYSE", "NASDAQ"] or not settings.alpaca_api_key_id:
        return None
    try:
        days = _PERIOD_DAYS.get(period, 730)
        start = (datetime.now() - timedelta(days=days)).isoformat() + "Z"
        url = f"https://data.alpaca.markets/v2/stocks/{ticker}/bars"
        headers = {
            "APCA-API-KEY-ID": settings.alpaca_api_key_id,
            "APCA-API-SECRET-KEY": settings.alpaca_api_secret_key
        }
        resp = httpx.get(url, params={"start": start, "timeframe": "1Day"}, headers=headers, timeout=10)
        if resp.status_code == 200:
            bars = resp.json().get("bars")
            if bars: return pd.DataFrame(bars)
    except Exception as e:
        logger.debug(f"Alpaca fail: {e}")
    return None


# ─── FINNHUB ─────────────────────────────────────────────────────────────────
def _fetch_finnhub(ticker: str, exchange: str, period: str) -> Optional[pd.DataFrame]:
    if not settings.finnhub_api_key: return None
    symbol = ticker.split(".")[0]
    if exchange == "NSE": symbol = f"{symbol}.NS"
    elif exchange == "BSE": symbol = f"{symbol}.BO"
    
    try:
        start, end = _period_to_timestamps(period)
        url = "https://finnhub.io/api/v1/stock/candle"
        resp = httpx.get(url, params={"symbol": symbol, "resolution": "D", "from": start, "to": end, "token": settings.finnhub_api_key}, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("s") == "ok":
                return pd.DataFrame({"Date": data["t"], "Open": data["o"], "High": data["h"], "Low": data["l"], "Close": data["c"], "Volume": data["v"]})
    except Exception as e:
        logger.debug(f"Finnhub fail: {e}")
    return None


# ─── YAHOO DIRECT ────────────────────────────────────────────────────────────
def _fetch_yahoo_direct(ticker: str, period: str) -> Optional[pd.DataFrame]:
    """Hits the v8 chart API directly. Immune to crumb 429s."""
    try:
        start, end = _period_to_timestamps(period)
        url = f"https://query2.finance.yahoo.com/v8/finance/chart/{ticker}"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"}
        resp = httpx.get(url, params={"period1": start, "period2": end, "interval": "1d"}, headers=headers, timeout=10)
        if resp.status_code == 200:
            res = resp.json().get("chart", {}).get("result", [None])[0]
            if res:
                ts = res.get("timestamp")
                quote = res["indicators"]["quote"][0]
                if ts and quote.get("close"):
                    return pd.DataFrame({"Date": ts, "Open": quote["open"], "High": quote["high"], "Low": quote["low"], "Close": quote["close"], "Volume": quote["volume"]})
    except Exception as e:
        logger.debug(f"Yahoo Direct fail: {e}")
    return None


def fetch_ohlcv_data(ticker_symbol: str, exchange: str, period: str = "2y", **kwargs) -> pd.DataFrame:
    cache = kwargs.get("cache_manager") or CacheManager(cache_dir=settings.cache_dir)
    key = f"{ticker_symbol}_{exchange}"

    # 1. Cache
    cached = cache.get(key)
    if cached is not None and not cached.data.empty:
        try: return _normalize_ohlcv(cached.data, ticker_symbol)
        except: pass

    # 2. Alpaca (US Primary)
    raw = _fetch_alpaca(ticker_symbol, exchange, period)
    if raw is not None:
        clean = _normalize_ohlcv(raw, ticker_symbol)
        cache.set(key, clean, ttl_minutes=get_cache_ttl(exchange, datetime.now()))
        return clean

    # 3. Finnhub (Global Cloud Reliable)
    raw = _fetch_finnhub(ticker_symbol, exchange, period)
    if raw is not None:
        clean = _normalize_ohlcv(raw, ticker_symbol)
        cache.set(key, clean, ttl_minutes=get_cache_ttl(exchange, datetime.now()))
        return clean

    # 4. Yahoo Direct (Cookie-less)
    raw = _fetch_yahoo_direct(ticker_symbol, period)
    if raw is not None:
        clean = _normalize_ohlcv(raw, ticker_symbol)
        cache.set(key, clean, ttl_minutes=get_cache_ttl(exchange, datetime.now()))
        return clean

    # 5. yfinance library (Last resort, locally only)
    if yf and not settings.is_dev_mode: # On cloud, this usually fails
        try:
            ticker_obj = yf.Ticker(ticker_symbol, session=get_yf_session())
            raw = ticker_obj.history(period=period)
            if not raw.empty:
                clean = _normalize_ohlcv(raw, ticker_symbol)
                cache.set(key, clean, ttl_minutes=get_cache_ttl(exchange, datetime.now()))
                return clean
        except: pass

    raise DataError(f"Data source exhausted for '{ticker_symbol}'. IP range may be globally blocked by Yahoo.", failed_step="FETCH_DATA")

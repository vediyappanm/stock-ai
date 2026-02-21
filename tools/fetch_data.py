"""OHLCV data retrieval with multi-source fallback.

Source priority:
  1. Cache   – instant hit from local parquet store
  2. Alpaca  – Broker API (Primary for US stocks, immune to cloud IP blocks)
  3. Finnhub – /stock/candle (Secondary for cloud IPs)
  4. Yahoo Finance v8 direct API (cookie + crumb auth)
  5. yfinance library (fallback for local dev)
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
except Exception:  # pragma: no cover
    yf = None

from config.settings import settings
from stk_cache.cache_validator import get_cache_ttl
from stk_cache.data_store import CacheManager
from tools.error_handler import DataError, NetworkError
from tools.yf_helper import get_yf_session

logger = logging.getLogger(__name__)

# ─── Period-to-days mapping ──────────────────────────────────────────────────
_PERIOD_DAYS = {
    "1mo": 30, "3mo": 90, "6mo": 180,
    "1y": 365, "2y": 730, "5y": 1825, "10y": 3650, "max": 7300,
}


def _period_to_timestamps(period: str):
    """Convert a human period string to (from_ts, to_ts) UNIX timestamps."""
    days = _PERIOD_DAYS.get(period, 730)
    now = int(time.time())
    start = now - (days * 86400)
    return start, now


# ─── Normalisation ───────────────────────────────────────────────────────────
def _normalize_ohlcv(df: pd.DataFrame, ticker: str = "Unknown") -> pd.DataFrame:
    """Normalise any OHLCV DataFrame into a clean Date|O|H|L|C|V format."""
    if df.empty:
        raise DataError(
            f"No OHLCV data returned for ticker '{ticker}'.",
            failed_step="FETCH_DATA",
        )

    clean = df.copy()

    # Handle MultiIndex columns (yfinance quirk)
    if isinstance(clean.columns, pd.MultiIndex):
        ohlcv_names = ["Open", "High", "Low", "Close", "Volume", "Adj Close"]
        new_cols = []
        for col in clean.columns:
            if col[0] in ohlcv_names:
                new_cols.append(col[0])
            elif len(col) > 1 and col[1] in ohlcv_names:
                new_cols.append(col[1])
            else:
                new_cols.append(col[0])
        clean.columns = new_cols

    # De-duplicate columns
    if not clean.columns.is_unique:
        clean = clean.loc[:, ~clean.columns.duplicated()]

    # Ensure a "Date" column exists
    if "Date" not in clean.columns:
        if not isinstance(clean.index, pd.RangeIndex):
            clean = clean.reset_index()
        
        candidates = ("Date", "Datetime", "index", "date", "timestamp", "t")
        for candidate in candidates:
            for col in clean.columns:
                if str(col).lower() == candidate:
                    clean = clean.rename(columns={col: "Date"})
                    break
            if "Date" in clean.columns:
                break

    if "Date" not in clean.columns:
        raise DataError(f"Could not find Date column in data for '{ticker}'.", failed_step="FETCH_DATA")

    clean["Date"] = pd.to_datetime(clean["Date"], utc=True).dt.tz_localize(None)

    # Standardise column names
    col_map = {
        "o": "Open", "h": "High", "l": "Low", "c": "Close", "v": "Volume",
        "open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume"
    }
    clean = clean.rename(columns=col_map)

    required = ["Open", "High", "Low", "Close", "Volume"]
    missing = [c for c in required if c not in clean.columns]
    if missing:
        raise DataError(
            f"OHLCV missing columns: {', '.join(missing)} (got: {', '.join(map(str, clean.columns))})",
            failed_step="FETCH_DATA",
        )

    return clean[["Date", "Open", "High", "Low", "Close", "Volume"]].dropna().reset_index(drop=True)


# ─── Source 1: Alpaca (Best for US) ──────────────────────────────────────────
def _fetch_alpaca(ticker_symbol: str, exchange: str, period: str) -> Optional[pd.DataFrame]:
    """Fetch US stock data via Alpaca Market Data API."""
    key_id = settings.alpaca_api_key_id
    secret_key = settings.alpaca_api_secret_key
    if not key_id or not secret_key or exchange not in ["NYSE", "NASDAQ"]:
        return None

    try:
        days = _PERIOD_DAYS.get(period, 730)
        start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
        
        url = f"https://data.alpaca.markets/v2/stocks/{ticker_symbol}/bars"
        params = {"start": start, "timeframe": "1Day"}
        headers = {"XB-Apaca-API-Key-ID": key_id, "XB-Apaca-API-Secret-Key": secret_key}
        
        # Correct Alpaca headers
        headers = {
            "APCA-API-KEY-ID": key_id,
            "APCA-API-SECRET-KEY": secret_key
        }

        logger.info("Alpaca: fetching %s (period=%s)", ticker_symbol, period)
        resp = httpx.get(url, params=params, headers=headers, timeout=10)
        if resp.status_code != 200:
            logger.warning("Alpaca: request failed for %s (code=%d)", ticker_symbol, resp.status_code)
            return None

        bars = resp.json().get("bars", [])
        if not bars:
            return None

        df = pd.DataFrame(bars)
        df = df.rename(columns={"t": "Date", "o": "Open", "h": "High", "l": "Low", "c": "Close", "v": "Volume"})
        return df

    except Exception as exc:
        logger.warning("Alpaca: error for %s: %s", ticker_symbol, exc)
        return None


# ─── Source 2: Finnhub ───────────────────────────────────────────────────────
def _fetch_finnhub(ticker_symbol: str, exchange: str, period: str) -> Optional[pd.DataFrame]:
    """Fetch OHLCV via Finnhub /stock/candle endpoint."""
    api_key = settings.finnhub_api_key
    if not api_key:
        return None

    # Finnhub uses standard tickers for US, but needs codes for others if not .NS/.BO
    symbol = ticker_symbol.split(".")[0] if exchange in ["NSE", "BSE"] else ticker_symbol
    if exchange == "NSE" and not symbol.endswith(".NS"): symbol = f"{symbol}.NS"
    elif exchange == "BSE" and not symbol.endswith(".BO"): symbol = f"{symbol}.BO"

    from_ts, to_ts = _period_to_timestamps(period)
    url = "https://finnhub.io/api/v1/stock/candle"
    params = {"symbol": symbol, "resolution": "D", "from": from_ts, "to": to_ts, "token": api_key}

    try:
        logger.info("Finnhub: fetching %s (period=%s)", symbol, period)
        resp = httpx.get(url, params=params, timeout=15)
        data = resp.json()

        if data.get("s") != "ok" or not data.get("c"):
            logger.warning("Finnhub: no data for %s (status=%s)", symbol, data.get("s"))
            return None

        df = pd.DataFrame({
            "Date": pd.to_datetime(data["t"], unit="s"),
            "Open": data["o"], "High": data["h"], "Low": data["l"], "Close": data["c"], "Volume": data["v"],
        })
        return df
    except Exception as exc:
        logger.warning("Finnhub: error for %s: %s", symbol, exc)
        return None


# ─── Source 3: Yahoo Finance v8 direct API ───────────────────────────────────
def _fetch_yahoo_v8(ticker_symbol: str, period: str) -> Optional[pd.DataFrame]:
    """Fetch OHLCV via Yahoo Finance v8 API directly (bypasses yfinance lib)."""
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
    try:
        with httpx.Client(headers=headers, follow_redirects=True, timeout=15) as client:
            from_ts, to_ts = _period_to_timestamps(period)
            url = f"https://query2.finance.yahoo.com/v8/finance/chart/{ticker_symbol}"
            # Using v8 chart API which is often more lenient than query1 v1 crumb API
            params = {"period1": from_ts, "period2": to_ts, "interval": "1d"}
            
            logger.info("Yahoo v8: fetching %s (period=%s)", ticker_symbol, period)
            resp = client.get(url, params=params)
            payload = resp.json()

            result = payload.get("chart", {}).get("result")
            if not result: return None
            
            chart = result[0]
            timestamps = chart.get("timestamp", [])
            quote = chart.get("indicators", {}).get("quote", [{}])[0]
            if not timestamps or not quote.get("close"): return None

            return pd.DataFrame({
                "Date": pd.to_datetime(timestamps, unit="s"),
                "Open": quote.get("open", []), "High": quote.get("high", []), "Low": quote.get("low", []),
                "Close": quote.get("close", []), "Volume": quote.get("volume", []),
            })
    except Exception as exc:
        logger.warning("Yahoo v8: error for %s: %s", ticker_symbol, exc)
        return None


# ─── Main entry point ────────────────────────────────────────────────────────
def fetch_ohlcv_data(
    ticker_symbol: str, exchange: str, period: Optional[str] = None,
    days: Optional[int] = None, interval: str = "1d", cache_manager: Optional[CacheManager] = None,
) -> pd.DataFrame:
    """Fetch OHLCV data with multi-source failover."""
    if not period:
        if days:
            if days <= 250: period = "1y"
            elif days <= 500: period = "2y"
            else: period = "5y"
        else:
            period = "2y"

    cache = cache_manager or CacheManager(cache_dir=settings.cache_dir)
    key = f"{ticker_symbol}_{exchange}"

    # 1. Cache
    cached = cache.get(key)
    if cached is not None and cached.data is not None and not cached.data.empty:
        try:
            return _normalize_ohlcv(cached.data, ticker=ticker_symbol)
        except Exception: pass

    # 2. Alpaca (US Primary)
    raw = _fetch_alpaca(ticker_symbol, exchange, period)
    if raw is not None and not raw.empty:
        clean = _normalize_ohlcv(raw, ticker=ticker_symbol)
        cache.set(key=key, data=clean, ttl_minutes=get_cache_ttl(exchange, datetime.now()))
        return clean

    # 3. Finnhub (Global Cloud Reliable)
    raw = _fetch_finnhub(ticker_symbol, exchange, period)
    if raw is not None and not raw.empty:
        clean = _normalize_ohlcv(raw, ticker=ticker_symbol)
        cache.set(key=key, data=clean, ttl_minutes=get_cache_ttl(exchange, datetime.now()))
        return clean

    # 4. Yahoo v8 (Direct API)
    raw = _fetch_yahoo_v8(ticker_symbol, period)
    if raw is not None and not raw.empty:
        clean = _normalize_ohlcv(raw, ticker=ticker_symbol)
        cache.set(key=key, data=clean, ttl_minutes=get_cache_ttl(exchange, datetime.now()))
        return clean

    # 5. yfinance lib (Last resort fallback)
    if yf is not None:
        try:
            ticker_obj = yf.Ticker(ticker_symbol, session=get_yf_session())
            raw = ticker_obj.history(period=period, interval=interval)
            if not raw.empty:
                clean = _normalize_ohlcv(raw, ticker=ticker_symbol)
                cache.set(key=key, data=clean, ttl_minutes=get_cache_ttl(exchange, datetime.now()))
                return clean
        except Exception: pass

    raise DataError(
        f"All data sources failed for '{ticker_symbol}'. Try again or check the ticker.",
        failed_step="FETCH_DATA"
    )

"""OHLCV data retrieval with multi-source fallback.

Source priority:
  1. Cache   – instant hit from local parquet store
  2. Finnhub – /stock/candle (works perfectly on cloud IPs)
  3. Yahoo Finance v8 direct API (cookie + crumb auth)
  4. yfinance library (fallback for local dev)
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


def _days_for_period(period: str) -> int:
    return _PERIOD_DAYS.get(period, 730)


# ─── Normalisation ───────────────────────────────────────────────────────────
def _normalize_ohlcv(df: pd.DataFrame, ticker: str = "Unknown") -> pd.DataFrame:
    """Normalise any OHLCV DataFrame into a clean Date|O|H|L|C|V format."""
    if df.empty:
        raise DataError(
            f"No OHLCV data returned for ticker '{ticker}'.",
            failed_step="FETCH_DATA",
        )

    clean = df.copy()

    # ── Handle MultiIndex columns (yfinance quirk) ──
    if isinstance(clean.columns, pd.MultiIndex):
        ohlcv_names = {"Open", "High", "Low", "Close", "Volume", "Adj Close"}
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

    # ── Ensure a "Date" column exists ──
    if "Date" not in clean.columns and not isinstance(clean.index, pd.RangeIndex):
        clean = clean.reset_index()

    for candidate in ("Date", "Datetime", "index", "date", "timestamp"):
        if candidate in clean.columns and "Date" not in clean.columns:
            clean = clean.rename(columns={candidate: "Date"})
            break

    # Stringified tuple fallback
    if "Date" not in clean.columns:
        for col in clean.columns:
            if "'Date'" in str(col):
                clean = clean.rename(columns={col: "Date"})
                break

    # Last resort – first column that parses as datetime
    if "Date" not in clean.columns:
        try:
            first = clean.columns[0]
            pd.to_datetime(clean[first].iloc[0])
            clean = clean.rename(columns={first: "Date"})
        except Exception:
            pass

    if "Date" not in clean.columns:
        raise DataError("Could not find Date column in OHLCV data.", failed_step="FETCH_DATA")

    clean["Date"] = pd.to_datetime(clean["Date"], utc=False).dt.tz_localize(None)

    # ── Ensure OHLCV columns exist ──
    required = ["Open", "High", "Low", "Close", "Volume"]
    for col in list(clean.columns):
        col_str = str(col)
        for req in required:
            if req not in clean.columns and f"'{req}'" in col_str:
                clean = clean.rename(columns={col: req})
                break

    missing = [c for c in required if c not in clean.columns]
    if missing:
        raise DataError(
            f"OHLCV missing columns: {', '.join(missing)} (got: {', '.join(map(str, clean.columns))})",
            failed_step="FETCH_DATA",
        )

    return clean[["Date", "Open", "High", "Low", "Close", "Volume"]].dropna().reset_index(drop=True)


# ─── Source 1: Finnhub ───────────────────────────────────────────────────────
def _finnhub_symbol(ticker_symbol: str, exchange: str) -> str:
    """Convert our internal symbol to Finnhub format.
       NSE: RELIANCE.NS  -> RELIANCE   (Finnhub uses plain for NSE via BSE exchange)
       NASDAQ: NVDA      -> NVDA       (no change)
    """
    base = ticker_symbol.split(".")[0]  # strip .NS / .BO
    return base


def _fetch_finnhub(ticker_symbol: str, exchange: str, period: str) -> Optional[pd.DataFrame]:
    """Fetch OHLCV via Finnhub /stock/candle endpoint."""
    api_key = settings.finnhub_api_key
    if not api_key:
        logger.info("Finnhub: no API key configured, skipping")
        return None

    symbol = _finnhub_symbol(ticker_symbol, exchange)
    from_ts, to_ts = _period_to_timestamps(period)

    url = "https://finnhub.io/api/v1/stock/candle"
    params = {
        "symbol": symbol,
        "resolution": "D",
        "from": from_ts,
        "to": to_ts,
        "token": api_key,
    }

    try:
        logger.info("Finnhub: fetching %s (period=%s)", symbol, period)
        resp = httpx.get(url, params=params, timeout=15)
        data = resp.json()

        if data.get("s") != "ok" or not data.get("c"):
            logger.warning("Finnhub: no data for %s (status=%s)", symbol, data.get("s"))
            return None

        df = pd.DataFrame({
            "Date": pd.to_datetime(data["t"], unit="s"),
            "Open": data["o"],
            "High": data["h"],
            "Low": data["l"],
            "Close": data["c"],
            "Volume": data["v"],
        })
        logger.info("Finnhub: got %d rows for %s", len(df), symbol)
        return df

    except Exception as exc:
        logger.warning("Finnhub: error for %s: %s", symbol, exc)
        return None


# ─── Source 2: Yahoo Finance v8 direct API ───────────────────────────────────
_YF_CRUMB_CACHE: dict = {}


def _get_yahoo_crumb(client: httpx.Client) -> Optional[str]:
    """Fetch a fresh Yahoo Finance crumb token."""
    if "crumb" in _YF_CRUMB_CACHE:
        age = time.time() - _YF_CRUMB_CACHE.get("ts", 0)
        if age < 3600:
            return _YF_CRUMB_CACHE["crumb"]

    try:
        # Visit consent page to get cookies
        client.get("https://fc.yahoo.com", follow_redirects=True)
        resp = client.get("https://query2.finance.yahoo.com/v1/test/getcrumb")
        if resp.status_code == 200 and resp.text and "<!DOCTYPE" not in resp.text:
            crumb = resp.text.strip()
            _YF_CRUMB_CACHE["crumb"] = crumb
            _YF_CRUMB_CACHE["ts"] = time.time()
            return crumb
    except Exception as exc:
        logger.debug("Yahoo crumb fetch failed: %s", exc)
    return None


def _fetch_yahoo_v8(ticker_symbol: str, period: str) -> Optional[pd.DataFrame]:
    """Fetch OHLCV via Yahoo Finance v8 API directly (bypasses yfinance lib)."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    try:
        with httpx.Client(headers=headers, follow_redirects=True, timeout=15) as client:
            crumb = _get_yahoo_crumb(client)
            if not crumb:
                logger.info("Yahoo v8: could not obtain crumb, skipping")
                return None

            from_ts, to_ts = _period_to_timestamps(period)
            url = f"https://query2.finance.yahoo.com/v8/finance/chart/{ticker_symbol}"
            params = {
                "period1": from_ts,
                "period2": to_ts,
                "interval": "1d",
                "includePrePost": "false",
                "crumb": crumb,
            }

            logger.info("Yahoo v8: fetching %s (period=%s)", ticker_symbol, period)
            resp = client.get(url, params=params)
            payload = resp.json()

            result = payload.get("chart", {}).get("result")
            if not result:
                logger.warning("Yahoo v8: no result for %s", ticker_symbol)
                return None

            chart = result[0]
            timestamps = chart.get("timestamp", [])
            quote = chart.get("indicators", {}).get("quote", [{}])[0]

            if not timestamps or not quote.get("close"):
                logger.warning("Yahoo v8: empty data for %s", ticker_symbol)
                return None

            df = pd.DataFrame({
                "Date": pd.to_datetime(timestamps, unit="s"),
                "Open": quote.get("open", []),
                "High": quote.get("high", []),
                "Low": quote.get("low", []),
                "Close": quote.get("close", []),
                "Volume": quote.get("volume", []),
            })
            logger.info("Yahoo v8: got %d rows for %s", len(df), ticker_symbol)
            return df

    except Exception as exc:
        logger.warning("Yahoo v8: error for %s: %s", ticker_symbol, exc)
        return None


from tools.yf_helper import get_yf_session

# ─── Source 3: yfinance library ──────────────────────────────────────────────
def _fetch_yfinance(ticker_symbol: str, period: str, interval: str) -> Optional[pd.DataFrame]:
    """Fetch via yfinance library – works locally, often blocked on cloud."""
    if yf is None:
        return None

    try:
        logger.info("yfinance lib: fetching %s (period=%s)", ticker_symbol, period)
        session = get_yf_session()
        ticker_obj = yf.Ticker(ticker_symbol, session=session)
        raw = ticker_obj.history(period=period, interval=interval)
        if raw.empty:
            logger.warning("yfinance lib: empty response for %s", ticker_symbol)
            return None
        return raw
    except Exception as exc:
        logger.warning("yfinance lib: error for %s: %s", ticker_symbol, exc)
        return None


# ─── Main entry point ────────────────────────────────────────────────────────
def fetch_ohlcv_data(
    ticker_symbol: str,
    exchange: str,
    period: Optional[str] = None,
    days: Optional[int] = None,
    interval: str = "1d",
    cache_manager: Optional[CacheManager] = None,
) -> pd.DataFrame:
    """
    Fetch OHLCV data with multi-source failover.

    Priority: Cache → Finnhub → Yahoo v8 → yfinance library.
    """
    if not period:
        if days:
            if days <= 250:   period = "1y"
            elif days <= 500:  period = "2y"
            elif days <= 1250: period = "5y"
            elif days <= 2500: period = "10y"
            else:              period = "max"
        else:
            period = "2y"

    cache = cache_manager or CacheManager(cache_dir=settings.cache_dir)
    key = f"{ticker_symbol}_{exchange}"

    logger.info("OHLCV request: %s on %s (period=%s)", ticker_symbol, exchange, period)

    # ── 1. Cache ──
    cached = cache.get(key)
    if cached is not None and cached.data is not None and not cached.data.empty:
        try:
            logger.info("Cache HIT for %s", key)
            return _normalize_ohlcv(cached.data, ticker=ticker_symbol)
        except Exception:
            logger.warning("Cache data corrupted for %s, re-fetching", key)

    # ── 2. Finnhub API ──
    raw = _fetch_finnhub(ticker_symbol, exchange, period)
    if raw is not None and not raw.empty:
        clean = _normalize_ohlcv(raw, ticker=ticker_symbol)
        ttl = get_cache_ttl(exchange, datetime.now())
        cache.set(key=key, data=clean, ttl_minutes=ttl)
        return clean

    # ── 3. Yahoo Finance v8 direct API ──
    raw = _fetch_yahoo_v8(ticker_symbol, period)
    if raw is not None and not raw.empty:
        clean = _normalize_ohlcv(raw, ticker=ticker_symbol)
        ttl = get_cache_ttl(exchange, datetime.now())
        cache.set(key=key, data=clean, ttl_minutes=ttl)
        return clean

    # ── 4. yfinance library (last resort) ──
    raw = _fetch_yfinance(ticker_symbol, period, interval)
    if raw is not None and not raw.empty:
        clean = _normalize_ohlcv(raw, ticker=ticker_symbol)
        ttl = get_cache_ttl(exchange, datetime.now())
        cache.set(key=key, data=clean, ttl_minutes=ttl)
        return clean

    raise DataError(
        f"All data sources failed for '{ticker_symbol}'. "
        f"Tried: Finnhub API, Yahoo Finance v8, yfinance library. "
        f"Please verify the ticker symbol is valid.",
        failed_step="FETCH_DATA",
    )

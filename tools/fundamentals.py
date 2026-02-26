"""Fundamentals and financials data fetching with multi-source fallback.

Source priority:
  1. Local Memory Cache (24h TTL)
  2. Finnhub API (Primary for cloud IPs)
  3. Yahoo Finance v8 quoteSummary (Direct API)
  4. yfinance library (Last resort)
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import httpx
import yfinance as yf

from config.settings import settings
from tools.error_handler import safe_float

logger = logging.getLogger(__name__)

# Simple TTL cache implementation
_cache: Dict[str, tuple[Any, datetime]] = {}
_CACHE_TTL_HOURS = 24


def _get_cached(key: str) -> Any:
    """Get cached value if not expired."""
    if key in _cache:
        value, timestamp = _cache[key]
        if datetime.now() - timestamp < timedelta(hours=_CACHE_TTL_HOURS):
            return value
    return None


def _set_cached(key: str, value: Any) -> None:
    """Set cached value with current timestamp."""
    _cache[key] = (value, datetime.now())


def _get_finnhub_fundamentals(symbol: str) -> Optional[Dict[str, Any]]:
    """Fetch basics from Finnhub."""
    api_key = settings.finnhub_api_key
    if not api_key:
        return None

    try:
        # Profile 2 for name, sector, industry
        profile_url = f"https://finnhub.io/api/v1/stock/profile2?symbol={symbol}&token={api_key}"
        # Basic financials for cap, pe, etc.
        metric_url = f"https://finnhub.io/api/v1/stock/metric?symbol={symbol}&metric=all&token={api_key}"
        
        with httpx.Client(timeout=10) as client:
            p_resp = client.get(profile_url)
            m_resp = client.get(metric_url)
            
            p_data = p_resp.json() if p_resp.status_code == 200 else {}
            m_data = m_resp.json().get("metric", {}) if m_resp.status_code == 200 else {}
            
            if not p_data and not m_data:
                return None
                
            return {
                "name": p_data.get("name", "N/A"),
                "sector": p_data.get("finnhubIndustry", "N/A"),
                "industry": p_data.get("finnhubIndustry", "N/A"),
                "market_cap": safe_float(m_data.get("marketCapitalization", 0)) * 1000000,
                "pe_ratio": safe_float(m_data.get("peExclExtraTTM", 0.0)),
                "forward_pe": safe_float(m_data.get("peNormalizedAnnual", 0.0)),
                "dividend_yield": safe_float(m_data.get("dividendYieldIndicatedAnnual", 0.0)),
                "beta": safe_float(m_data.get("beta", 0.0)),
                "fifty_two_week_high": safe_float(m_data.get("52WeekHigh", 0.0)),
                "fifty_two_week_low": safe_float(m_data.get("52WeekLow", 0.0)),
                "summary": "Business dynamics captured via Finnhub telemetry."
            }
    except Exception as e:
        logger.warning("Finnhub fundamentals error for %s: %s", symbol, e)
        return None


def _get_yahoo_direct_fundamentals(symbol: str) -> Optional[Dict[str, Any]]:
    """Fetch basics from Yahoo Finance v7 Quote API (more resilient than info scraper)."""
    try:
        url = f"https://query2.finance.yahoo.com/v7/finance/quote?symbols={symbol}"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"}
        with httpx.Client(timeout=10) as client:
            resp = client.get(url, headers=headers)
            if resp.status_code == 200:
                result = resp.json().get("quoteResponse", {}).get("result", [None])[0]
                if result:
                    return {
                        "name": result.get("longName") or result.get("shortName") or "N/A",
                        "sector": "N/A", # Not in quote API
                        "industry": "N/A",
                        "market_cap": safe_float(result.get("marketCap", 0)),
                        "pe_ratio": safe_float(result.get("trailingPE", 0.0)),
                        "forward_pe": safe_float(result.get("forwardPE", 0.0)),
                        "dividend_yield": safe_float(result.get("dividendYield", 0.0)) / 100, # convert pct
                        "beta": safe_float(result.get("beta", 0.0)),
                        "fifty_two_week_high": safe_float(result.get("fiftyTwoWeekHigh", 0.0)),
                        "fifty_two_week_low": safe_float(result.get("fiftyTwoWeekLow", 0.0)),
                        "summary": f"Market Data for {symbol} captured via Yahoo Direct API."
                    }
    except Exception as e:
        logger.debug("Yahoo Direct fundamentals error: %s", e)
    return None


from tools.yf_helper import get_yf_session

def get_fundamentals(ticker: str, exchange: str = "NSE") -> Dict[str, Any]:
    """Fetch company fundamentals with multi-source failover."""
    cache_key = f"fundamentals_{ticker}_{exchange}"
    cached = _get_cached(cache_key)
    if cached is not None:
        return cached

    from tools.symbol_utils import resolve_finnhub_symbol
    symbol = resolve_finnhub_symbol(ticker, exchange)
    
    # 1. Try Finnhub (Best for Cloud)
    result = _get_finnhub_fundamentals(symbol)
    if result:
        logger.info("Fundamentals: Finnhub HIT for %s", symbol)
        _set_cached(cache_key, result)
        return result

    # 2. Try Yahoo Direct (Resilient fallback)
    result = _get_yahoo_direct_fundamentals(symbol)
    if result:
        logger.info("Fundamentals: Yahoo Direct HIT for %s", symbol)
        _set_cached(cache_key, result)
        return result

    # 3. Try yfinance (Last resort - likely to fail on cloud)
    try:
        logger.info("Fundamentals: yfinance last resort for %s", symbol)
        # Let yfinance handle its own session management
        stock = yf.Ticker(symbol)
        info = stock.info
        if info and ("longName" in info or "shortName" in info):
            result = {
                "name": info.get("longName", info.get("shortName", "N/A")),
                "sector": info.get("sector", "N/A"),
                "industry": info.get("industry", "N/A"),
                "market_cap": safe_float(info.get("marketCap", 0)),
                "pe_ratio": safe_float(info.get("trailingPE", 0.0)),
                "forward_pe": safe_float(info.get("forwardPE", 0.0)),
                "dividend_yield": safe_float(info.get("dividendYield", 0.0)),
                "beta": safe_float(info.get("beta", 0.0)),
                "fifty_two_week_high": safe_float(info.get("fiftyTwoWeekHigh", 0.0)),
                "fifty_two_week_low": safe_float(info.get("fiftyTwoWeekLow", 0.0)),
                "summary": info.get("longBusinessSummary", "No summary available.")[:1000]
            }
            _set_cached(cache_key, result)
            return result
    except Exception as e:
        logger.warning("yfinance info error for %s: %s", symbol, e)

    return {}


def get_financials_table(ticker: str, exchange: str = "NSE") -> List[Dict[str, Any]]:
    """Fetch annual financials table data."""
    cache_key = f"financials_{ticker}_{exchange}"
    cached = _get_cached(cache_key)
    if cached is not None:
        return cached

    # For financials, yfinance .financials is still the most comprehensive free source.
    # We will try it, but handle failure.
    from tools.symbol_utils import resolve_finnhub_symbol
    symbol = resolve_finnhub_symbol(ticker, exchange)

    try:
        logger.info("Financials Table: fetching for %s", symbol)
        # Let yfinance handle its own session management
        stock = yf.Ticker(symbol)
        df = stock.financials
        if df is not None and not df.empty:
            table = []
            df_t = df.T
            mapping = {
                "Total Revenue": "revenue",
                "Net Income": "net_income",
                "EBIT": "ebit",
            }
            for index, row in df_t.head(5).iterrows():
                year = str(index.year) if hasattr(index, "year") else str(index)
                data = {"year": year}
                for yf_key, my_key in mapping.items():
                    if yf_key in row:
                        data[my_key] = safe_float(row[yf_key])
                data["growth_notes"] = "Market telemetry data captured"
                table.append(data)
            
            result = sorted(table, key=lambda x: x["year"])
            _set_cached(cache_key, result)
            return result
    except Exception as e:
        logger.warning("Financials table fetch error for %s: %s", symbol, e)
    
    return []

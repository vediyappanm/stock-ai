"""Fundamentals and financials data fetching with TTL caching."""

import yfinance as yf
from typing import Dict, Any, List
from functools import lru_cache
from datetime import datetime, timedelta
from schemas.response_schemas import FundamentalsResult
from tools.error_handler import safe_float

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


def get_fundamentals(ticker: str, exchange: str = "NSE") -> Dict[str, Any]:
    """Fetch company fundamentals using yfinance with 24-hour TTL cache."""
    cache_key = f"fundamentals_{ticker}_{exchange}"
    
    # Check cache first
    cached = _get_cached(cache_key)
    if cached is not None:
        return cached
    
    from tools.symbol_utils import resolve_finnhub_symbol
    symbol = resolve_finnhub_symbol(ticker, exchange)
        
    import httpx
    from config.settings import settings
    
    try:
        stock = yf.Ticker(symbol)
        info = stock.info
        
        # Base result from yfinance
        result = {
            "name": info.get("longName", "N/A"),
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
        
        # Augment with Finnhub if key is available
        if settings.finnhub_api_key:
            try:
                # Finnhub basic financial metrics
                url = f"https://finnhub.io/api/v1/stock/metric?symbol={symbol}&metric=all&token={settings.finnhub_api_key}"
                resp = httpx.get(url, timeout=5)
                if resp.status_code == 200:
                    fm = resp.json().get("metric", {})
                    # Prioritize Finnhub for certain metrics if available
                    if fm.get("marketCapitalization"):
                        result["market_cap"] = safe_float(fm["marketCapitalization"] * 1000000) # Finnhub reports in millions
                    if fm.get("peExclExtraTTM"):
                         result["pe_ratio"] = safe_float(fm["peExclExtraTTM"])
                    if fm.get("beta"):
                         result["beta"] = safe_float(fm["beta"])
                    if fm.get("52WeekHigh"):
                         result["fifty_two_week_high"] = safe_float(fm["52WeekHigh"])
                    if fm.get("52WeekLow"):
                         result["fifty_two_week_low"] = safe_float(fm["52WeekLow"])
            except Exception as fe:
                print(f"Finnhub metrics fetch error for {symbol}: {fe}")
        
        # Cache the result
        _set_cached(cache_key, result)
        return result
    except Exception as e:
        print(f"Error fetching fundamentals for {symbol}: {e}")
        return {}


def get_financials_table(ticker: str, exchange: str = "NSE") -> List[Dict[str, Any]]:
    """Fetch annual financials table data with 24-hour TTL cache."""
    cache_key = f"financials_{ticker}_{exchange}"
    
    # Check cache first
    cached = _get_cached(cache_key)
    if cached is not None:
        return cached
    
    symbol = ticker
    if exchange == "NSE" and not ticker.endswith(".NS"):
        symbol = f"{ticker}.NS"
    elif exchange == "BSE" and not ticker.endswith(".BO"):
        symbol = f"{ticker}.BO"

    try:
        stock = yf.Ticker(symbol)
        # Fetch annual financials
        df = stock.financials
        if df is None or df.empty:
            return []
            
        table = []
        # Standardize columns (transpose for year rows)
        df_t = df.T
        
        # Mapping for common fields
        mapping = {
            "Total Revenue": "revenue",
            "Net Income": "net_income",
            "EBIT": "ebit",
            "Operating Income": "ebit" # Fallback
        }
        
        for index, row in df_t.head(5).iterrows():
            year = str(index.year) if hasattr(index, "year") else str(index)
            data = {"year": year}
            for yf_key, my_key in mapping.items():
                if yf_key in row:
                    data[my_key] = safe_float(row[yf_key])
                elif my_key not in data:
                    data[my_key] = 0.0
            
            # Simple growth note logic
            data["growth_notes"] = "Data pulse captured"
            table.append(data)
        
        result = sorted(table, key=lambda x: x["year"])
        
        # Cache the result
        _set_cached(cache_key, result)
        return result
    except Exception as e:
        print(f"Error fetching financials table for {symbol}: {e}")
        return []

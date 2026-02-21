"""Ticker symbol resolution and exchange suffix handling.

On cloud deployments (Render/Railway), yfinance validation is unreliable because
Yahoo Finance blocks cloud IPs. This module uses a deterministic alias + 
Finnhub-based validation strategy that works everywhere.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import httpx

from config.settings import settings
from schemas.response_schemas import ResolvedTicker
from tools.error_handler import DataError, ValidationError

logger = logging.getLogger(__name__)

# ─── Known ticker aliases (typos, company names → canonical tickers) ─────────
_COMMON_ALIASES: Dict[str, str] = {
    # Indian blue-chips
    "RELIANCE": "RELIANCE",
    "TCS": "TCS",
    "INFOSYS": "INFY",
    "INFY": "INFY",
    "HDFCBANK": "HDFCBANK",
    "WIPRO": "WIPRO",
    "SBIN": "SBIN",
    "ICICIBANK": "ICICIBANK",
    "BHARTIARTL": "BHARTIARTL",
    "ITC": "ITC",
    "HINDUNILVR": "HINDUNILVR",
    "KOTAKBANK": "KOTAKBANK",
    "LT": "LT",
    "AXISBANK": "AXISBANK",
    "BAJFINANCE": "BAJFINANCE",
    "MARUTI": "MARUTI",
    "TATAMOTORS": "TATAMOTORS",
    "SUNPHARMA": "SUNPHARMA",
    "TITAN": "TITAN",
    "ASIANPAINT": "ASIANPAINT",
    "HCLTECH": "HCLTECH",
    "ADANIENT": "ADANIENT",
    "ADANIPORTS": "ADANIPORTS",
    "POWERGRID": "POWERGRID",
    "NTPC": "NTPC",
    "TATASTEEL": "TATASTEEL",
    # US mega-caps
    "APPLE": "AAPL",
    "AAPL": "AAPL",
    "TESLA": "TSLA",
    "TSLA": "TSLA",
    "MICROSOFT": "MSFT",
    "MSFT": "MSFT",
    "GOOGLE": "GOOGL",
    "ALPHABET": "GOOGL",
    "GOOGL": "GOOGL",
    "AMAZON": "AMZN",
    "AMZN": "AMZN",
    "NVIDIA": "NVDA",
    "NVDIA": "NVDA",  # Common typos
    "NVDA": "NVDA",
    "META": "META",
    "FACEBOOK": "META",
    "NETFLIX": "NFLX",
    "NFLX": "NFLX",
    "AMD": "AMD",
    "INTEL": "INTC",
    "INTC": "INTC",
    "DISNEY": "DIS",
    "DIS": "DIS",
    "JPMORGAN": "JPM",
    "JPM": "JPM",
    "BERKSHIRE": "BRK-B",
    "VISA": "V",
    "MASTERCARD": "MA",
    "PAYPAL": "PYPL",
    "UBER": "UBER",
    "AIRBNB": "ABNB",
    "COINBASE": "COIN",
    "SPOTIFY": "SPOT",
    "SNOWFLAKE": "SNOW",
    "PALANTIR": "PLTR",
    # Crypto
    "BITCOIN": "BTC-USD",
    "BTC": "BTC-USD",
    "ETHEREUM": "ETH-USD",
    "ETH": "ETH-USD",
}

# Tickers that are KNOWN to trade on specific US exchanges
_US_TICKERS: set = {
    "AAPL", "TSLA", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "NFLX",
    "AMD", "INTC", "DIS", "JPM", "V", "MA", "PYPL", "UBER", "ABNB",
    "COIN", "SPOT", "SNOW", "PLTR", "BRK-B",
}

_PREFERRED_EXCHANGE: Dict[str, str] = {
    "AAPL": "NASDAQ", "TSLA": "NASDAQ", "MSFT": "NASDAQ", "GOOGL": "NASDAQ",
    "AMZN": "NASDAQ", "NVDA": "NASDAQ", "META": "NASDAQ", "NFLX": "NASDAQ",
    "AMD": "NASDAQ", "INTC": "NASDAQ", "PYPL": "NASDAQ", "UBER": "NYSE",
    "ABNB": "NASDAQ", "COIN": "NASDAQ", "SPOT": "NYSE", "SNOW": "NYSE",
    "PLTR": "NYSE", "DIS": "NYSE", "JPM": "NYSE", "V": "NYSE", "MA": "NYSE",
    "BRK-B": "NYSE",
}


@dataclass(frozen=True)
class _Resolved:
    base_ticker: str
    exchange: str


def _normalize_exchange(exchange: str | None) -> str:
    resolved = (exchange or settings.default_exchange).strip().upper()
    if resolved not in settings.supported_exchanges:
        supported = ", ".join(settings.supported_exchanges)
        raise ValidationError(
            f"Unsupported exchange '{resolved}'. Supported: {supported}",
            failed_step="RESOLVE_TICKER",
        )
    return resolved


def _normalize_stock(stock: str) -> str:
    cleaned = stock.strip()
    if not cleaned:
        raise ValidationError("Stock/ticker cannot be empty", failed_step="RESOLVE_TICKER")
    return cleaned.upper().replace(" ", "")


def apply_exchange_suffix(ticker: str, exchange: str) -> str:
    """Apply exchange suffix according to configured mapping."""
    suffix = settings.exchange_suffixes.get(exchange, "")
    if suffix and not ticker.endswith(suffix):
        return f"{ticker}{suffix}"
    return ticker


def _validate_via_finnhub(symbol: str) -> bool:
    """Quick validation using Finnhub quote endpoint (works on cloud IPs)."""
    api_key = settings.finnhub_api_key
    if not api_key:
        return False  # Can't validate without key

    try:
        resp = httpx.get(
            "https://finnhub.io/api/v1/quote",
            params={"symbol": symbol, "token": api_key},
            timeout=5,
        )
        if resp.status_code == 200:
            data = resp.json()
            # A valid ticker has a current price > 0
            return data.get("c", 0) > 0
    except Exception:
        pass
    return False


def _resolve_deterministic(stock: str, requested_exchange: str) -> ResolvedTicker:
    """
    Deterministic resolution using alias tables — no API calls needed.
    
    This is the FAST PATH that handles 99% of real-world queries.
    """
    normalized = _normalize_stock(stock)

    # Step 1: Check alias table
    canonical = _COMMON_ALIASES.get(normalized, normalized)

    # Step 2: Determine correct exchange
    if canonical in _US_TICKERS:
        # This is a US stock — override Indian exchange if user sent NSE/BSE
        exchange = _PREFERRED_EXCHANGE.get(canonical, "NASDAQ")
        logger.info("Deterministic: %s -> %s on %s (US stock detected)", stock, canonical, exchange)
    elif canonical.endswith("-USD"):
        # Crypto — no exchange suffix needed
        exchange = requested_exchange
        logger.info("Deterministic: %s -> %s (crypto)", stock, canonical)
        return ResolvedTicker(ticker=canonical, exchange=exchange, full_symbol=canonical)
    else:
        # Assume Indian stock if requested exchange is NSE/BSE
        exchange = requested_exchange
        logger.info("Deterministic: %s -> %s on %s", stock, canonical, exchange)

    full_symbol = apply_exchange_suffix(canonical, exchange)
    return ResolvedTicker(ticker=canonical, exchange=exchange, full_symbol=full_symbol)


def resolve_ticker(stock: str, exchange: str | None = None) -> ResolvedTicker:
    """
    Resolve stock/company input into an exchange-qualified ticker symbol.
    
    Strategy (permanent, cloud-safe):
    1. Deterministic alias resolution (instant, offline)
    2. Finnhub API validation (optional, cloud-friendly)
    3. Direct passthrough with suffix (last resort)
    """
    requested_exchange = _normalize_exchange(exchange)
    logger.info("Resolving: stock='%s', exchange='%s'", stock, requested_exchange)

    # ── Fast path: deterministic resolution ──
    result = _resolve_deterministic(stock, requested_exchange)

    # ── Optional: validate with Finnhub if key is available ──
    # Only validate non-Indian tickers (Finnhub free tier doesn't cover NSE well)
    if result.exchange in {"NYSE", "NASDAQ"} and settings.finnhub_api_key:
        plain_symbol = result.ticker  # Finnhub uses plain symbols for US stocks
        if _validate_via_finnhub(plain_symbol):
            logger.info("Finnhub validated: %s ✓", plain_symbol)
        else:
            logger.warning("Finnhub could not validate %s (may be rate-limited)", plain_symbol)
            # Don't fail — trust the alias table

    logger.info("Resolved: %s -> %s (%s)", stock, result.full_symbol, result.exchange)
    return result


def _suggestions(stock: str, exchange: str) -> List[str]:
    normalized = _normalize_stock(stock)
    suggestions: List[str] = []
    for key, value in _COMMON_ALIASES.items():
        if normalized in key or key.startswith(normalized[:2]):
            suggestions.append(apply_exchange_suffix(value, exchange))
    return list(dict.fromkeys(suggestions))[:3]

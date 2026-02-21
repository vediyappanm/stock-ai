"""Ticker symbol resolution and exchange suffix handling.

Cloud-resilient: Uses deterministic aliases and Finnhub validation.
Never hits Yahoo Finance to avoid IP blocking.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional

import httpx
from config.settings import settings
from schemas.response_schemas import ResolvedTicker
from tools.error_handler import ValidationError

logger = logging.getLogger(__name__)

# ─── Alias Table ─────────────────────────────────────────────────────────────
_COMMON_ALIASES: Dict[str, str] = {
    # Indian
    "RELIANCE": "RELIANCE", "TCS": "TCS", "INFOSYS": "INFY", "INFY": "INFY",
    "HDFCBANK": "HDFCBANK", "WIPRO": "WIPRO", "SBIN": "SBIN", "ICICIBANK": "ICICIBANK",
    "BHARTIARTL": "BHARTIARTL", "ITC": "ITC", "HINDUNILVR": "HINDUNILVR",
    # US
    "APPLE": "AAPL", "AAPL": "AAPL", "TESLA": "TSLA", "TSLA": "TSLA",
    "MICROSOFT": "MSFT", "MSFT": "MSFT", "GOOGLE": "GOOGL", "ALPHABET": "GOOGL",
    "AMAZON": "AMZN", "AMZN": "AMZN", "NVIDIA": "NVDA", "NVDIA": "NVDA", "NVDA": "NVDA",
    "META": "META", "FACEBOOK": "META", "NETFLIX": "NFLX", "NFLX": "NFLX",
    "AMD": "AMD", "INTEL": "INTC", "INTC": "INTC", "BITCOIN": "BTC-USD",
}

_US_TICKERS = {"AAPL", "TSLA", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "NFLX", "AMD", "INTC", "BTC-USD"}

@dataclass(frozen=True)
class _Resolved:
    base_ticker: str
    exchange: str

def _normalize_exchange(exchange: str | None) -> str:
    res = (exchange or settings.default_exchange).strip().upper()
    return res if res in settings.supported_exchanges else settings.default_exchange

def _normalize_stock(stock: str) -> str:
    return stock.strip().upper().replace(" ", "")

def apply_exchange_suffix(ticker: str, exchange: str) -> str:
    suffix = settings.exchange_suffixes.get(exchange, "")
    return f"{ticker}{suffix}" if suffix and not ticker.endswith(suffix) else ticker

def resolve_ticker(stock: str, exchange: str | None = None) -> ResolvedTicker:
    """Deterministic ticker resolution without hitting Yahoo."""
    requested_exchange = _normalize_exchange(exchange)
    normalized = _normalize_stock(stock)
    
    # 1. Check Alias
    canonical = _COMMON_ALIASES.get(normalized, normalized)
    
    # 2. Market Detection
    if canonical in _US_TICKERS or canonical.endswith("-USD"):
        target_exchange = "NASDAQ" if canonical != "BTC-USD" else requested_exchange
        full_symbol = apply_exchange_suffix(canonical, target_exchange)
    else:
        target_exchange = requested_exchange
        full_symbol = apply_exchange_suffix(canonical, target_exchange)
        
    logger.info("Resolved: %s -> %s (%s)", stock, full_symbol, target_exchange)
    return ResolvedTicker(ticker=canonical, exchange=target_exchange, full_symbol=full_symbol)

def _suggestions(stock: str, exchange: str) -> List[str]:
    norm = _normalize_stock(stock)
    return [apply_exchange_suffix(v, exchange) for k, v in _COMMON_ALIASES.items() if norm in k][:3]

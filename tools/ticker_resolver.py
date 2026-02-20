"""Ticker symbol resolution and exchange suffix handling."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

try:
    import yfinance as yf
    import logging
    # Silence yfinance ubiquitous delisted warnings
    logging.getLogger("yfinance").setLevel(logging.CRITICAL)
except Exception:  # pragma: no cover - optional dependency fallback
    yf = None

from config.settings import settings
from schemas.response_schemas import ResolvedTicker
from tools.error_handler import DataError, ValidationError


_COMMON_ALIASES: Dict[str, str] = {
    "RELIANCE": "RELIANCE",
    "TCS": "TCS",
    "INFOSYS": "INFY",
    "HDFCBANK": "HDFCBANK",
    "APPLE": "AAPL",
    "TESLA": "TSLA",
    "MICROSOFT": "MSFT",
    "GOOGLE": "GOOGL",
    "ALPHABET": "GOOGL",
    "AMAZON": "AMZN",
    "NVIDIA": "NVDA",
    "NVDIA": "NVDA",
    "META": "META",
}

_PREFERRED_EXCHANGE_BY_TICKER: Dict[str, str] = {
    "AAPL": "NASDAQ",
    "AMZN": "NASDAQ",
    "GOOGL": "NASDAQ",
    "META": "NASDAQ",
    "MSFT": "NASDAQ",
    "NVDA": "NASDAQ",
    "TSLA": "NASDAQ",
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


def _build_candidates(stock: str, exchange: str) -> List[_Resolved]:
    base = _normalize_stock(stock)

    candidates: List[_Resolved] = []
    alias = _COMMON_ALIASES.get(base, base)
    candidates.append(_Resolved(alias, exchange))

    # If stock already includes known suffix, keep it and infer base.
    if "." in base:
        ticker_part = base.split(".", 1)[0]
        candidates.append(_Resolved(ticker_part, exchange))

    # Also try direct symbol for US exchanges.
    if exchange in {"NYSE", "NASDAQ"} and alias != base:
        candidates.append(_Resolved(base, exchange))

    # De-duplicate while preserving order.
    seen: set[Tuple[str, str]] = set()
    unique: List[_Resolved] = []
    for item in candidates:
        key = (item.base_ticker, item.exchange)
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique


def _ticker_exists(symbol: str) -> bool:
    if yf is None:
        # Offline fallback: accept plausible symbol shape.
        return bool(symbol and symbol[0].isalnum())
    
    try:
        # Use a custom session to avoid being blocked on common cloud IPs (Render/GCP)
        import requests
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36'
        })
        
        ticker = yf.Ticker(symbol, session=session)
        # Search for a slightly longer window to confirm it's actually trading/active
        hist = ticker.history(period="1mo", interval="1d")
        
        # Stricter check: Valid tickers should have multiple days of data
        if len(hist) < 3:
            return False
            
        # Ensure it has basic OHLCV columns and non-NaN values
        required = {"Open", "High", "Low", "Close"}
        if not required.issubset(hist.columns):
            return False
            
        return not hist["Close"].dropna().empty
        
    except Exception:
        return False


def _suggestions(stock: str, exchange: str) -> List[str]:
    normalized = _normalize_stock(stock)
    suggestions: List[str] = []
    for key, value in _COMMON_ALIASES.items():
        if normalized in key or key.startswith(normalized[:2]):
            suggestions.append(apply_exchange_suffix(value, exchange))
    # De-duplicate while preserving order.
    deduped = list(dict.fromkeys(suggestions))
    return deduped[:3]


def resolve_ticker(stock: str, exchange: str | None = None) -> ResolvedTicker:
    """
    Resolve stock/company input into an exchange-qualified ticker symbol.
    
    Implements a multi-exchange fallback strategy:
    1. Try the requested/default exchange.
    2. If failed, sweep through other supported exchanges.
    """
    primary_exchange = _normalize_exchange(exchange)
    
    # Order: Primary first, then others
    other_exchanges = [ex for ex in settings.supported_exchanges if ex != primary_exchange]
    search_order = [primary_exchange] + other_exchanges

    for current_exchange in search_order:
        candidates = _build_candidates(stock, current_exchange)
        for candidate in candidates:
            full_symbol = apply_exchange_suffix(candidate.base_ticker, candidate.exchange)
            if _ticker_exists(full_symbol):
                return ResolvedTicker(
                    ticker=candidate.base_ticker,
                    exchange=candidate.exchange,
                    full_symbol=full_symbol,
                )

    # Best-effort fallback for known aliases/typos when provider validation is unavailable.
    normalized = _normalize_stock(stock)
    aliased = _COMMON_ALIASES.get(normalized)
    if aliased:
        preferred_exchange = _PREFERRED_EXCHANGE_BY_TICKER.get(aliased, primary_exchange)
        # If the requested exchange is NSE/BSE but the stock is clearly US-based (or vice versa), 
        # and we couldn't verify the requested one, use the preferred one.
        if primary_exchange in {"NSE", "BSE"} and preferred_exchange in {"NYSE", "NASDAQ"}:
            target_exchange = preferred_exchange
        elif primary_exchange in {"NYSE", "NASDAQ"} and preferred_exchange in {"NSE", "BSE"}:
            target_exchange = preferred_exchange
        else:
            target_exchange = primary_exchange
            
        return ResolvedTicker(
            ticker=aliased,
            exchange=target_exchange,
            full_symbol=apply_exchange_suffix(aliased, target_exchange),
        )

    hints = _suggestions(stock, primary_exchange)
    hint_text = f" Suggestions: {', '.join(hints)}." if hints else ""
    raise DataError(
        f"Could not resolve ticker '{stock}' on any supported exchange (checked: {', '.join(search_order)}).{hint_text}",
        failed_step="RESOLVE_TICKER",
    )

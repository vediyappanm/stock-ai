
"""Utility for global symbol resolution and currency mapping."""
from typing import Dict, Tuple

def resolve_finnhub_symbol(ticker: str, exchange: str = "NSE") -> str:
    """Resolve symbol into a Finnhub-compatible format."""
    if "." in ticker:
        return ticker # Already has suffix
        
    exchange = exchange.upper()
    if exchange == "NSE":
        return f"{ticker}.NS"
    if exchange == "BSE":
        return f"{ticker}.BO"
    # NYSE/NASDAQ usually don't need suffix in Finnhub
    return ticker

def get_currency_symbol(exchange: str) -> str:
    """Get currency symbol based on exchange."""
    exchange = exchange.upper()
    if exchange in ["NSE", "BSE"]:
        return "₹"
    return "$"

def get_market_label(exchange: str) -> str:
    """Get market label for display."""
    exchange = exchange.upper()
    if exchange in ["NSE", "BSE"]:
        return "Indian"
    return "Global"

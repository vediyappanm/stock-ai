"""
Ticker validation and suggestion system to prevent typos and improve UX.
"""
import logging
from typing import Optional, List, Dict
from difflib import get_close_matches

logger = logging.getLogger(__name__)

# Common ticker corrections
TICKER_CORRECTIONS = {
    "NVDIA": "NVDA",
    "GOOGL": "GOOGL",  # Keep as is
    "GOOG": "GOOGL",   # Suggest Class A
    "TSLA": "TSLA",    # Keep as is
    "TESLA": "TSLA",
    "APPLE": "AAPL",
    "MICROSOFT": "MSFT",
    "AMAZON": "AMZN",
    "META": "META",
    "FACEBOOK": "META",
    "RELIANCE": "RELIANCE",
    "TCS": "TCS",
    "INFY": "INFY",
    "INFOSYS": "INFY",
    "HDFC": "HDFCBANK",
    "ICICI": "ICICIBANK",
    "SBI": "SBIN",
    "WIPRO": "WIPRO",
    "ITC": "ITC",
    "BHARTI": "BHARTIARTL",
    "AIRTEL": "BHARTIARTL",
}

# Popular tickers by exchange for suggestions
POPULAR_TICKERS = {
    "NSE": [
        "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK", "SBIN", "BHARTIARTL",
        "ITC", "KOTAKBANK", "LT", "ASIANPAINT", "AXISBANK", "MARUTI", "SUNPHARMA",
        "ULTRACEMCO", "TITAN", "WIPRO", "NESTLEIND", "POWERGRID", "NTPC"
    ],
    "NYSE": [
        "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "BRK.B", "UNH", "JNJ",
        "V", "PG", "JPM", "HD", "MA", "ABBV", "PFE", "KO", "PEP", "COST"
    ],
    "NASDAQ": [
        "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "NFLX", "ADBE", "CRM",
        "INTC", "CMCSA", "AMD", "QCOM", "TXN", "AVGO", "ORCL", "CSCO", "PYPL", "AMGN"
    ]
}


def validate_and_suggest_ticker(ticker: str, exchange: str = "NSE") -> Dict[str, any]:
    """
    Validate ticker and provide suggestions if it looks like a typo.
    
    Returns:
        {
            "original": str,
            "corrected": Optional[str],
            "suggestions": List[str],
            "confidence": str  # "high", "medium", "low"
        }
    """
    ticker = ticker.upper().strip()
    
    # Direct correction from known typos
    if ticker in TICKER_CORRECTIONS:
        return {
            "original": ticker,
            "corrected": TICKER_CORRECTIONS[ticker],
            "suggestions": [TICKER_CORRECTIONS[ticker]],
            "confidence": "high"
        }
    
    # Check if ticker is already in popular list (likely correct)
    popular_list = POPULAR_TICKERS.get(exchange, [])
    if ticker in popular_list:
        return {
            "original": ticker,
            "corrected": None,
            "suggestions": [],
            "confidence": "high"
        }
    
    # Find close matches in popular tickers
    suggestions = get_close_matches(ticker, popular_list, n=3, cutoff=0.6)
    
    if suggestions:
        confidence = "medium" if len(suggestions) == 1 else "low"
        return {
            "original": ticker,
            "corrected": suggestions[0] if len(suggestions) == 1 else None,
            "suggestions": suggestions,
            "confidence": confidence
        }
    
    # No suggestions found
    return {
        "original": ticker,
        "corrected": None,
        "suggestions": [],
        "confidence": "low"
    }


def auto_correct_ticker(ticker: str, exchange: str = "NSE") -> str:
    """
    Auto-correct ticker if we have high confidence, otherwise return original.
    """
    result = validate_and_suggest_ticker(ticker, exchange)
    
    if result["confidence"] == "high" and result["corrected"]:
        logger.info(f"Auto-corrected ticker: {ticker} -> {result['corrected']}")
        return result["corrected"]
    
    return ticker
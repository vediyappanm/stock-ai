"""Shared helper for yfinance to ensure consistent session and header usage across all tools.
This helps bypass cloud IP blocks by impersonating a real browser.
"""

import logging
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

def get_yf_session() -> None:
    """
    Deprecated: yfinance now handles sessions internally with curl_cffi.
    Return None to let yfinance manage its own session.
    """
    logger.info("Using yfinance internal session management")
    return None

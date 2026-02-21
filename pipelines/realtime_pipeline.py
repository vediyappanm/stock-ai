"""Real-time data pipeline for WebSockets and live alerts.

Optimised for cloud deployments: uses Finnhub as the primary source for live prices
to avoid being blocked by Yahoo Finance 429 errors.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, time
from typing import Dict, List, Set, Tuple

import httpx
from fastapi import WebSocket

from config.settings import settings

logger = logging.getLogger(__name__)

_COMMON_US_TICKERS = {"AAPL", "AMZN", "GOOGL", "META", "MSFT", "NVDA", "TSLA"}


class ConnectionManager:
    """Manages active WebSocket connections."""

    def __init__(self):
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)

    async def broadcast(self, message: dict):
        if not self.active_connections:
            return
        
        payload = json.dumps(message)
        connections = list(self.active_connections)
        tasks = [connection.send_text(payload) for connection in connections]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for connection, result in zip(connections, results):
            if isinstance(result, Exception):
                self.disconnect(connection)


manager = ConnectionManager()


def _resolve_finnhub_symbol(ticker: str) -> str:
    """Map UI ticker to Finnhub-compatible symbol."""
    raw = ticker.strip().upper()
    if ":" in raw:
        base, exchange = raw.split(":", 1)
        if exchange == "NSE": return f"{base}.NS"
        if exchange == "BSE": return f"{base}.BO"
        return base
    return raw


async def stream_live_prices(tickers: List[str]):
    """
    Real-time price stream using Finnhub polling.
    Avoids yfinance inside background loops to prevent IP blocking.
    """
    last_prices: Dict[str, float] = {}
    api_key = settings.finnhub_api_key
    
    if not api_key:
        logger.warning("Live Stream: No Finnhub API key. Streaming disabled to avoid Yahoo blocks.")
        return

    while True:
        try:
            now = datetime.now()
            # Simple market hours check (India/US combined window for background polling)
            current_hour = now.hour
            is_market_active = (3 <= current_hour <= 21) # Broad window for both NSE and US
            
            if is_market_active or settings.enable_alerts:
                for ticker in tickers:
                    try:
                        symbol = _resolve_finnhub_symbol(ticker)
                        url = f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={api_key}"
                        
                        async with httpx.AsyncClient() as client:
                            resp = await client.get(url, timeout=5)
                            if resp.status_code == 200:
                                data = resp.json()
                                current_price = data.get("c")
                                if current_price:
                                    current_price = float(current_price)
                                    # Only broadcast if price changed
                                    if ticker not in last_prices or abs(current_price - last_prices[ticker]) > 0.001:
                                        change_pct = data.get("dp", 0)
                                        
                                        payload = {
                                            "type": "PRICE_UPDATE",
                                            "ticker": ticker.split(":")[0],
                                            "price": round(current_price, 2),
                                            "timestamp": datetime.now().isoformat(),
                                            "change_pct": round(float(change_pct), 4),
                                            "high": round(float(data.get("h", current_price)), 2),
                                            "low": round(float(data.get("l", current_price)), 2)
                                        }
                                        await manager.broadcast(payload)
                                        last_prices[ticker] = current_price
                        
                        # Small stagger between tickers to avoid burst
                        await asyncio.sleep(0.5)

                    except Exception as e:
                        logger.debug("Live Stream error for %s: %s", ticker, e)
                        continue
            
            # Poll every 20 seconds
            await asyncio.sleep(20)
            
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error("Live Stream loop error: %s", e)
            await asyncio.sleep(60)

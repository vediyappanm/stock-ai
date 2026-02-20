"""Real-time data pipeline for WebSockets and live alerts."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, List, Set, Tuple

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
        
        # Create a list of tasks to run concurrently
        payload = json.dumps(message)
        connections = list(self.active_connections)
        tasks = [connection.send_text(payload) for connection in connections]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for connection, result in zip(connections, results):
            if isinstance(result, Exception):
                self.disconnect(connection)


manager = ConnectionManager()


def _resolve_stream_symbol(ticker: str) -> Tuple[str, str]:
    """Map stream ticker input to provider symbol and UI-friendly base ticker."""
    raw = ticker.strip().upper()

    if ":" in raw:
        base, exchange = raw.split(":", 1)
        if exchange == "NSE":
            return f"{base}.NS", base
        if exchange == "BSE":
            return f"{base}.BO", base
        return base, base

    if raw.endswith("-USD"):
        return raw, raw
    if "." in raw:
        return raw, raw.split(".", 1)[0]
    if raw in _COMMON_US_TICKERS:
        return raw, raw
    return f"{raw}.NS", raw


async def stream_live_prices(tickers: List[str]):
    """
    Real-time price stream using yfinance polling.
    Polls market data every 15 seconds during trading hours.
    """
    import yfinance as yf
    import httpx
    from datetime import datetime, time
    
    # Initialize last known prices
    last_prices: Dict[str, float] = {}
    
    while True:
        # Check if market is open
        now = datetime.now()
        current_time = now.time()
        
        is_market_hours = time(9, 15) <= current_time <= time(15, 30)
        
        if is_market_hours or settings.enable_alerts:
            for ticker in tickers:
                try:
                    current_price = None
                    high_val = 0.0
                    low_val = 0.0
                    
                    symbol, ui_ticker = _resolve_stream_symbol(ticker)

                    # Try Finnhub first if key is available
                    if settings.finnhub_api_key:
                        try:
                            url = f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={settings.finnhub_api_key}"
                            resp = httpx.get(url, timeout=5)
                            if resp.status_code == 200:
                                data = resp.json()
                                if data.get("c"): # 'c' is the current price
                                    current_price = float(data["c"])
                                    high_val = float(data.get("h", current_price))
                                    low_val = float(data.get("l", current_price))
                        except Exception as fe:
                            logger.debug("Finnhub live fetch error for %s: %s", symbol, fe)

                    # Fallback to yfinance if Finnhub failed or not available
                    if current_price is None:
                        stock = yf.Ticker(symbol)
                        hist = stock.history(period="1d", interval="1m")
                        if not hist.empty:
                            current_price = float(hist['Close'].iloc[-1])
                            high_val = float(hist['High'].max())
                            low_val = float(hist['Low'].min())
                    
                    if current_price is not None:
                        # Only broadcast if price changed meaningfully
                        if ticker not in last_prices or abs(current_price - last_prices[ticker]) > 0.001:
                            change_pct = 0.0
                            if ticker in last_prices and last_prices[ticker] > 0:
                                change_pct = ((current_price - last_prices[ticker]) / last_prices[ticker]) * 100
                            
                            payload = {
                                "type": "PRICE_UPDATE",
                                "ticker": ui_ticker,
                                "price": round(current_price, 2),
                                "timestamp": datetime.now().isoformat(),
                                "change_pct": round(change_pct, 4),
                                "high": round(high_val, 2),
                                "low": round(low_val, 2)
                            }
                            
                            await manager.broadcast(payload)
                            last_prices[ticker] = current_price
                            
                            # Check for alerts
                            if settings.enable_alerts and abs(change_pct) > 0.5:
                                alert = {
                                    "type": "ALERT",
                                    "ticker": ui_ticker,
                                    "level": "INFO",
                                    "message": f"Significant movement for {ticker}: {change_pct:+.2f}%",
                                    "value": round(current_price, 2)
                                }
                                await manager.broadcast(alert)
                
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    logger.debug("Error fetching real-time price for %s: %s", ticker, e)
                    continue
        
        # Poll every 15 seconds (Finnhub allows higher frequency, but 15s is good for our needs)
        await asyncio.sleep(15)

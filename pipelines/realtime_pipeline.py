"""Real-time data pipeline for WebSockets and live alerts."""

from __future__ import annotations

import asyncio
import json
import random
from datetime import datetime
from typing import Dict, List, Set

from fastapi import WebSocket
from config.settings import settings


class ConnectionManager:
    """Manages active WebSocket connections."""

    def __init__(self):
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        if not self.active_connections:
            return
        
        # Create a list of tasks to run concurrently
        payload = json.dumps(message)
        tasks = [connection.send_text(payload) for connection in self.active_connections]
        await asyncio.gather(*tasks, return_exceptions=True)


manager = ConnectionManager()


async def stream_live_prices(tickers: List[str]):
    """
    Simulates a live price stream for a list of tickers.
    In a production app, this would subscribe to a real WebSocket feed.
    """
    # Mock starting prices
    prices = {ticker: random.uniform(2000, 3000) for ticker in tickers}
    
    while True:
        for ticker in tickers:
            # Random walk simulation
            change = random.uniform(-0.002, 0.002)
            prices[ticker] *= (1 + change)
            
            payload = {
                "type": "PRICE_UPDATE",
                "ticker": ticker,
                "price": round(prices[ticker], 2),
                "timestamp": datetime.now().isoformat(),
                "change_pct": round(change * 100, 4)
            }
            
            await manager.broadcast(payload)
            
            # Check for alerts (simple threshold demo)
            if settings.enable_alerts and abs(change) > 0.0015:
                alert = {
                    "type": "ALERT",
                    "ticker": ticker,
                    "level": "INFO",
                    "message": f"Significant price volatility detected for {ticker}",
                    "value": round(prices[ticker], 2)
                }
                await manager.broadcast(alert)
                
        await asyncio.sleep(1) # Stream every second

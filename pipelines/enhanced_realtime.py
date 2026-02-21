"""Enhanced Real-time Integration for All Components.

Neutralised to stop hitting Yahoo Finance in background loops.
Uses Finnhub and Alpaca as reliable cloud sources.
"""

import asyncio
import logging
from datetime import datetime, time
from typing import Dict, List, Set, Optional

import httpx
from config.settings import settings
from pipelines.realtime_pipeline import manager

logger = logging.getLogger(__name__)

class EnhancedRealtimeManager:
    """Enhanced real-time manager optimized for cloud resiliency."""
    
    def __init__(self):
        self.active_watchlist: Set[str] = set()
        self.active_portfolio: Set[str] = set()
        self.price_cache: Dict[str, Dict] = {}
        self.alert_threshold = 0.5
        
    async def start_realtime_streaming(self):
        """Start streaming for watchlist and portfolio symbols."""
        from tools.watchlist import watchlist_manager
        from tools.portfolio import portfolio_manager
        
        watchlist_items = watchlist_manager.get_all()
        portfolio_items = portfolio_manager.get_all()
        
        self.active_watchlist = {item.ticker for item in watchlist_items}
        self.active_portfolio = {item.ticker for item in portfolio_items}
        all_tickers = list(self.active_watchlist.union(self.active_portfolio))
        
        if all_tickers and settings.finnhub_api_key:
            logger.info(f"📡 Enhanced Stream: {len(all_tickers)} tickers active")
            asyncio.create_task(self._safe_price_stream(all_tickers))
        else:
            logger.info("⚠️ Enhanced Stream: Disabled (no tickers or no API key)")
    
    async def _safe_price_stream(self, tickers: List[str]):
        """Price streaming using only cloud-safe APIs (Finnhub)."""
        api_key = settings.finnhub_api_key
        last_prices = {}
        
        while True:
            try:
                for ticker in tickers:
                    # Map UI ticker to Finnhub symbol (Best Effort)
                    symbol = ticker.replace("NSE:", "").replace("BSE:", "")
                    if ".NS" not in symbol and ".BO" not in symbol:
                        # Auto-suffix for Indian stocks in watchlist
                        if any(c.islower() for c in ticker): pass # likely already handled
                        else: symbol = f"{symbol}.NS" # Default to NSE
                    
                    try:
                        url = f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={api_key}"
                        async with httpx.AsyncClient() as client:
                            resp = await client.get(url, timeout=5)
                            if resp.status_code == 200:
                                data = resp.json()
                                price = data.get("c")
                                if price:
                                    price = float(price)
                                    if ticker not in last_prices or abs(price - last_prices[ticker]) > 0.01:
                                        payload = {
                                            "type": "ENHANCED_PRICE_UPDATE",
                                            "ticker": ticker,
                                            "price": price,
                                            "change_pct": float(data.get("dp", 0)),
                                            "timestamp": datetime.now().isoformat(),
                                            "high": float(data.get("h", price)),
                                            "low": float(data.get("l", price)),
                                            "source": "finnhub"
                                        }
                                        await manager.broadcast(payload)
                                        last_prices[ticker] = price
                        
                        await asyncio.sleep(1) # Stagger requests

                    except Exception as e:
                        logger.debug(f"Enhanced Stream fetch failed for {ticker}: {e}")
                
                await asyncio.sleep(30) # Poll every 30s
                
            except Exception as e:
                logger.error(f"Enhanced Stream loop error: {e}")
                await asyncio.sleep(60)

# Global instances
enhanced_manager = EnhancedRealtimeManager()

async def start_enhanced_realtime():
    await enhanced_manager.start_realtime_streaming()

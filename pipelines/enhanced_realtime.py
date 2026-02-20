"""Enhanced Real-time Integration for All Components"""

import asyncio
import json
from datetime import datetime, time
from typing import Dict, List, Set
import logging

from config.settings import settings
from pipelines.realtime_pipeline import manager

logger = logging.getLogger(__name__)

class EnhancedRealtimeManager:
    """Enhanced real-time manager for complete system integration"""
    
    def __init__(self):
        self.active_watchlist: Set[str] = set()
        self.active_portfolio: Set[str] = set()
        self.price_cache: Dict[str, Dict] = {}
        self.alert_threshold = 0.5  # 0.5% change threshold
        self.last_broadcast = {}
        
    async def start_realtime_streaming(self):
        """Start comprehensive real-time streaming for all components"""
        logger.info("🚀 Starting enhanced real-time streaming...")
        
        # Get current watchlist and portfolio
        from tools.watchlist import watchlist_manager
        from tools.portfolio import portfolio_manager
        
        watchlist_items = watchlist_manager.get_all()
        portfolio_items = portfolio_manager.get_all()
        
        # Extract tickers
        self.active_watchlist = {item.ticker for item in watchlist_items}
        self.active_portfolio = {item.ticker for item in portfolio_items}
        
        # Combine all tickers for streaming
        all_tickers = self.active_watchlist.union(self.active_portfolio)
        
        if all_tickers:
            logger.info(f"📡 Streaming {len(all_tickers)} tickers in real-time")
            await self._broadcast_system_status("REALTIME_STARTED", f"Streaming {len(all_tickers)} symbols")
            
            # Start the enhanced streaming task
            asyncio.create_task(self._enhanced_price_stream(list(all_tickers)))
        else:
            logger.info("⚠️ No tickers to stream")
            await self._broadcast_system_status("NO_TICKERS", "No symbols in watchlist/portfolio")
    
    async def _enhanced_price_stream(self, tickers: List[str]):
        """Enhanced price streaming with better error handling and features"""
        import yfinance as yf
        import httpx
        
        last_prices = {}
        volume_cache = {}
        
        while True:
            try:
                now = datetime.now()
                current_time = now.time()
                
                # Check market hours for different exchanges
                is_nse_open = time(9, 15) <= current_time <= time(15, 30)
                is_nyse_open = time(9, 30) <= current_time <= time(16, 0)
                
                # Stream during market hours or if alerts are enabled
                should_stream = (is_nse_open or is_nyse_open or settings.enable_alerts)
                
                if should_stream:
                    for ticker in tickers:
                        try:
                            price_data = await self._fetch_comprehensive_price(ticker)
                            
                            if price_data:
                                # Check for significant changes
                                last_price = last_prices.get(ticker)
                                if last_price and abs(price_data['price'] - last_price) > 0.01:
                                    change_pct = ((price_data['price'] - last_price) / last_price) * 100
                                    
                                    # Prepare comprehensive update
                                    update_payload = {
                                        "type": "ENHANCED_PRICE_UPDATE",
                                        "ticker": ticker,
                                        "price": price_data['price'],
                                        "change": price_data['price'] - last_price,
                                        "change_pct": round(change_pct, 3),
                                        "volume": price_data.get('volume', 0),
                                        "timestamp": now.isoformat(),
                                        "high": price_data.get('high', price_data['price']),
                                        "low": price_data.get('low', price_data['price']),
                                        "open": price_data.get('open', price_data['price']),
                                        "exchange": price_data.get('exchange', 'NSE'),
                                        "market_cap": price_data.get('market_cap', 0)
                                    }
                                    
                                    # Broadcast to all connected clients
                                    await manager.broadcast(update_payload)
                                    
                                    # Check for alerts
                                    if abs(change_pct) >= self.alert_threshold:
                                        await self._send_alert(ticker, change_pct, price_data['price'])
                                    
                                    # Update cache
                                    self.price_cache[ticker] = update_payload
                                    last_prices[ticker] = price_data['price']
                                    
                        except Exception as e:
                            logger.error(f"Error streaming {ticker}: {e}")
                            continue
                
                # Broadcast periodic status updates
                if now.minute % 5 == 0:  # Every 5 minutes
                    await self._broadcast_market_status()
                
                # Dynamic polling interval
                if should_stream:
                    await asyncio.sleep(10)  # 10 seconds during market hours
                else:
                    await asyncio.sleep(60)  # 1 minute when market closed
                    
            except Exception as e:
                logger.error(f"Error in enhanced streaming loop: {e}")
                await asyncio.sleep(30)
    
    async def _fetch_comprehensive_price(self, ticker: str) -> Dict:
        """Fetch comprehensive price data from multiple sources"""
        import yfinance as yf
        import httpx
        
        from tools.ticker_resolver import resolve_ticker
        
        # Resolve ticker to get standard exchange and symbol
        try:
            resolved = resolve_ticker(stock=ticker)
            exchange = resolved.exchange
            full_symbol = resolved.full_symbol
        except Exception:
            # Fallback if resolution fails
            exchange = "NSE"
            full_symbol = f"{ticker}.NS"

        price_data = {}
        
        # Try Finnhub first for real-time data (US stocks only on free tier)
        if settings.finnhub_api_key and exchange in ["NYSE", "NASDAQ"]:
            try:
                # Finnhub free tier only supports US stocks
                # Use resolved.symbol (e.g. NVDA) not full_symbol (NVDA) for Finnhub? 
                # resolve_ticker returns full_symbol as TICKER (US) or TICKER.NS (India)
                # Finnhub needs just the ticker for US.
                finnhub_symbol = full_symbol.split(".")[0]
                
                url = f"https://finnhub.io/api/v1/quote?symbol={finnhub_symbol}&token={settings.finnhub_api_key}"
                resp = httpx.get(url, timeout=5)
                
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("c"):
                        price_data.update({
                            'price': float(data["c"]),
                            'change': float(data.get("d", 0)),
                            'change_pct': float(data.get("dp", 0)),
                            'high': float(data.get("h", 0)),
                            'low': float(data.get("l", 0)),
                            'open': float(data.get("o", 0)),
                            'volume': int(data.get("v", 0)),
                            'source': 'finnhub',
                            'exchange': exchange
                        })
            except Exception as e:
                logger.debug(f"Finnhub failed for {ticker}: {e}")
        
        # Fallback to yfinance for all stocks (primary source for Indian stocks)
        if not price_data or price_data.get('source') != 'finnhub':
            try:
                # Use the resolved full symbol for yfinance
                symbol = full_symbol
                
                stock = yf.Ticker(symbol)
                hist = stock.history(period="1d", interval="1m")
                
                if not hist.empty:
                    latest = hist.iloc[-1]
                    price_data.update({
                        'price': float(latest['Close']),
                        'high': float(latest['High']),
                        'low': float(latest['Low']),
                        'open': float(latest['Open']),
                        'volume': int(latest['Volume']),
                        'source': 'yfinance',
                        'exchange': 'NSE'
                    })
                    
                    # Get additional info
                    info = stock.info
                    if info:
                        price_data['market_cap'] = info.get('marketCap', 0)
                        
            except Exception as e:
                logger.debug(f"Yfinance failed for {ticker}: {e}")
        
        return price_data if price_data else None
    
    async def _send_alert(self, ticker: str, change_pct: float, price: float):
        """Send real-time alert"""
        alert = {
            "type": "REALTIME_ALERT",
            "ticker": ticker,
            "level": "WARNING" if abs(change_pct) > 2.0 else "INFO",
            "change_pct": round(change_pct, 3),
            "price": round(price, 2),
            "message": f"{ticker} moved {change_pct:+.2f}% to ₹{price:.2f}",
            "timestamp": datetime.now().isoformat()
        }
        
        await manager.broadcast(alert)
        logger.info(f"🚨 Alert: {ticker} {change_pct:+.2f}%")
    
    async def _broadcast_system_status(self, status_type: str = None, message: str = None):
        """Broadcast system status updates"""
        status = {
            "type": "SYSTEM_STATUS",
            "status": status_type or "STREAMING_ACTIVE",
            "message": message or "Real-time streaming active",
            "timestamp": datetime.now().isoformat(),
            "active_watchlist": len(self.active_watchlist),
            "active_portfolio": len(self.active_portfolio),
            "cached_symbols": len(self.price_cache)
        }
        
        await manager.broadcast(status)
    
    async def _broadcast_market_status(self):
        """Broadcast overall market status"""
        try:
            # Get market indices
            indices = ["^NSEI", "^BSESN", "^GSPC", "^DJI"]
            market_data = {}
            
            import yfinance as yf
            for index in indices:
                try:
                    ticker = yf.Ticker(index)
                    hist = ticker.history(period="1d", interval="1m")
                    if not hist.empty:
                        latest = hist.iloc[-1]
                        market_data[index] = {
                            'price': float(latest['Close']),
                            'change': float(latest['Close'] - latest['Open']),
                            'change_pct': ((latest['Close'] - latest['Open']) / latest['Open']) * 100
                        }
                except:
                    pass
            
            market_status = {
                "type": "MARKET_STATUS",
                "indices": market_data,
                "timestamp": datetime.now().isoformat()
            }
            
            await manager.broadcast(market_status)
            
        except Exception as e:
            logger.error(f"Error broadcasting market status: {e}")

# Global enhanced manager instance
enhanced_manager = EnhancedRealtimeManager()

async def start_enhanced_realtime():
    """Start enhanced real-time streaming"""
    await enhanced_manager.start_realtime_streaming()

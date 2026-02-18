"""Batch scanner for multiple tickers to find market opportunities."""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional

import pandas as pd
from pydantic import BaseModel

from config.settings import settings
from models.random_forest import RandomForestModel
from schemas.response_schemas import ScanResultItem
from tools.fetch_data import fetch_ohlcv_data
from tools.indicators import compute_indicators
from tools.ticker_resolver import resolve_ticker


# Market Presets
PRESETS = {
    "NIFTY50": [
        "ADANIENT", "ADANIPORTS", "APOLLOHOSP", "ASIANPAINT", "AXISBANK", 
        "BAJAJ-AUTO", "BAJFINANCE", "BAJAJFINSV", "BPCL", "BHARTIARTL", 
        "BRITANNIA", "CIPLA", "COALINDIA", "DIVISLAB", "DRREDDY", 
        "EICHERMOT", "GRASIM", "HCLTECH", "HDFCBANK", "HDFCLIFE", 
        "HEROMOTOCO", "HINDALCO", "HINDUNILVR", "ICICIBANK", "ITC", 
        "INDUSINDBK", "INFY", "JSWSTEEL", "KOTAKBANK", "LTIM", 
        "LT", "M&M", "MARUTI", "NTPC", "NESTLEIND", 
        "ONGC", "POWERGRID", "RELIANCE", "SBILIFE", "SBIN", 
        "SUNPHARMA", "TCS", "TATACONSUM", "TATAMOTORS", "TATASTEEL", 
        "TECHM", "TITAN", "UPL", "ULTRACEMCO", "WIPRO"
    ],
    "BLUECHIP_US": ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "TSLA", "NVDA"]
}

def scan_ticker(ticker: str, exchange: str = "NSE") -> Optional[ScanResultItem]:
    """Scan a single ticker and compute core metrics."""
    try:
        resolved = resolve_ticker(stock=ticker, exchange=exchange)
        ohlcv = fetch_ohlcv_data(ticker_symbol=resolved.full_symbol, exchange=resolved.exchange)
        indicators = compute_indicators(ohlcv)
        
        last = indicators.iloc[-1]
        prev = indicators.iloc[-2]
        
        # Price Change
        change_pct = ((last["Close"] - prev["Close"]) / prev["Close"]) * 100
        
        # Fast Directional Prediction using RF (quick)
        model = RandomForestModel()
        model.train(indicators.tail(100)) # Small window for speed
        prediction = model.predict_next(indicators)
        ai_direction = "UP" if prediction > last["Close"] else "DOWN"
        
        # Signal Logic
        rsi = float(last["RSI_14"])
        signal = "NEUTRAL"
        if rsi < 30: signal = "OVERSOLD"
        elif rsi > 70: signal = "OVERBOUGHT"
        
        return ScanResultItem(
            ticker=resolved.full_symbol,
            price=float(last["Close"]),
            change_pct=float(change_pct),
            rsi=rsi,
            macd=float(last["MACD"]),
            signal=signal,
            ai_direction=ai_direction
        )
    except Exception as e:
        print(f"Error scanning {ticker}: {e}")
        return None

async def run_market_scan(tickers: List[str], exchange: str = "NSE") -> List[ScanResultItem]:
    """Run parallel scans across a list of tickers."""
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor(max_workers=5) as executor:
        tasks = [
            loop.run_in_executor(executor, scan_ticker, ticker, exchange)
            for ticker in tickers
        ]
        results = await asyncio.gather(*tasks)
    
    return [r for r in results if r is not None]

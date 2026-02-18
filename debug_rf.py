import pandas as pd
from tools.fetch_data import fetch_ohlcv_data
from tools.indicators import compute_indicators
from tools.ticker_resolver import resolve_ticker
from models.random_forest import RandomForestModel
import json

try:
    resolved = resolve_ticker(stock="RELIANCE", exchange="NSE")
    ohlcv = fetch_ohlcv_data(ticker_symbol=resolved.full_symbol, exchange=resolved.exchange)
    indicators = compute_indicators(ohlcv)
    print(f"Indicators columns: {indicators.columns.tolist()}")
    
    rf = RandomForestModel()
    prepared = rf._prepare(indicators)
    print(f"Prepared columns: {prepared.columns.tolist()}")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()

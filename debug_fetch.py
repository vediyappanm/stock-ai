import pandas as pd
from tools.fetch_data import fetch_ohlcv_data
from tools.ticker_resolver import resolve_ticker
import json

try:
    resolved = resolve_ticker(stock="TCS", exchange="NSE")
    print(f"Resolved: {resolved}")
    df = fetch_ohlcv_data(ticker_symbol=resolved.full_symbol, exchange=resolved.exchange)
    print(f"DF Columns: {df.columns.tolist()}")
    print(f"DF Head:\n{df.head()}")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()

import pandas as pd
import numpy as np
import yfinance as yf
from typing import List, Dict, Any
from tools.fetch_data import fetch_ohlcv_data

# Mapping of Nifty Sectors to proxy tickers
SECTOR_PROXIES = {
    "Financial Services": "^CNXFIN",
    "IT": "^CNXIT",
    "Bank": "^NSEBANK",
    "Auto": "^CNXAUTO",
    "FMCG": "^CNXFMCG",
    "Pharma": "^CNXPHARMA",
    "Metal": "^CNXMETAL",
    "Energy": "^CNXENERGY",
    "Realty": "^CNXREALTY"
}

def get_sector_rotation(days: int = 30) -> List[Dict[str, Any]]:
    """Calculate percentage change for major sectors to identify rotation."""
    results = []
    for sector, proxy in SECTOR_PROXIES.items():
        try:
            # yfinance tickers for indices often need ^ prefix
            df = yf.download(proxy, period=f"{days+10}d", interval="1d", progress=False)
            if df.empty: continue
            
            df = df.tail(days)
            start_price = df['Close'].iloc[0]
            end_price = df['Close'].iloc[-1]
            perf = ((end_price - start_price) / start_price) * 100
            
            results.append({
                "sector": sector,
                "proxy": proxy,
                "performance_pct": float(perf.iloc[0]) if hasattr(perf, "iloc") else float(perf)
            })
        except Exception as e:
            print(f"Error fetching sector {sector}: {e}")
            
    # Sort by performance
    return sorted(results, key=lambda x: x['performance_pct'], reverse=True)

def get_portfolio_correlation(tickers: List[str]) -> Dict[str, Any]:
    """Calculate correlation matrix for a list of tickers."""
    if not tickers or len(tickers) < 2:
        return {"error": "At least 2 tickers required for correlation analysis", "matrix": {}}
    
    returns_data = {}
    for ticker in tickers:
        try:
            # Standardize for yfinance
            symbol = f"{ticker}.NS" if not (ticker.endswith(".NS") or ticker.startswith("^")) else ticker
            df = yf.download(symbol, period="90d", progress=False)
            if not df.empty:
                # Ensure we have a Series, not a single-column DataFrame
                close_series = df['Close']
                if hasattr(close_series, "iloc") and isinstance(close_series, pd.DataFrame):
                    close_series = close_series.iloc[:, 0]
                
                rets = close_series.pct_change().dropna()
                if not rets.empty:
                    returns_data[ticker] = rets
        except:
            continue
            
    valid_returns = {t: r for t, r in returns_data.items() if not r.empty}
    if not valid_returns:
        return {"error": "No valid return series found for tickers", "matrix": {}}
        
    df_returns = pd.DataFrame(valid_returns)
    corr_matrix = df_returns.corr().round(2)
    
    # Convert matrix to a more serializable format (list of lists or dict)
    return {
        "tickers": list(corr_matrix.columns),
        "matrix": corr_matrix.values.tolist()
    }

def get_risk_impact_analysis(ticker: str, days: int = 120) -> Dict[str, Any]:
    """Compare Buy & Hold vs a simple ATR-based stop strategy."""
    try:
        symbol = f"{ticker}.NS" if not ticker.endswith(".NS") else ticker
        df = yf.download(symbol, period=f"{days}d", progress=False)
        if df.empty: return {}
        
        # Simple ATR Approximation
        high_low = df['High'] - df['Low']
        high_close = np.abs(df['High'] - df['Close'].shift())
        low_close = np.abs(df['Low'] - df['Close'].shift())
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = tr.rolling(14).mean()
        
        close = df['Close']
        bh_returns = (close / close.iloc[0]) * 100
        
        # Simple Strategy: Use 2*ATR trailing stop
        # In a real app we'd iterate through bars, here we'll simplify
        strategy_equity = [100.0]
        in_pos = True
        entry_price = close.iloc[0]
        
        for i in range(1, len(close)):
            price = close.iloc[i]
            prev_price = close.iloc[i-1]
            current_atr = atr.iloc[i]
            
            if in_pos:
                # Trailing stop logic
                stop_price = close.iloc[:i].max() - (2 * current_atr)
                if price < stop_price:
                    in_pos = False
                    # Gain from entry to prev price
                    change = (prev_price / entry_price)
                    strategy_equity.append(strategy_equity[-1] * change)
                else:
                    # Still in position
                    strategy_equity.append(strategy_equity[-1] * (price / prev_price))
            else:
                # Re-entry logic (e.g. price > prev price + ATR)
                if price > prev_price + (0.5 * current_atr):
                    in_pos = True
                    entry_price = price
                    strategy_equity.append(strategy_equity[-1])
                else:
                    strategy_equity.append(strategy_equity[-1])
                    
        return {
            "buy_and_hold": bh_returns.tolist(),
            "risk_managed": strategy_equity,
            "bh_final": float(bh_returns.iloc[-1]),
            "st_final": float(strategy_equity[-1])
        }
    except Exception as e:
        print(f"Risk analysis error: {e}")
        return {}

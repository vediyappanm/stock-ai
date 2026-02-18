import yfinance as yf
from typing import Dict, Any
from schemas.response_schemas import FundamentalsResult

def get_fundamentals(ticker: str, exchange: str = "NSE") -> Dict[str, Any]:
    """Fetch company fundamentals using yfinance."""
    # Resolve ticker symbol for yfinance
    symbol = ticker
    if exchange == "NSE" and not ticker.endswith(".NS"):
        symbol = f"{ticker}.NS"
    elif exchange == "BSE" and not ticker.endswith(".BO"):
        symbol = f"{ticker}.BO"
        
    try:
        stock = yf.Ticker(symbol)
        info = stock.info
        
        return {
            "name": info.get("longName", "N/A"),
            "sector": info.get("sector", "N/A"),
            "industry": info.get("industry", "N/A"),
            "market_cap": info.get("marketCap", 0),
            "pe_ratio": info.get("trailingPE", 0.0),
            "forward_pe": info.get("forwardPE", 0.0),
            "dividend_yield": info.get("dividendYield", 0.0),
            "beta": info.get("beta", 0.0),
            "fifty_two_week_high": info.get("fiftyTwoWeekHigh", 0.0),
            "fifty_two_week_low": info.get("fiftyTwoWeekLow", 0.0),
            "summary": info.get("longBusinessSummary", "No summary available.")[:1000]
        }
    except Exception as e:
        print(f"Error fetching fundamentals for {symbol}: {e}")
        return {}

def get_financials_table(ticker: str, exchange: str = "NSE") -> List[Dict[str, Any]]:
    """Fetch annual financials table data (Revenue, Net Income, etc)."""
    symbol = ticker
    if exchange == "NSE" and not ticker.endswith(".NS"):
        symbol = f"{ticker}.NS"
    elif exchange == "BSE" and not ticker.endswith(".BO"):
        symbol = f"{ticker}.BO"

    try:
        stock = yf.Ticker(symbol)
        # Fetch annual financials
        df = stock.financials
        if df is None or df.empty:
            return []
            
        table = []
        # Standardize columns (transpose for year rows)
        df_t = df.T
        
        # Mapping for common fields
        mapping = {
            "Total Revenue": "revenue",
            "Net Income": "net_income",
            "EBIT": "ebit",
            "Operating Income": "ebit" # Fallback
        }
        
        for index, row in df_t.head(5).iterrows():
            year = str(index.year) if hasattr(index, "year") else str(index)
            data = {"year": year}
            for yf_key, my_key in mapping.items():
                if yf_key in row:
                    data[my_key] = row[yf_key]
                elif my_key not in data:
                    data[my_key] = 0.0
            
            # Simple growth note logic
            data["growth_notes"] = "Data pulse captured"
            table.append(data)
            
        return sorted(table, key=lambda x: x["year"])
    except Exception as e:
        print(f"Error fetching financials table for {symbol}: {e}")
        return []

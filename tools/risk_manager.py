"""Risk management utilities for position sizing and portfolio protection."""

from __future__ import annotations

import numpy as np
import pandas as pd
from typing import Dict, Any, List

def calculate_kelly_criterion(win_rate: float, avg_win: float, avg_loss: float) -> float:
    """
    Calculate Kelly Criterion for position sizing.
    K% = W - (1-W)/R
    W = win probability
    R = win/loss ratio
    """
    if avg_loss == 0: return 0.2 # Default safe 20% if no loss data
    w = win_rate / 100.0
    r = abs(avg_win / avg_loss)
    kelly = w - ((1 - w) / r) if r != 0 else 0.0
    # Use Half-Kelly for safety (industry standard)
    return max(0, min(kelly * 0.5, 0.25)) # Cap at 25% of capital

def calculate_volatility_adjusted_size(capital: float, price: float, atr: float, risk_factor: float = 0.02) -> float:
    """
    Size based on 'Risk %' of capital. 
    Shares = (Capital * Risk%) / (ATR * Multiplier)
    """
    if atr == 0: return 0.0
    stop_loss_distance = atr * 2.0 # 2x ATR stop
    dollar_at_risk = capital * risk_factor
    shares = dollar_at_risk / stop_loss_distance
    return float(shares)

def calculate_portfolio_var(returns: List[float], confidence: float = 0.95) -> float:
    """Simple Historical Value at Risk (VaR)."""
    if not returns: return 0.0
    sorted_returns = np.sort(returns)
    idx = int((1 - confidence) * len(sorted_returns))
    return float(abs(sorted_returns[idx]))

def get_risk_profile(equity_curve: List[float]) -> Dict[str, Any]:
    """Analyze an equity curve for risk metrics."""
    equity = np.array(equity_curve)
    rets = np.diff(equity) / equity[:-1]
    
    var_95 = calculate_portfolio_var(rets.tolist(), 0.95)
    
    # Calculate Max Consecutive Losses
    is_loss = (rets < 0).astype(int)
    max_consecutive_losses = 0
    current_run = 0
    for l in is_loss:
        if l == 1:
            current_run += 1
            max_consecutive_losses = max(max_consecutive_losses, current_run)
        else:
            current_run = 0
            
    return {
        "var_95_pct": float(var_95 * 100),
        "max_consecutive_losses": max_consecutive_losses,
        "volatility_daily": float(np.std(rets) * 100) if len(rets) > 0 else 0.0,
        "risk_rating": "MODERATE" if var_95 < 0.05 else "HIGH"
    }

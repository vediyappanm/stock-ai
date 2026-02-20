"""Position sizing and risk management (Kelly criterion, drawdown limits)."""

from __future__ import annotations

from typing import Tuple
import logging

logger = logging.getLogger(__name__)


def kelly_criterion(
    win_rate: float,
    avg_win: float,
    avg_loss: float,
    max_fraction: float = 0.25,
) -> float:
    """
    Kelly criterion: optimal fraction of capital to risk.

    Formula: f* = (p*b - q) / b
    where:
    - p = win_rate
    - q = 1 - win_rate
    - b = avg_win / avg_loss (win/loss ratio)

    Returns:
    - fraction: optimal position size (0-1, typically 5-15%)
    - capped at max_fraction to avoid over-leverage
    """
    if win_rate <= 0 or win_rate >= 1:
        return 0.02  # Default conservative 2%

    if avg_loss <= 0:
        return 0.02  # Avoid division by zero

    q = 1 - win_rate
    b = avg_win / avg_loss if avg_loss > 0 else 1.0

    # Kelly formula
    kelly_fraction = (win_rate * b - q) / b if b > 0 else 0.0

    # Cap at max_fraction (typically 25% for safety)
    optimal_fraction = min(max(kelly_fraction, 0.01), max_fraction)

    logger.info(
        f"Kelly Criterion: win_rate={win_rate:.1%}, win/loss={b:.2f}, "
        f"optimal_fraction={optimal_fraction:.1%} (raw={kelly_fraction:.1%})"
    )

    return float(optimal_fraction)


def position_size(
    capital: float,
    kelly_fraction: float,
    current_price: float,
    max_loss_per_trade: float = 0.02,
) -> Tuple[int, float]:
    """
    Calculate position size in shares based on Kelly criterion.

    Args:
    - capital: total capital in $
    - kelly_fraction: from kelly_criterion() (0-1)
    - current_price: stock price
    - max_loss_per_trade: max loss as % of capital (e.g., 2% = 0.02)

    Returns:
    - shares: number of shares to buy
    - position_value: $ value of position
    """
    risk_capital = capital * kelly_fraction
    shares = int(risk_capital / current_price)
    position_value = shares * current_price

    logger.info(
        f"Position sizing: capital={capital:,.0f}, kelly={kelly_fraction:.1%}, "
        f"shares={shares}, value={position_value:,.0f}"
    )

    return shares, position_value


def drawdown_limits(
    entry_price: float,
    kelly_fraction: float,
    capital: float,
    max_drawdown_pct: float = 0.05,
) -> Tuple[float, float]:
    """
    Calculate stop-loss and take-profit levels.

    Args:
    - entry_price: entry stock price
    - kelly_fraction: position size fraction
    - capital: total capital
    - max_drawdown_pct: max portfolio drawdown (e.g., 5% = 0.05)

    Returns:
    - stop_loss_price: stop loss price
    - take_profit_price: take profit price (approx 2:1 reward:risk)
    """
    risk_capital = capital * kelly_fraction
    max_loss = capital * max_drawdown_pct

    # Stop loss: price that triggers max_loss
    loss_per_share = min(max_loss / (risk_capital / entry_price), entry_price * 0.15)
    stop_loss_price = entry_price - loss_per_share

    # Take profit: 2:1 reward:risk
    take_profit_price = entry_price + (2 * loss_per_share)

    logger.info(
        f"Risk limits: entry={entry_price:.2f}, stop={stop_loss_price:.2f}, "
        f"target={take_profit_price:.2f}, risk=${loss_per_share:.2f}"
    )

    return float(stop_loss_price), float(take_profit_price)


def regime_adjustment(
    base_kelly_fraction: float,
    volatility: float,
    volatility_baseline: float = 0.02,
) -> float:
    """
    Adjust Kelly fraction based on volatility regime.

    High vol → reduce position (3x to 5x reduction)
    Low vol → normal Kelly
    """
    vol_ratio = volatility / volatility_baseline if volatility_baseline > 0 else 1.0

    if vol_ratio > 3.0:
        # Extremely high vol: reduce to 50% of Kelly
        adjusted = base_kelly_fraction * 0.5
    elif vol_ratio > 1.5:
        # High vol: reduce to 70% of Kelly
        adjusted = base_kelly_fraction * 0.7
    else:
        # Normal vol: use full Kelly
        adjusted = base_kelly_fraction

    return float(adjusted)


def portfolio_risk_metrics(
    entry_price: float,
    current_price: float,
    shares: int,
    capital: float,
) -> dict:
    """
    Calculate real-time portfolio risk metrics.
    """
    position_value = current_price * shares
    unrealized_pnl = position_value - (entry_price * shares)
    pnl_pct = (unrealized_pnl / (entry_price * shares)) * 100 if entry_price * shares > 0 else 0

    capital_at_risk = (entry_price * shares)
    drawdown_pct = (-unrealized_pnl / capital) * 100 if capital > 0 else 0

    return {
        "position_value": float(position_value),
        "unrealized_pnl": float(unrealized_pnl),
        "pnl_pct": float(pnl_pct),
        "drawdown_pct": float(drawdown_pct),
        "capital_at_risk": float(capital_at_risk),
    }

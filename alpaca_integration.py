#!/usr/bin/env python3
"""Alpaca API Integration - Paper Trading & Live Capital Deployment."""

import os
import logging
from typing import Dict, List, Optional
from datetime import datetime
import json

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

try:
    from alpaca_trade_api import REST
    from alpaca_trade_api.entity import Account, Position, Order
    _HAS_ALPACA = True
except ImportError:
    _HAS_ALPACA = False
    logger.warning("alpaca-trade-api not installed. Run: pip install alpaca-trade-api")


class AlpacaTrader:
    """Interface for Alpaca paper/live trading."""

    def __init__(self, paper: bool = True):
        """
        Initialize Alpaca connection.

        Args:
        - paper: True for paper trading, False for live capital
        """
        if not _HAS_ALPACA:
            raise ImportError("alpaca-trade-api required. Install: pip install alpaca-trade-api")

        self.paper = paper
        self.api_key = os.getenv("APCA_API_KEY_ID")
        self.secret_key = os.getenv("APCA_API_SECRET_KEY")

        if not self.api_key or not self.secret_key:
            raise ValueError(
                "Set APCA_API_KEY_ID and APCA_API_SECRET_KEY environment variables. "
                "Get free paper keys: alpaca.markets"
            )

        # Connect to Alpaca
        base_url = 'https://paper-api.alpaca.markets' if paper else 'https://api.alpaca.markets'
        self.api = REST(self.api_key, self.secret_key, base_url=base_url)

        # Get account info
        account = self.api.get_account()
        self.capital = float(account.cash)
        self.mode = "PAPER" if paper else "LIVE"

        logger.info(
            f"Connected to Alpaca ({self.mode} mode) | "
            f"Capital: ${self.capital:,.2f} | "
            f"Buying Power: ${account.buying_power:,.2f}"
        )

    def get_positions(self) -> Dict[str, Dict]:
        """Get current open positions."""
        positions = self.api.list_positions()
        result = {}

        for pos in positions:
            result[pos.symbol] = {
                "shares": int(pos.qty),
                "avg_entry": float(pos.avg_fill_price),
                "current_value": float(pos.market_value),
                "unrealized_pnl": float(pos.unrealized_pl),
                "unrealized_pnl_pct": float(pos.unrealized_plpc) * 100,
            }

        return result

    def submit_order(
        self,
        symbol: str,
        qty: int,
        side: str,
        order_type: str = "market",
        time_in_force: str = "day",
        stop_price: Optional[float] = None,
        limit_price: Optional[float] = None,
    ) -> Dict:
        """
        Submit order to Alpaca.

        Args:
        - symbol: Ticker (e.g., 'NVDA')
        - qty: Quantity of shares
        - side: 'buy' or 'sell'
        - order_type: 'market', 'limit', 'stop', 'stop_limit'
        - time_in_force: 'day', 'gtc' (good-til-canceled), 'opg', 'cls'
        - stop_price: For stop/stop_limit orders
        - limit_price: For limit/stop_limit orders

        Returns:
        - Order details with ID, status, fill price
        """
        try:
            order = self.api.submit_order(
                symbol=symbol,
                qty=qty,
                side=side,
                type=order_type,
                time_in_force=time_in_force,
                stop_price=stop_price,
                limit_price=limit_price,
            )

            logger.info(
                f"[ORDER] {side.upper()} {qty} {symbol} "
                f"@ {limit_price or 'market'} | "
                f"Order ID: {order.id}"
            )

            return {
                "id": order.id,
                "symbol": order.symbol,
                "qty": int(order.qty),
                "side": order.side,
                "type": order.order_type,
                "status": order.status,
                "filled_qty": int(order.filled_qty) if order.filled_qty else 0,
                "filled_avg_price": float(order.filled_avg_price) if order.filled_avg_price else None,
                "timestamp": order.created_at.isoformat(),
            }

        except Exception as e:
            logger.error(f"Failed to submit order: {e}")
            raise

    def close_position(self, symbol: str, qty: Optional[int] = None) -> Dict:
        """
        Close position (sell all or partial).

        Args:
        - symbol: Ticker
        - qty: Shares to sell (if None, closes entire position)
        """
        positions = self.get_positions()

        if symbol not in positions:
            logger.warning(f"No position in {symbol}")
            return {}

        close_qty = qty or positions[symbol]["shares"]

        return self.submit_order(symbol=symbol, qty=close_qty, side="sell")

    def get_order_status(self, order_id: str) -> Dict:
        """Get status of submitted order."""
        try:
            order = self.api.get_order(order_id)

            return {
                "id": order.id,
                "status": order.status,
                "filled_qty": int(order.filled_qty) if order.filled_qty else 0,
                "filled_avg_price": float(order.filled_avg_price) if order.filled_avg_price else None,
                "created_at": order.created_at.isoformat(),
            }

        except Exception as e:
            logger.error(f"Failed to get order status: {e}")
            return {}

    def get_portfolio_summary(self) -> Dict:
        """Get portfolio summary."""
        account = self.api.get_account()
        positions = self.get_positions()

        portfolio_value = float(account.portfolio_value)
        total_return = (portfolio_value - self.capital) / self.capital * 100

        return {
            "portfolio_value": portfolio_value,
            "cash": float(account.cash),
            "buying_power": float(account.buying_power),
            "total_return_pct": total_return,
            "open_positions": len(positions),
            "positions": positions,
            "mode": self.mode,
        }

    def set_stop_and_limit(
        self,
        symbol: str,
        stop_price: float,
        limit_price: Optional[float] = None,
    ) -> Dict:
        """
        Set stop loss or stop-limit order for open position.

        Args:
        - symbol: Ticker
        - stop_price: Stop loss price
        - limit_price: Sell limit (if None, market order when triggered)
        """
        positions = self.get_positions()

        if symbol not in positions:
            logger.warning(f"No position in {symbol} to set stops")
            return {}

        qty = positions[symbol]["shares"]

        # Submit stop or stop-limit order
        return self.submit_order(
            symbol=symbol,
            qty=qty,
            side="sell",
            order_type="stop_limit" if limit_price else "stop",
            stop_price=stop_price,
            limit_price=limit_price,
        )


def deploy_paper_trading(tickers: List[str] = None, capital: float = 100000):
    """
    Deploy paper trading with signal generation.

    Args:
    - tickers: List of tickers to trade (default: ['NVDA', 'AMD'])
    - capital: Starting capital (default: $100k)
    """
    if tickers is None:
        tickers = ["NVDA", "AMD"]

    logger.info("=" * 70)
    logger.info("DEPLOYING PAPER TRADING")
    logger.info("=" * 70)

    try:
        # Connect to Alpaca
        trader = AlpacaTrader(paper=True)

        # Example: Execute buy signal
        logger.info("\nExample: Executing BUY signal for NVDA")

        # Get current price (you'd use your prediction here)
        from tools.fetch_data import fetch_ohlcv_data
        from tools.ticker_resolver import resolve_ticker

        for ticker in tickers:
            resolved = resolve_ticker(stock=ticker, exchange="NASDAQ")
            ohlcv = fetch_ohlcv_data(ticker_symbol=resolved.full_symbol, exchange="NASDAQ", days=1)

            if len(ohlcv) > 0:
                current_price = float(ohlcv.iloc[-1]["Close"])
                kelly_fraction = 0.062  # 1/4 Kelly

                # Calculate position size
                position_capital = trader.capital * kelly_fraction
                shares = int(position_capital / current_price)

                logger.info(f"\n{ticker}: Current price ${current_price:.2f}")
                logger.info(f"  Position size: {shares} shares")
                logger.info(f"  Capital allocated: ${shares * current_price:,.2f}")

                # Submit BUY order
                if shares > 0:
                    order = trader.submit_order(
                        symbol=ticker,
                        qty=shares,
                        side="buy",
                        order_type="market",
                    )
                    logger.info(f"  Order submitted: {order['id']}")

        # Get portfolio summary
        logger.info("\nPortfolio Summary:")
        summary = trader.get_portfolio_summary()
        logger.info(f"  Portfolio Value: ${summary['portfolio_value']:,.2f}")
        logger.info(f"  Cash: ${summary['cash']:,.2f}")
        logger.info(f"  Open Positions: {summary['open_positions']}")

        logger.info("\n" + "=" * 70)
        logger.info("PAPER TRADING DEPLOYED - Monitor via dashboard")
        logger.info("=" * 70)

    except Exception as e:
        logger.error(f"Deployment failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # Check if API keys are set
    if not os.getenv("APCA_API_KEY_ID"):
        print("\n" + "=" * 70)
        print("ALPACA API KEY SETUP REQUIRED")
        print("=" * 70)
        print("\n1. Go to: https://app.alpaca.markets/")
        print("2. Sign up for free paper trading account")
        print("3. Create API key in Settings → API")
        print("4. Set environment variables:")
        print('   export APCA_API_KEY_ID="your_key"')
        print('   export APCA_API_SECRET_KEY="your_secret"')
        print('   export APCA_PAPER=True')
        print("\n5. Then run: python alpaca_integration.py")
        print("=" * 70 + "\n")
    else:
        # Deploy paper trading
        deploy_paper_trading(tickers=["NVDA", "AMD"], capital=100000)

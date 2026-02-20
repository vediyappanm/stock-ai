"""Alpaca broker integration for paper & live trading."""

from __future__ import annotations

import os
import logging
from typing import Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

try:
    from alpaca.trading.client import TradingClient
    from alpaca.trading.requests import MarketOrderRequest, LimitOrderRequest
    from alpaca.trading.enums import OrderSide, TimeInForce
    from alpaca.data.historical import StockHistoricalDataClient
    _HAS_ALPACA = True
except Exception:
    _HAS_ALPACA = False
    TradingClient = None

# Import settings
from config.settings import settings


class AlpacaBroker:
    """Connect to Alpaca trading API (paper or live)."""

    def __init__(self, paper: bool = True):
        """
        Initialize Alpaca broker connection.

        Args:
        - paper: True for paper trading, False for live
        """
        if not _HAS_ALPACA:
            raise ImportError("alpaca-py library required. Install: pip install alpaca-py")

        # Use settings first, fallback to environment variables
        self.api_key = settings.alpaca_api_key_id or os.environ.get("APCA_API_KEY_ID")
        self.secret_key = settings.alpaca_api_secret_key or os.environ.get("APCA_API_SECRET_KEY")
        self.paper = paper or settings.alpaca_paper

        if not self.api_key or not self.secret_key:
            raise ValueError(
                "Set alpaca_api_key_id and alpaca_api_secret_key in settings or "
                "APCA_API_KEY_ID and APCA_API_SECRET_KEY environment variables"
            )

        # Connect
        self.client = TradingClient(
            api_key=self.api_key,
            secret_key=self.secret_key,
            paper=self.paper
        )

        account = self.client.get_account()
        logger.info(
            f"Connected to Alpaca {'PAPER' if self.paper else 'LIVE'} trading. "
            f"Account: {account.account_number}, Cash: ${float(account.cash):,.2f}"
        )

    def place_market_order(
        self,
        ticker: str,
        qty: int,
        side: str = "buy",  # "buy" or "sell"
    ) -> Dict:
        """Place market order."""

        order_request = MarketOrderRequest(
            symbol=ticker,
            qty=qty,
            side=OrderSide.BUY if side.lower() == "buy" else OrderSide.SELL,
            time_in_force=TimeInForce.DAY,
        )

        try:
            order = self.client.submit_order(order_request)
            logger.info(
                f"[{side.upper()}] {ticker}: {qty} shares. "
                f"Order ID: {order.id}, Status: {order.status}"
            )
            return {
                "order_id": order.id,
                "ticker": ticker,
                "qty": qty,
                "side": side,
                "status": order.status,
                "submitted_at": order.submitted_at.isoformat() if order.submitted_at else None,
            }
        except Exception as e:
            logger.error(f"Order failed: {e}")
            return {"error": str(e)}

    def place_limit_order(
        self,
        ticker: str,
        qty: int,
        limit_price: float,
        side: str = "buy",
    ) -> Dict:
        """Place limit order."""

        order_request = LimitOrderRequest(
            symbol=ticker,
            qty=qty,
            limit_price=limit_price,
            side=OrderSide.BUY if side.lower() == "buy" else OrderSide.SELL,
            time_in_force=TimeInForce.DAY,
        )

        try:
            order = self.client.submit_order(order_request)
            logger.info(
                f"[{side.upper()}] {ticker}: {qty} @ ${limit_price:.2f}. "
                f"Order ID: {order.id}"
            )
            return {
                "order_id": order.id,
                "ticker": ticker,
                "qty": qty,
                "limit_price": limit_price,
                "side": side,
                "status": order.status,
            }
        except Exception as e:
            logger.error(f"Limit order failed: {e}")
            return {"error": str(e)}

    def cancel_order(self, order_id: str) -> bool:
        """Cancel an open order."""

        try:
            self.client.cancel_order_by_id(order_id)
            logger.info(f"Cancelled order: {order_id}")
            return True
        except Exception as e:
            logger.error(f"Cancel failed: {e}")
            return False

    def get_positions(self) -> List[Dict]:
        """Get current positions."""

        try:
            positions = self.client.get_all_positions()
            return [
                {
                    "ticker": p.symbol,
                    "qty": int(p.qty),
                    "avg_fill_price": float(p.avg_fill_price),
                    "market_value": float(p.market_value),
                    "unrealized_pl": float(p.unrealized_pl),
                    "unrealized_pl_pct": float(p.unrealized_plpc),
                }
                for p in positions
            ]
        except Exception as e:
            logger.error(f"Get positions failed: {e}")
            return []

    def get_account(self) -> Dict:
        """Get account information."""

        try:
            account = self.client.get_account()
            return {
                "cash": float(account.cash),
                "buying_power": float(account.buying_power),
                "portfolio_value": float(account.portfolio_value),
                "day_trading_buying_power": float(account.daytrade_buying_power),
                "status": account.status,
            }
        except Exception as e:
            logger.error(f"Get account failed: {e}")
            return {}

    def close_position(self, ticker: str, percent: float = 100) -> Dict:
        """Close position (partially or fully)."""

        positions = self.get_positions()
        position = next((p for p in positions if p["ticker"] == ticker), None)

        if not position:
            logger.warning(f"No position in {ticker}")
            return {}

        qty_to_sell = int(position["qty"] * percent / 100)

        if qty_to_sell == 0:
            return {}

        return self.place_market_order(ticker, qty_to_sell, side="sell")

    def get_orders(self, status: str = "open") -> List[Dict]:
        """Get orders by status."""

        try:
            orders = self.client.get_orders(status=status)
            return [
                {
                    "order_id": o.id,
                    "ticker": o.symbol,
                    "qty": int(o.qty),
                    "side": o.side.value,
                    "status": o.status.value,
                    "submitted_at": o.submitted_at.isoformat() if o.submitted_at else None,
                }
                for o in orders
            ]
        except Exception as e:
            logger.error(f"Get orders failed: {e}")
            return []

#!/usr/bin/env python3
"""Live Trading Engine - Real-time predictions → Alpaca orders."""

import os
import logging
from datetime import datetime
from typing import Dict, Optional
import json
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

from alpaca_integration import AlpacaTrader
from tools.position_sizing import kelly_criterion, drawdown_limits
from tools.model_monitor import ModelHealthMonitor


class LiveTradingEngine:
    """Execute live predictions as Alpaca orders."""

    def __init__(
        self,
        capital: float = 100000,
        paper: bool = True,
        tickers: list = None,
    ):
        """
        Initialize live trading engine.

        Args:
        - capital: Starting capital
        - paper: True for paper trading, False for live
        - tickers: List of symbols to trade
        """
        self.capital = capital
        self.paper = paper
        self.tickers = tickers or ["NVDA", "AMD", "MSFT"]

        # Connect to Alpaca
        self.broker = AlpacaTrader(paper=paper)

        # Model monitoring
        self.monitors = {ticker: ModelHealthMonitor(ticker) for ticker in self.tickers}

        # Trade log
        self.trades_log = Path("trades.json")
        self.trades = self._load_trades_log()

        mode = "PAPER" if paper else "LIVE"
        logger.info(
            f"Live Trading Engine initialized ({mode} mode) | "
            f"Capital: ${capital:,.2f} | Tickers: {self.tickers}"
        )

    def _load_trades_log(self) -> list:
        """Load previous trades from log."""
        if self.trades_log.exists():
            try:
                return json.loads(self.trades_log.read_text())
            except Exception:
                return []
        return []

    def _save_trades_log(self) -> None:
        """Save trades to log."""
        self.trades_log.write_text(json.dumps(self.trades, indent=2))

    def execute_signal(
        self,
        ticker: str,
        signal: str,  # "BUY" or "SELL"
        predicted_price: float,
        current_price: float,
        confidence: float,
        indicators: Dict = None,
    ) -> Dict:
        """
        Execute trading signal.

        Args:
        - ticker: Stock symbol
        - signal: "BUY" or "SELL"
        - predicted_price: Model's predicted price
        - current_price: Current market price
        - confidence: Prediction confidence (0-1)
        - indicators: Technical indicators dict (optional)

        Returns:
        - Trade execution result
        """

        # Check if already have position
        positions = self.broker.get_positions()
        if ticker in positions and signal == "BUY":
            logger.warning(f"Already have position in {ticker}. Skipping BUY.")
            return {"status": "skipped", "reason": "position_exists"}

        # Check model health
        monitor = self.monitors[ticker]
        accuracy = monitor.get_recent_accuracy(days=7)

        if accuracy < 0.50:
            logger.warning(f"Model accuracy too low ({accuracy:.1%}). Skipping signal.")
            return {"status": "skipped", "reason": "low_accuracy"}

        # Position sizing (Kelly criterion)
        win_rate = accuracy  # Approximate
        kelly_f = kelly_criterion(
            win_rate=win_rate,
            avg_win=2.5,
            avg_loss=1.0,
            max_fraction=0.25,
        )

        # Conservative: use 1/4 Kelly
        conservative_f = kelly_f / 4
        position_capital = self.capital * conservative_f

        if signal == "BUY":
            shares = int(position_capital / current_price)

            if shares == 0:
                logger.warning(f"Insufficient capital for {ticker} position")
                return {"status": "skipped", "reason": "insufficient_capital"}

            # Risk limits
            stop_loss, take_profit = drawdown_limits(
                current_price, conservative_f, self.capital, max_drawdown_pct=0.05
            )

            # Submit BUY order
            try:
                order = self.broker.submit_order(
                    symbol=ticker,
                    qty=shares,
                    side="buy",
                    order_type="market",
                )

                # Set stop loss
                self.broker.set_stop_and_limit(
                    symbol=ticker,
                    stop_price=stop_loss,
                    limit_price=take_profit,
                )

                trade = {
                    "timestamp": datetime.now().isoformat(),
                    "signal": "BUY",
                    "ticker": ticker,
                    "shares": shares,
                    "entry_price": current_price,
                    "predicted_price": predicted_price,
                    "confidence": confidence,
                    "stop_loss": stop_loss,
                    "take_profit": take_profit,
                    "kelly_fraction": conservative_f,
                    "order_id": order["id"],
                    "accuracy_7d": accuracy,
                }

                self.trades.append(trade)
                self._save_trades_log()

                # Log signal
                monitor.log_prediction(
                    predicted_price=predicted_price,
                    actual_price=current_price,
                    confidence=confidence,
                )

                logger.info(
                    f"[SIGNAL] {signal} {ticker} | "
                    f"Shares: {shares} @ ${current_price:.2f} | "
                    f"SL: ${stop_loss:.2f} | TP: ${take_profit:.2f} | "
                    f"Confidence: {confidence:.1%} | Kelly: {conservative_f:.1%}"
                )

                return {
                    "status": "executed",
                    "order_id": order["id"],
                    "trade": trade,
                }

            except Exception as e:
                logger.error(f"Failed to execute BUY signal: {e}")
                return {"status": "failed", "error": str(e)}

        elif signal == "SELL":
            # Close position
            try:
                order = self.broker.close_position(ticker)

                trade = {
                    "timestamp": datetime.now().isoformat(),
                    "signal": "SELL",
                    "ticker": ticker,
                    "exit_price": current_price,
                    "order_id": order["id"],
                }

                self.trades.append(trade)
                self._save_trades_log()

                logger.info(
                    f"[SIGNAL] {signal} {ticker} | "
                    f"Exit @ ${current_price:.2f} | Order: {order['id']}"
                )

                return {
                    "status": "executed",
                    "order_id": order["id"],
                    "trade": trade,
                }

            except Exception as e:
                logger.error(f"Failed to execute SELL signal: {e}")
                return {"status": "failed", "error": str(e)}

        return {"status": "unknown"}

    def get_performance(self) -> Dict:
        """Get current portfolio performance."""
        summary = self.broker.get_portfolio_summary()

        closed_trades = [t for t in self.trades if "exit_price" in t]
        pnls = []

        for trade in closed_trades:
            if "entry_price" in trade and "exit_price" in trade:
                pnl = (trade["exit_price"] - trade["entry_price"]) * trade.get("shares", 1)
                pnls.append(pnl)

        return {
            "portfolio_value": summary["portfolio_value"],
            "cash": summary["cash"],
            "total_return_pct": summary["total_return_pct"],
            "open_positions": summary["open_positions"],
            "closed_trades": len(closed_trades),
            "total_pnl": sum(pnls),
            "win_rate": len([p for p in pnls if p > 0]) / len(pnls) * 100 if pnls else 0,
            "mode": "PAPER" if self.paper else "LIVE",
        }

    def health_check(self) -> Dict:
        """Check system health."""
        health = {
            "timestamp": datetime.now().isoformat(),
            "status": "healthy",
            "models": {},
        }

        for ticker, monitor in self.monitors.items():
            report = monitor.get_health_report()
            health["models"][ticker] = report

        return health


def run_live_trading_demo():
    """Demo: execute sample signals."""

    logger.info("=" * 70)
    logger.info("LIVE TRADING ENGINE DEMO")
    logger.info("=" * 70)

    engine = LiveTradingEngine(
        capital=100000,
        paper=True,
        tickers=["NVDA", "AMD"],
    )

    # Simulate signals from predictions
    signals = [
        {
            "ticker": "NVDA",
            "signal": "BUY",
            "predicted_price": 195.00,
            "current_price": 187.90,
            "confidence": 0.82,
        },
        {
            "ticker": "AMD",
            "signal": "BUY",
            "predicted_price": 165.00,
            "current_price": 158.50,
            "confidence": 0.68,
        },
    ]

    logger.info("\nExecuting signals...")
    for sig in signals:
        result = engine.execute_signal(**sig)
        logger.info(f"Result: {result['status']}")

    # Get performance
    logger.info("\nPortfolio Performance:")
    perf = engine.get_performance()
    logger.info(f"  Portfolio Value: ${perf['portfolio_value']:,.2f}")
    logger.info(f"  Total Return: {perf['total_return_pct']:+.2f}%")
    logger.info(f"  Open Positions: {perf['open_positions']}")

    # Health check
    logger.info("\nSystem Health:")
    health = engine.health_check()
    for ticker, report in health["models"].items():
        logger.info(f"  {ticker}: {report.get('status', 'unknown')}")

    logger.info("\n" + "=" * 70)
    logger.info("LIVE TRADING ENGINE READY")
    logger.info("=" * 70)


if __name__ == "__main__":
    run_live_trading_demo()

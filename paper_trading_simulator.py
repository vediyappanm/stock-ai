#!/usr/bin/env python3
"""Step 4: Paper Trading Simulator - Live signal testing without real capital."""

import logging
from datetime import datetime, timedelta
from typing import Dict, List
import json
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


class PaperTradingSimulator:
    """Simulate live trading with prediction signals."""

    def __init__(self, capital: float = 100000, risk_per_trade: float = 0.02):
        self.capital = capital
        self.risk_per_trade = risk_per_trade
        self.positions: Dict = {}
        self.trades: List[Dict] = []
        self.cash = capital
        self.portfolio_value = capital
        self.start_time = datetime.now()

    def open_position(
        self,
        ticker: str,
        signal: str,  # "BUY" or "SELL"
        predicted_price: float,
        current_price: float,
        confidence: float,
        kelly_fraction: float = 0.062,  # 1/4 Kelly
    ) -> Dict:
        """
        Open a position based on prediction signal.

        Returns:
        - trade_id: unique trade ID
        - shares: shares allocated
        - entry_price: actual entry (current_price)
        - stop_loss: stop loss price
        - take_profit: take profit price
        """

        if ticker in self.positions:
            logger.warning(f"Already have position in {ticker}. Skipping.")
            return {}

        # Position sizing (Kelly-based)
        position_capital = self.cash * kelly_fraction
        shares = int(position_capital / current_price)

        if shares == 0:
            logger.warning(f"Insufficient capital for {ticker} position")
            return {}

        # Risk management
        if signal == "BUY":
            stop_loss = current_price * 0.85  # 15% downside
            take_profit = current_price * 1.30  # 30% upside
        else:  # SELL
            stop_loss = current_price * 1.15
            take_profit = current_price * 0.70

        # Record trade
        trade = {
            "trade_id": len(self.trades) + 1,
            "timestamp": datetime.now().isoformat(),
            "ticker": ticker,
            "signal": signal,
            "shares": shares,
            "entry_price": current_price,
            "predicted_price": predicted_price,
            "confidence": confidence,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "status": "OPEN",
        }

        self.positions[ticker] = trade
        self.trades.append(trade)
        self.cash -= shares * current_price

        logger.info(
            f"[{signal}] {ticker}: {shares} shares @ ${current_price:.2f} "
            f"(SL: ${stop_loss:.2f}, TP: ${take_profit:.2f}, Conf: {confidence:.1%})"
        )

        return trade

    def close_position(self, ticker: str, exit_price: float) -> Dict:
        """Close a position and record P/L."""

        if ticker not in self.positions:
            logger.warning(f"No position in {ticker}")
            return {}

        trade = self.positions[ticker]
        shares = trade["shares"]
        entry_price = trade["entry_price"]

        # Calculate P/L
        pnl = (exit_price - entry_price) * shares
        pnl_pct = (exit_price - entry_price) / entry_price * 100

        # Update cash
        self.cash += shares * exit_price

        # Record close
        trade["exit_price"] = exit_price
        trade["pnl"] = pnl
        trade["pnl_pct"] = pnl_pct
        trade["status"] = "CLOSED"
        trade["close_time"] = datetime.now().isoformat()

        del self.positions[ticker]

        logger.info(
            f"[CLOSE] {ticker}: Exit @ ${exit_price:.2f}, "
            f"P/L: ${pnl:.2f} ({pnl_pct:+.1f}%)"
        )

        return trade

    def check_stops(self, price_update: Dict[str, float]) -> List[str]:
        """Check if any positions hit stop loss or take profit."""

        triggered = []

        for ticker, trade in list(self.positions.items()):
            if ticker not in price_update:
                continue

            current_price = price_update[ticker]
            sl = trade["stop_loss"]
            tp = trade["take_profit"]

            if trade["signal"] == "BUY":
                if current_price <= sl:
                    self.close_position(ticker, sl)
                    logger.warning(f"[STOP LOSS] {ticker} hit at ${sl:.2f}")
                    triggered.append(f"{ticker}_SL")
                elif current_price >= tp:
                    self.close_position(ticker, tp)
                    logger.info(f"[TAKE PROFIT] {ticker} hit at ${tp:.2f}")
                    triggered.append(f"{ticker}_TP")

        return triggered

    def update_portfolio_value(self, price_update: Dict[str, float]) -> float:
        """Update portfolio value based on current prices."""

        self.portfolio_value = self.cash

        for ticker, trade in self.positions.items():
            if ticker in price_update:
                current_price = price_update[ticker]
                position_value = trade["shares"] * current_price
                self.portfolio_value += position_value

        return self.portfolio_value

    def get_performance_report(self) -> Dict:
        """Generate performance report."""

        closed_trades = [t for t in self.trades if t["status"] == "CLOSED"]

        if not closed_trades:
            return {
                "status": "no_closed_trades",
                "trades_open": len(self.positions),
                "portfolio_value": self.portfolio_value,
            }

        pnls = [t["pnl"] for t in closed_trades]
        pnl_pcts = [t["pnl_pct"] for t in closed_trades]

        wins = len([p for p in pnls if p > 0])
        losses = len([p for p in pnls if p < 0])
        win_rate = wins / len(closed_trades) * 100 if closed_trades else 0

        return {
            "total_trades": len(closed_trades),
            "win_rate_pct": win_rate,
            "wins": wins,
            "losses": losses,
            "total_pnl": sum(pnls),
            "avg_pnl_pct": sum(pnl_pcts) / len(pnl_pcts) if pnl_pcts else 0,
            "portfolio_value": self.portfolio_value,
            "total_return_pct": (self.portfolio_value - self.capital) / self.capital * 100,
        }

    def log_to_file(self, filename: str = "paper_trading_log.json") -> None:
        """Save trading log to file."""

        log_data = {
            "start_time": self.start_time.isoformat(),
            "current_time": datetime.now().isoformat(),
            "capital": self.capital,
            "portfolio_value": self.portfolio_value,
            "trades": self.trades,
            "performance": self.get_performance_report(),
        }

        with open(filename, "w") as f:
            json.dump(log_data, f, indent=2)

        logger.info(f"Trading log saved to {filename}")


def run_paper_trading_demo():
    """Demo: simulate paper trading over 48 hours."""

    print("\n" + "=" * 70)
    print("STEP 4: PAPER TRADING SIMULATOR DEMO")
    print("=" * 70)

    sim = PaperTradingSimulator(capital=100000, risk_per_trade=0.02)

    # Simulate signals
    logger.info("\n--- Day 1: Opening positions ---")

    # Trade 1: NVDA BUY signal
    sim.open_position(
        ticker="NVDA",
        signal="BUY",
        predicted_price=195.00,
        current_price=187.90,
        confidence=0.82,
        kelly_fraction=0.062,
    )

    # Trade 2: AMD BUY signal
    sim.open_position(
        ticker="AMD",
        signal="BUY",
        predicted_price=165.00,
        current_price=158.50,
        confidence=0.68,
        kelly_fraction=0.062,
    )

    logger.info(f"Portfolio Value: ${sim.portfolio_value:,.2f} | Cash: ${sim.cash:,.2f}")

    # Simulate price movements
    logger.info("\n--- Day 2: Price movements ---")

    price_update = {
        "NVDA": 191.50,  # +$3.60 (1.9%)
        "AMD": 160.25,   # +$1.75 (1.1%)
    }

    sim.update_portfolio_value(price_update)
    sim.check_stops(price_update)

    logger.info(f"Portfolio Value: ${sim.portfolio_value:,.2f}")

    # Close trades
    logger.info("\n--- Day 2: Closing positions ---")

    sim.close_position("NVDA", 191.50)
    sim.close_position("AMD", 160.25)

    # Performance report
    logger.info("\n--- PERFORMANCE REPORT ---")

    report = sim.get_performance_report()
    print("\nPaper Trading Results:")
    print(f"  Total Trades:        {report.get('total_trades', 0)}")
    print(f"  Win Rate:            {report.get('win_rate_pct', 0):.1f}%")
    print(f"  Total P/L:           ${report.get('total_pnl', 0):+,.2f}")
    print(f"  Avg P/L %:           {report.get('avg_pnl_pct', 0):+.2f}%")
    print(f"  Portfolio Value:     ${report.get('portfolio_value', 0):,.2f}")
    print(f"  Total Return:        {report.get('total_return_pct', 0):+.2f}%")

    sim.log_to_file("paper_trading_log.json")

    print("\n" + "=" * 70)
    print("STEP 4 RESULT: Paper Trading Simulator Ready")
    print("=" * 70)
    print("\nTo deploy live paper trading:")
    print("  1. Connect to Alpaca API or IBKR")
    print("  2. Update open_position() with live order execution")
    print("  3. Monitor signals in real-time via webhook")
    print("  4. Dashboard (Streamlit) displays live metrics")


if __name__ == "__main__":
    run_paper_trading_demo()

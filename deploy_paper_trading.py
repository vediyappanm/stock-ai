#!/usr/bin/env python3
"""Deploy paper trading live on Alpaca."""

import os
import sys
import logging
from datetime import datetime, timedelta
import time

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

from tools.alpaca_broker import AlpacaBroker
from tools.position_sizing import kelly_criterion
from pipelines.orchestrated_pipeline import execute_prediction_pipeline
from schemas.request_schemas import PredictRequest
from tools.model_monitor import get_global_monitor


class PaperTradingManager:
    """Manage live paper trading on Alpaca."""

    def __init__(self, capital: float = 100000, kelly_fraction: float = 0.062):
        """
        Initialize paper trading.

        Args:
        - capital: Starting capital
        - kelly_fraction: Position size (1/4 Kelly = 0.062)
        """
        self.capital = capital
        self.kelly_fraction = kelly_fraction
        self.broker = AlpacaBroker(paper=True)
        self.monitor = get_global_monitor()

        # Get account info
        account = self.broker.get_account()
        logger.info(
            f"Account initialized. Cash: ${account.get('cash', 0):,.2f}, "
            f"Buying Power: ${account.get('buying_power', 0):,.2f}"
        )

    def generate_signal(self, ticker: str) -> dict | None:
        """Generate trading signal for ticker."""

        try:
            logger.info(f"Generating signal for {ticker}...")

            request = PredictRequest(
                ticker=ticker,
                exchange="NASDAQ",
                include_sentiment=True,
                include_backtest=False,
                model_type="ensemble",
            )

            result = execute_prediction_pipeline(request)

            signal = {
                "ticker": ticker,
                "prediction": result.prediction,
                "lower_bound": result.lower_bound,
                "upper_bound": result.upper_bound,
                "confidence": result.confidence_level,
                "sentiment": result.sentiment.score if result.sentiment else 0.0,
            }

            return signal

        except Exception as e:
            logger.error(f"Signal generation failed for {ticker}: {e}")
            return None

    def execute_trade(self, ticker: str, signal: dict, current_price: float) -> bool:
        """Execute trade based on signal."""

        if not signal:
            return False

        prediction = signal["prediction"]
        confidence = signal["confidence"]

        # Determine signal
        if prediction > current_price * 1.01:  # >1% upside
            trade_signal = "BUY"
        elif prediction < current_price * 0.99:  # >1% downside
            trade_signal = "SELL"
        else:
            logger.info(f"No clear signal for {ticker} (prediction near current price)")
            return False

        # Only trade if confidence >0.7
        if confidence < 0.7:
            logger.warning(
                f"Skipping {ticker}: Low confidence ({confidence:.1%})"
            )
            return False

        # Position sizing
        account = self.broker.get_account()
        available_capital = account.get("cash", 0)
        position_size = available_capital * self.kelly_fraction
        qty = int(position_size / current_price)

        if qty == 0:
            logger.warning(f"Insufficient capital for {ticker} position")
            return False

        # Execute
        logger.info(
            f"[{trade_signal}] {ticker}: {qty} shares @ ${current_price:.2f} "
            f"(Prediction: ${prediction:.2f}, Confidence: {confidence:.1%})"
        )

        if trade_signal == "BUY":
            order = self.broker.place_market_order(ticker, qty, side="buy")
        else:
            order = self.broker.place_market_order(ticker, qty, side="sell")

        if "error" not in order:
            self.monitor.log_prediction(ticker, prediction, confidence=confidence)
            return True

        return False

    def monitor_positions(self) -> None:
        """Monitor open positions."""

        positions = self.broker.get_positions()

        if not positions:
            logger.info("No open positions")
            return

        logger.info(f"\n--- POSITIONS ({len(positions)}) ---")
        for pos in positions:
            logger.info(
                f"{pos['ticker']}: {pos['qty']} shares, "
                f"Value: ${pos['market_value']:,.2f}, "
                f"P/L: ${pos['unrealized_pl']:+,.2f} ({pos['unrealized_pl_pct']:+.1%})"
            )

    def run_trading_loop(self, tickers: list[str], duration_hours: int = 48) -> None:
        """Run main trading loop."""

        logger.info(f"Starting paper trading loop for {', '.join(tickers)}")
        logger.info(f"Duration: {duration_hours} hours")
        logger.info(f"Kelly fraction: {self.kelly_fraction:.1%}")

        start_time = datetime.now()
        end_time = start_time + timedelta(hours=duration_hours)

        iteration = 0

        while datetime.now() < end_time:
            iteration += 1
            logger.info(f"\n=== ITERATION {iteration} ({datetime.now()}) ===")

            for ticker in tickers:
                try:
                    # Get current price
                    from tools.fetch_data import fetch_ohlcv_data
                    from tools.ticker_resolver import resolve_ticker

                    resolved = resolve_ticker(stock=ticker, exchange="NASDAQ")
                    ohlcv = fetch_ohlcv_data(
                        ticker_symbol=resolved.full_symbol,
                        exchange=resolved.exchange,
                        days=5
                    )

                    current_price = float(ohlcv["Close"].iloc[-1])

                    # Generate signal
                    signal = self.generate_signal(ticker)

                    if signal:
                        self.execute_trade(ticker, signal, current_price)

                except Exception as e:
                    logger.error(f"Error processing {ticker}: {e}")

            # Monitor positions
            self.monitor_positions()

            # Check health
            health = self.monitor.get_all_health_reports()
            logger.info(f"System health: {health}")

            # Sleep before next iteration (15 minutes between signals)
            logger.info("Sleeping 15 minutes before next iteration...")
            time.sleep(900)

        logger.info(f"Paper trading session ended")
        logger.info(f"Total duration: {(datetime.now() - start_time).total_seconds() / 3600:.1f} hours")

        # Final report
        final_positions = self.broker.get_positions()
        if final_positions:
            logger.info("\n=== FINAL POSITIONS ===")
            for pos in final_positions:
                logger.info(
                    f"{pos['ticker']}: {pos['qty']} @ {pos['avg_fill_price']:.2f}, "
                    f"P/L: {pos['unrealized_pl_pct']:+.1%}"
                )


def main():
    """Main deployment."""

    print("\n" + "=" * 70)
    print("ALPACA PAPER TRADING - LIVE DEPLOYMENT")
    print("=" * 70)

    # Check env vars
    if not os.environ.get("APCA_API_KEY_ID"):
        print("\nERROR: Set APCA_API_KEY_ID environment variable")
        print("Get free paper trading keys: https://alpaca.markets/")
        sys.exit(1)

    # Create manager
    manager = PaperTradingManager(capital=100000, kelly_fraction=0.062)

    # Run trading loop
    tickers = ["NVDA", "AMD"]
    try:
        manager.run_trading_loop(tickers=tickers, duration_hours=48)
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)

    print("\n" + "=" * 70)
    print("PAPER TRADING DEPLOYMENT COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()

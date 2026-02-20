"""Telegram bot for trading alerts and monitoring."""

from __future__ import annotations

import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

try:
    import requests
    _HAS_REQUESTS = True
except Exception:
    _HAS_REQUESTS = False


class TelegramNotifier:
    """Send alerts via Telegram bot."""

    def __init__(self, bot_token: Optional[str] = None, chat_id: Optional[str] = None):
        """
        Initialize Telegram notifier.

        Args:
        - bot_token: Telegram bot token (or env TELEGRAM_BOT_TOKEN)
        - chat_id: Chat ID (or env TELEGRAM_CHAT_ID)
        """
        if not _HAS_REQUESTS:
            logger.warning("requests library not available for Telegram")
            return

        self.bot_token = bot_token or os.environ.get("TELEGRAM_BOT_TOKEN")
        self.chat_id = chat_id or os.environ.get("TELEGRAM_CHAT_ID")

        if not self.bot_token or not self.chat_id:
            logger.warning(
                "Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID environment variables for alerts"
            )
            self.enabled = False
        else:
            self.enabled = True
            logger.info("Telegram notifier enabled")

    def send_message(self, message: str) -> bool:
        """Send message to Telegram."""

        if not self.enabled:
            return False

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": message,
            "parse_mode": "HTML",
        }

        try:
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"Telegram message failed: {e}")
            return False

    def send_trade_signal(self, ticker: str, signal: str, price: float, confidence: float) -> bool:
        """Send trade signal alert."""

        message = (
            f"<b>[SIGNAL] {signal}</b>\n"
            f"Ticker: {ticker}\n"
            f"Price: ${price:.2f}\n"
            f"Confidence: {confidence:.1%}\n"
            f"Time: {self._timestamp()}"
        )

        return self.send_message(message)

    def send_order_fill(self, ticker: str, qty: int, price: float, order_id: str) -> bool:
        """Send order fill notification."""

        message = (
            f"<b>[ORDER FILLED]</b>\n"
            f"Ticker: {ticker}\n"
            f"Qty: {qty}\n"
            f"Price: ${price:.2f}\n"
            f"Order ID: <code>{order_id}</code>\n"
            f"Time: {self._timestamp()}"
        )

        return self.send_message(message)

    def send_position_alert(self, ticker: str, pnl: float, pnl_pct: float) -> bool:
        """Send position P/L alert."""

        emoji = "📈" if pnl > 0 else "📉"
        message = (
            f"{emoji} <b>[POSITION UPDATE]</b>\n"
            f"Ticker: {ticker}\n"
            f"P/L: ${pnl:+,.2f} ({pnl_pct:+.1%})\n"
            f"Time: {self._timestamp()}"
        )

        return self.send_message(message)

    def send_drift_alert(self, p_value: float, action: str) -> bool:
        """Send drift detection alert."""

        message = (
            f"<b>[DRIFT ALERT]</b>\n"
            f"KS Test p-value: {p_value:.4f}\n"
            f"Action: {action}\n"
            f"Time: {self._timestamp()}"
        )

        return self.send_message(message)

    def send_daily_report(self, metrics: dict) -> bool:
        """Send daily performance report."""

        message = (
            f"<b>[DAILY REPORT]</b>\n"
            f"Accuracy: {metrics.get('accuracy', 0):.1f}%\n"
            f"P/L: ${metrics.get('pnl', 0):+,.2f}\n"
            f"Max DD: {metrics.get('max_dd', 0):.1f}%\n"
            f"Trades: {metrics.get('trades', 0)}\n"
            f"Time: {self._timestamp()}"
        )

        return self.send_message(message)

    @staticmethod
    def _timestamp() -> str:
        """Get current timestamp."""
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# Global instance
_global_notifier = TelegramNotifier()


def get_notifier() -> TelegramNotifier:
    """Get global Telegram notifier."""
    return _global_notifier


def setup_telegram(bot_token: str, chat_id: str) -> None:
    """Setup Telegram bot."""
    global _global_notifier
    _global_notifier = TelegramNotifier(bot_token=bot_token, chat_id=chat_id)

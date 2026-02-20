"""Model health monitoring and automated retraining scheduler."""

from __future__ import annotations

from datetime import datetime, timedelta
import json
from pathlib import Path
from typing import Dict, List
import logging

logger = logging.getLogger(__name__)


class ModelHealthMonitor:
    """Track model performance, drift, and trigger retraining."""

    def __init__(self, ticker: str, history_file: Path | None = None):
        self.ticker = ticker
        self.history_file = history_file or Path(f"model_health_{ticker}.json")
        self.history: List[Dict] = self._load_history()

    def _load_history(self) -> List[Dict]:
        """Load historical metrics."""
        if self.history_file.exists():
            try:
                return json.loads(self.history_file.read_text())
            except Exception as e:
                logger.warning(f"Failed to load history: {e}")
                return []
        return []

    def _save_history(self) -> None:
        """Save metrics to file."""
        try:
            self.history_file.write_text(json.dumps(self.history, indent=2))
        except Exception as e:
            logger.error(f"Failed to save history: {e}")

    def log_prediction(
        self,
        predicted_price: float,
        actual_price: float | None = None,
        confidence: float = 0.5,
        accuracy_dir: float | None = None,
    ) -> None:
        """Log a prediction for monitoring."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "predicted": float(predicted_price),
            "actual": float(actual_price) if actual_price else None,
            "confidence": float(confidence),
            "directional_accuracy": float(accuracy_dir) if accuracy_dir else None,
        }

        self.history.append(entry)
        self._save_history()

    def get_recent_accuracy(self, days: int = 7) -> float:
        """Get average directional accuracy over recent period."""
        cutoff = datetime.now() - timedelta(days=days)
        recent = [
            e for e in self.history
            if e.get("directional_accuracy") is not None
            and datetime.fromisoformat(e["timestamp"]) > cutoff
        ]

        if not recent:
            return 0.0

        return sum(e["directional_accuracy"] for e in recent) / len(recent)

    def should_retrain(
        self,
        min_accuracy: float = 0.55,
        days_since_retrain: int = 7,
    ) -> bool:
        """Check if retraining is needed."""
        accuracy = self.get_recent_accuracy(days=7)

        if accuracy < min_accuracy:
            logger.warning(f"Accuracy {accuracy:.1%} < {min_accuracy:.1%}. Retrain needed.")
            return True

        return False

    def get_health_report(self) -> Dict:
        """Generate comprehensive health report."""
        if not self.history:
            return {"status": "no_data", "message": "No prediction history"}

        recent_7d = self.get_recent_accuracy(days=7)
        recent_30d = self.get_recent_accuracy(days=30)

        predictions_7d = len([e for e in self.history if e.get("directional_accuracy") is not None])
        last_update = self.history[-1]["timestamp"] if self.history else None

        return {
            "ticker": self.ticker,
            "last_update": last_update,
            "predictions_7d": predictions_7d,
            "accuracy_7d": f"{recent_7d:.1%}",
            "accuracy_30d": f"{recent_30d:.1%}",
            "status": "healthy" if recent_7d >= 0.55 else "degraded",
            "retrain_needed": self.should_retrain(),
        }


class ModelEnsembleMonitor:
    """Monitor all models in ensemble."""

    def __init__(self):
        self.monitors: Dict[str, ModelHealthMonitor] = {}

    def get_or_create(self, ticker: str) -> ModelHealthMonitor:
        """Get monitor for ticker, create if needed."""
        if ticker not in self.monitors:
            self.monitors[ticker] = ModelHealthMonitor(ticker)
        return self.monitors[ticker]

    def log_prediction(
        self,
        ticker: str,
        predicted_price: float,
        actual_price: float | None = None,
        confidence: float = 0.5,
    ) -> None:
        """Log prediction for ticker."""
        monitor = self.get_or_create(ticker)
        monitor.log_prediction(
            predicted_price=predicted_price,
            actual_price=actual_price,
            confidence=confidence,
        )

    def get_all_health_reports(self) -> Dict[str, Dict]:
        """Get health reports for all tickers."""
        return {ticker: monitor.get_health_report() for ticker, monitor in self.monitors.items()}

    def get_tickers_needing_retrain(self) -> List[str]:
        """Get list of tickers that need retraining."""
        return [ticker for ticker, monitor in self.monitors.items() if monitor.should_retrain()]


# Global instance
_global_monitor = ModelEnsembleMonitor()


def get_global_monitor() -> ModelEnsembleMonitor:
    """Get the global model monitor."""
    return _global_monitor

"""Advanced sentiment: aspect-based + earnings focus."""

from __future__ import annotations

from typing import List, Dict
import logging

logger = logging.getLogger(__name__)

try:
    from transformers import pipeline
    _HAS_TRANSFORMERS = True
except Exception:
    _HAS_TRANSFORMERS = False


def aspect_sentiment(text: str, aspects: List[str] | None = None) -> Dict[str, float]:
    """Analyze sentiment for specific aspects (earnings, competition, supply chain)."""
    if not _HAS_TRANSFORMERS:
        return {}

    if aspects is None:
        aspects = ["earnings", "competition", "supply chain", "innovation", "market share"]

    try:
        zero_shot = pipeline("zero-shot-classification", model="facebook/bart-large-mnli")
        scores = {}

        for aspect in aspects:
            premise = f"This text is about {aspect}"
            result = zero_shot(text, [premise], multi_class=False)
            scores[aspect] = float(result["scores"][0]) if result["scores"] else 0.0

        return scores
    except Exception as e:
        logger.debug(f"Aspect sentiment failed: {e}")
        return {}


def earnings_signal(headlines: List[str]) -> float:
    """Extract earnings-specific sentiment (pre-earnings jitter vs. beat/miss)."""
    if not headlines:
        return 0.0

    earnings_keywords = [
        "earnings", "beat", "miss", "guidance", "forecast", "q1", "q2", "q3", "q4",
        "revenue", "margin", "eps", "profit", "cash flow"
    ]

    bullish_keywords = ["beat", "raise", "strong", "growth", "record", "exceed"]
    bearish_keywords = ["miss", "lower", "weakness", "decline", "disappoint", "cut"]

    earnings_headlines = [h for h in headlines if any(kw in h.lower() for kw in earnings_keywords)]

    if not earnings_headlines:
        return 0.0

    bullish_count = sum(1 for h in earnings_headlines if any(kw in h.lower() for kw in bullish_keywords))
    bearish_count = sum(1 for h in earnings_headlines if any(kw in h.lower() for kw in bearish_keywords))

    total = bullish_count + bearish_count
    if total == 0:
        return 0.0

    signal = (bullish_count - bearish_count) / total
    return float(signal)


def supply_chain_risk(headlines: List[str], ticker: str = "NVDA") -> float:
    """Detect supply chain risks (TSMC, Samsung, Taiwan tensions for semiconductor stocks)."""
    if not headlines:
        return 0.0

    supply_chain_keywords = ["tsmc", "samsung", "taiwan", "supply chain", "fab", "shortage", "capacity"]
    risk_keywords = ["risk", "concern", "warning", "disruption", "attack", "tension", "sanction"]

    risk_headlines = [h for h in headlines if any(kw in h.lower() for kw in supply_chain_keywords)]

    if not risk_headlines:
        return 0.0

    risk_count = sum(1 for h in risk_headlines if any(kw in h.lower() for kw in risk_keywords))
    risk_signal = -risk_count / len(risk_headlines)  # Negative = bearish

    return float(risk_signal)


def sentiment_composite(
    finbert_score: float,
    aspect_scores: Dict[str, float] | None = None,
    earnings_signal_score: float = 0.0,
    supply_chain_score: float = 0.0,
    weights: Dict[str, float] | None = None,
) -> float:
    """Composite sentiment combining all signals."""
    if weights is None:
        weights = {
            "finbert": 0.5,
            "aspects": 0.2,
            "earnings": 0.2,
            "supply_chain": 0.1,
        }

    composite = finbert_score * weights["finbert"]

    if aspect_scores:
        aspect_avg = sum(aspect_scores.values()) / len(aspect_scores) if aspect_scores else 0.0
        composite += aspect_avg * weights["aspects"]

    composite += earnings_signal_score * weights["earnings"]
    composite += supply_chain_score * weights["supply_chain"]

    return float(composite)

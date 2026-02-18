"""News sentiment analysis using RSS + VADER."""

from __future__ import annotations

from typing import List

import httpx
try:
    import feedparser
except Exception:  # pragma: no cover - optional dependency fallback
    feedparser = None

try:
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
except Exception:  # pragma: no cover - optional dependency fallback
    SentimentIntensityAnalyzer = None

from config.settings import settings
from schemas.response_schemas import SentimentResult


def _fetch_feed(url: str, timeout_seconds: int) -> List[str]:
    if feedparser is None:
        return []
    try:
        with httpx.Client(timeout=timeout_seconds, follow_redirects=True) as client:
            response = client.get(url)
            response.raise_for_status()
            parsed = feedparser.parse(response.text)
            return [entry.get("title", "").strip() for entry in parsed.entries if entry.get("title")]
    except Exception:
        return []


def _label(score: float) -> str:
    if score > 0.05:
        return "positive"
    if score < -0.05:
        return "negative"
    return "neutral"


def analyze_sentiment(ticker: str) -> SentimentResult:
    """
    Analyze headline sentiment from Yahoo Finance RSS and Google News RSS.
    """
    analyzer = SentimentIntensityAnalyzer() if SentimentIntensityAnalyzer is not None else None
    sources = [
        settings.yahoo_rss_template.format(ticker=ticker),
        settings.google_news_template.format(ticker=ticker),
    ]

    headlines: List[str] = []
    for url in sources:
        headlines.extend(_fetch_feed(url, timeout_seconds=settings.sentiment_timeout))

    if not headlines:
        return SentimentResult(score=0.0, label="neutral", article_count=0, headlines=[], headline_details=[])

    if analyzer is None:
        return SentimentResult(score=0.0, label="neutral", article_count=len(headlines), headlines=headlines[:10], headline_details=[])

    details = []
    scores = []
    for text in headlines[:15]:
        score = analyzer.polarity_scores(text)["compound"]
        scores.append(score)
        details.append({"text": text, "score": score, "label": _label(score)})
        
    avg = float(sum(scores) / len(scores)) if scores else 0.0

    return SentimentResult(
        score=avg,
        label=_label(avg),
        article_count=len(headlines),
        headlines=[d["text"] for d in details],
        headline_details=details,
    )

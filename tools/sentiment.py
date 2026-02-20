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


def analyze_sentiment(ticker: str, research_catalysts: List[str] = None) -> SentimentResult:
    """
    Analyze headline sentiment from Yahoo Finance RSS, Google News RSS, and Research Agent.
    """
    analyzer = SentimentIntensityAnalyzer() if SentimentIntensityAnalyzer is not None else None
    
    # Resolve ticker for RSS
    base_ticker = ticker.split(".")[0]
    
    sources = [
        settings.yahoo_rss_template.format(ticker=ticker),
        settings.google_news_template.format(ticker=base_ticker),
    ]

    headlines: List[str] = []
    for url in sources:
        headlines.extend(_fetch_feed(url, timeout_seconds=settings.sentiment_timeout))

    # Add research catalysts if provided
    if research_catalysts:
        headlines.extend(research_catalysts)

    if not headlines:
        return SentimentResult(score=0.0, label="neutral", article_count=0, headlines=[], headline_details=[])

    if analyzer is None:
        return SentimentResult(score=0.0, label="neutral", article_count=len(headlines), headlines=headlines[:10], headline_details=[])

    details = []
    scores = []
    # Deduplicate and limit
    seen = set()
    unique_headlines = []
    for h in headlines:
        if h and h.lower() not in seen:
            seen.add(h.lower())
            unique_headlines.append(h)

    for text in unique_headlines[:20]:
        score = analyzer.polarity_scores(text)["compound"]
        scores.append(score)
        details.append({"text": text, "score": score, "label": _label(score)})
        
    avg = float(sum(scores) / len(scores)) if scores else 0.0

    return SentimentResult(
        score=avg,
        label=_label(avg),
        article_count=len(unique_headlines),
        headlines=[d["text"] for d in details],
        headline_details=details,
    )

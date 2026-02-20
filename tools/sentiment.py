"""News sentiment analysis using RSS + FinBERT (with VADER fallback)."""

from __future__ import annotations

from typing import List

import httpx
try:
    import feedparser
except Exception:  # pragma: no cover - optional dependency fallback
    feedparser = None

# FinBERT (primary)
try:
    from transformers import AutoTokenizer, AutoModelForSequenceClassification
    import torch
    _HAS_FINBERT = True
except Exception:  # pragma: no cover - optional dependency fallback
    _HAS_FINBERT = False
    AutoTokenizer = None
    AutoModelForSequenceClassification = None
    torch = None

# VADER (fallback)
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


def _analyze_with_finbert(texts: List[str]) -> List[float]:
    """Analyze sentiment using FinBERT (financial-domain transformer)."""
    try:
        tokenizer = AutoTokenizer.from_pretrained("yiyanghkust/finbert-tone")
        model = AutoModelForSequenceClassification.from_pretrained("yiyanghkust/finbert-tone")
        model.eval()

        scores = []
        with torch.no_grad():
            for text in texts[:20]:  # Limit to batch size
                inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=512)
                outputs = model(**inputs)
                logits = outputs.logits[0]
                probs = torch.softmax(logits, dim=-1).numpy()
                # FinBERT: [Negative, Neutral, Positive]
                score = float((probs[2] - probs[0]) / (probs[0] + probs[1] + probs[2]))
                scores.append(score)
        return scores
    except Exception:
        return []


def _analyze_with_vader(texts: List[str]) -> List[float]:
    """Analyze sentiment using VADER (fast, rule-based fallback)."""
    if SentimentIntensityAnalyzer is None:
        return []
    analyzer = SentimentIntensityAnalyzer()
    return [analyzer.polarity_scores(text)["compound"] for text in texts[:20]]


def analyze_sentiment(ticker: str, research_catalysts: List[str] = None) -> SentimentResult:
    """
    Analyze headline sentiment from Yahoo Finance RSS, Google News RSS.
    Primary: FinBERT for financial-domain accuracy.
    Fallback: VADER for speed.
    """
    base_ticker = ticker.split(".")[0]

    sources = [
        settings.yahoo_rss_template.format(ticker=ticker),
        settings.google_news_template.format(ticker=base_ticker),
    ]

    headlines: List[str] = []
    for url in sources:
        headlines.extend(_fetch_feed(url, timeout_seconds=settings.sentiment_timeout))

    if research_catalysts:
        headlines.extend(research_catalysts)

    if not headlines:
        return SentimentResult(score=0.0, label="neutral", article_count=0, headlines=[], headline_details=[])

    # Deduplicate
    seen = set()
    unique_headlines = []
    for h in headlines:
        if h and h.lower() not in seen:
            seen.add(h.lower())
            unique_headlines.append(h)

    # Try FinBERT first, fallback to VADER
    scores = []
    if _HAS_FINBERT:
        scores = _analyze_with_finbert(unique_headlines)

    if not scores:
        scores = _analyze_with_vader(unique_headlines)

    if not scores:
        return SentimentResult(
            score=0.0, label="neutral", article_count=len(unique_headlines),
            headlines=unique_headlines[:10], headline_details=[]
        )

    details = []
    for i, text in enumerate(unique_headlines[:20]):
        if i < len(scores):
            score = scores[i]
            details.append({"text": text, "score": score, "label": _label(score)})

    avg = float(sum(scores) / len(scores)) if scores else 0.0

    return SentimentResult(
        score=avg,
        label=_label(avg),
        article_count=len(unique_headlines),
        headlines=[d["text"] for d in details],
        headline_details=details,
    )

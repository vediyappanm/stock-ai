"""
Semantic Reranker
- Primary: cross-encoder/ms-marco-MiniLM-L-6-v2 (local, free)
- Fallback: Cohere Rerank API (if API key set)
- Last resort: Keyword scoring (fast, no dependencies)

Usage:
    from tools.reranker import rerank_chunks
    top_chunks = await rerank_chunks(chunks, query="NVDA earnings 2026", top_k=12)
"""
import asyncio
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

# Lazy-loaded cross-encoder model (loaded once on first use)
_cross_encoder = None
_cross_encoder_loaded = False


def _load_cross_encoder():
    """Lazily load cross-encoder model to avoid slow startup."""
    global _cross_encoder, _cross_encoder_loaded
    if _cross_encoder_loaded:
        return _cross_encoder

    try:
        from sentence_transformers import CrossEncoder
        _cross_encoder = CrossEncoder(
            "cross-encoder/ms-marco-MiniLM-L-6-v2",
            max_length=512,
        )
        logger.info("Reranker: cross-encoder loaded ✅")
    except ImportError:
        logger.warning("Reranker: sentence-transformers not installed, using keyword scoring")
        _cross_encoder = None
    except Exception as e:
        logger.warning(f"Reranker: cross-encoder load failed ({e}), using keyword scoring")
        _cross_encoder = None

    _cross_encoder_loaded = True
    return _cross_encoder


def _keyword_score(chunk_text: str, query: str, ticker: str) -> float:
    """
    Fast keyword-based relevance score.
    Used when no ML reranker is available.
    """
    score = 0.0
    text_lower = chunk_text.lower()
    query_terms = query.lower().split()
    ticker_lower = ticker.lower()

    # Ticker mention
    if ticker_lower in text_lower:
        score += 0.35

    # Query term matches
    matched = sum(1 for term in query_terms if term in text_lower)
    score += min(matched / max(len(query_terms), 1) * 0.4, 0.4)

    # Financial keywords
    financial_keywords = [
        "earnings", "revenue", "profit", "loss", "growth", "acquisition",
        "merger", "partnership", "guidance", "forecast", "dividend", "buyback",
        "ipo", "sec", "filing", "analyst", "upgrade", "downgrade", "target price",
    ]
    fin_matches = sum(1 for kw in financial_keywords if kw in text_lower)
    score += min(fin_matches * 0.05, 0.2)

    # Recency
    from datetime import datetime
    year = str(datetime.now().year)
    if year in chunk_text:
        score += 0.05

    return min(score, 1.0)


async def _rerank_with_cohere(
    chunks: list[dict], query: str, top_k: int
) -> list[dict] | None:
    """Try Cohere Rerank API if key is set."""
    api_key = os.getenv("COHERE_API_KEY", "")
    if not api_key:
        return None

    try:
        import cohere
        co = cohere.AsyncClient(api_key)
        docs = [c["text"][:512] for c in chunks]

        response = await co.rerank(
            model="rerank-english-v3.0",
            query=query,
            documents=docs,
            top_n=top_k,
        )

        reranked = []
        for hit in response.results:
            chunk = dict(chunks[hit.index])
            chunk["rerank_score"] = round(hit.relevance_score, 4)
            reranked.append(chunk)

        logger.info(f"Reranker: Cohere reranked {len(reranked)} chunks")
        return reranked

    except Exception as e:
        logger.warning(f"Reranker: Cohere failed ({e})")
        return None


async def _rerank_with_cross_encoder(
    chunks: list[dict], query: str, top_k: int
) -> list[dict] | None:
    """Rerank using local cross-encoder model."""
    model = await asyncio.to_thread(_load_cross_encoder)
    if not model:
        return None

    try:
        pairs = [(query, c["text"][:512]) for c in chunks]

        # Run inference in thread to avoid blocking event loop
        scores = await asyncio.to_thread(model.predict, pairs)

        for chunk, score in zip(chunks, scores):
            chunk["rerank_score"] = round(float(score), 4)

        sorted_chunks = sorted(chunks, key=lambda x: x["rerank_score"], reverse=True)
        logger.info(f"Reranker: cross-encoder reranked {len(sorted_chunks[:top_k])} chunks")
        return sorted_chunks[:top_k]

    except Exception as e:
        logger.warning(f"Reranker: cross-encoder inference failed ({e})")
        return None


async def rerank_chunks(
    chunks: list[dict[str, Any]],
    query: str,
    ticker: str = "",
    top_k: int = 12,
) -> list[dict[str, Any]]:
    """
    Rerank chunks by relevance to query.

    Priority:
    1. Cohere Rerank API (best quality, requires COHERE_API_KEY)
    2. Cross-encoder/ms-marco (good quality, local, no API key)
    3. Keyword scoring (fast, always works)

    Args:
        chunks: List of chunk dicts with 'text' key
        query: Search query / topic string
        ticker: Stock ticker for boosting
        top_k: Number of top chunks to return

    Returns:
        Reranked chunks (top_k), each with 'rerank_score' added
    """
    if not chunks:
        return []

    # Try Cohere first (best quality)
    result = await _rerank_with_cohere(chunks, query, top_k)
    if result:
        return result

    # Try cross-encoder (good quality, local)
    result = await _rerank_with_cross_encoder(chunks, query, top_k)
    if result:
        return result

    # Keyword fallback (always works)
    logger.info("Reranker: using keyword scoring fallback")
    for chunk in chunks:
        chunk["rerank_score"] = _keyword_score(chunk["text"], query, ticker)

    sorted_chunks = sorted(chunks, key=lambda x: x["rerank_score"], reverse=True)
    return sorted_chunks[:top_k]

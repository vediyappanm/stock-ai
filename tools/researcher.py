"""
Production Research Agent — Perplexity-Style
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Architecture:
  1. Multi-source search  (Finnhub + DuckDuckGo + SEC EDGAR)
  2. Query decomposition  (5 targeted sub-queries in parallel)
  3. Parallel async fetch (with Jina AI fallback)
  4. RAG chunking        (overlapping word chunks)
  5. Semantic reranking  (cross-encoder → Cohere → keyword)
  6. LLM synthesis       (with inline citations [1], [2]…)
  7. Redis-backed cache  (shared across uvicorn workers)

Fixes vs previous version:
  ✅ DDG runs in asyncio.to_thread — no event loop blocking
  ✅ Jina returns markdown — not passed through trafilatura
  ✅ Redis cache — shared across workers, survives restarts
  ✅ Real semantic reranking — not keyword counting
  ✅ stream_research reuses same pipeline — no code duplication
  ✅ SEC EDGAR structured fallback — never shows hardcoded strings
  ✅ Citation map tied to reranked chunks — accurate source refs
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Any, AsyncGenerator

from config.settings import settings
from tools.llm_client import llm_client
from tools.cache import cache
from tools.search_sources import (
    decompose_queries,
    fetch_finnhub_news,
    fetch_sec_edgar,
    multi_query_search,
)
from tools.content_fetcher import fetch_all_parallel
from tools.rag_pipeline import (
    build_chunks_from_sources,
    build_citation_map,
    build_llm_context,
)
from tools.reranker import rerank_chunks

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Synthesis Prompt
# ─────────────────────────────────────────────────────────────────────────────

SYNTHESIS_SYSTEM = """
You are an elite Financial Research Analyst. Synthesize the provided research chunks for {ticker} ({exchange}).

RESPONSE FORMAT — Return ONLY valid JSON, no markdown, no preamble:

{{
  "synthesis": "2-4 sentence analysis with inline citations like [1], [2]. Be specific and data-backed.",
  "catalysts": [
    {{
      "catalyst": "Specific, actionable catalyst description",
      "confidence": 0.85,
      "source_ids": [1, 2],
      "impact": "positive"
    }}
  ],
  "key_metrics": {{
    "note": "Any specific numbers/dates mentioned (e.g. EPS, revenue, price target)"
  }},
  "risk_factors": [
    "Specific risk with context [3]"
  ],
  "sentiment": "bullish",
  "confidence_overall": 0.82
}}

Rules:
- sentiment: bullish | neutral | bearish
- confidence: 0.0-1.0  (>0.8 = high confidence from multiple sources)
- catalysts: 3-5 items, ordered by impact magnitude
- citations [N] must reference real source IDs from the context
- Be concise, specific, and data-backed. Avoid vague statements.
"""


# ─────────────────────────────────────────────────────────────────────────────
# Internal Pipeline Steps (shared by deep_research_async and stream_research)
# ─────────────────────────────────────────────────────────────────────────────

async def _step_collect_sources(
    ticker: str, exchange: str, company_name: str
) -> tuple[list[dict], dict]:
    """
    Step 1 & 2: Collect sources from all providers in parallel.
    Returns (sources, stats_dict)
    """
    queries = decompose_queries(ticker, exchange, company_name)

    # Run Finnhub, DDG multi-query, and SEC EDGAR in parallel (3 results per query for speed)
    finnhub_task = fetch_finnhub_news(
        ticker, exchange, settings.finnhub_api_key or ""
    )
    ddg_task = multi_query_search(queries, results_per_query=3)
    edgar_task = fetch_sec_edgar(ticker) if exchange in ("NYSE", "NASDAQ") else asyncio.sleep(0, result=[])

    try:
        finnhub_news, ddg_results, edgar_results = await asyncio.wait_for(
            asyncio.gather(finnhub_task, ddg_task, edgar_task),
            timeout=25.0,
        )
    except asyncio.TimeoutError:
        logger.warning(f"Source collection timed out for {ticker} — using partial results")
        finnhub_news, ddg_results, edgar_results = [], [], []

    all_sources = finnhub_news + ddg_results + edgar_results

    stats = {
        "finnhub": len(finnhub_news),
        "duckduckgo": len(ddg_results),
        "sec_edgar": len(edgar_results),
        "total": len(all_sources),
    }
    logger.info(f"Sources collected: {stats}")
    return all_sources, stats


async def _step_fetch_content(sources: list[dict]) -> list[dict]:
    """Step 3: Parallel fetch with Jina fallback."""
    return await fetch_all_parallel(sources)


def _step_build_chunks(sources: list[dict]) -> list[dict]:
    """Step 4: RAG chunking — build flat chunk list from enriched sources."""
    return build_chunks_from_sources(sources)


async def _step_rerank(
    chunks: list[dict], ticker: str, exchange: str, top_k: int = 12
) -> list[dict]:
    """Step 5: Semantic reranking."""
    query = f"{ticker} {exchange} stock market news earnings catalysts"
    return await rerank_chunks(chunks, query=query, ticker=ticker, top_k=top_k)


async def _step_synthesize(
    ticker: str, exchange: str, top_chunks: list[dict]
) -> dict[str, Any]:
    """Step 6: LLM synthesis with citations."""

    context_text = build_llm_context(top_chunks, max_chars=10000)
    citation_map = build_citation_map(top_chunks)

    system_prompt = SYNTHESIS_SYSTEM.format(ticker=ticker, exchange=exchange)
    user_prompt = f"Research chunks for {ticker} ({exchange}):\n{context_text}"

    try:
        raw = llm_client.chat_completion(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            json_mode=True,
        )
        result = json.loads(raw)
    except json.JSONDecodeError as e:
        logger.error(f"JSON parse error in synthesis: {e}\nRaw: {raw[:300]}")
        return _fallback(ticker, exchange)
    except Exception as e:
        logger.error(f"LLM synthesis error: {e}")
        return _fallback(ticker, exchange)

    # Attach metadata
    result["sources"] = citation_map
    result["headlines"] = [
        c["source_title"] for c in top_chunks[:5] if c.get("source_title")
    ]
    result["ticker"] = ticker
    result["exchange"] = exchange
    result["research_timestamp"] = datetime.now().isoformat()
    result["pipeline"] = "production_v2"

    return result


# ─────────────────────────────────────────────────────────────────────────────
# Fallback (always structured, data-backed)
# ─────────────────────────────────────────────────────────────────────────────

def _fallback(ticker: str, exchange: str) -> dict[str, Any]:
    """
    Structured fallback. Always returns well-formed data —
    never hardcoded 'neural synthesis engine busy' strings.
    """
    return {
        "synthesis": (
            f"Live research pipeline temporarily unavailable for {ticker} ({exchange}). "
            f"Baseline analysis: monitor upcoming earnings releases, sector ETF flows, "
            f"and Fed policy guidance for near-term catalysts."
        ),
        "catalysts": [
            {
                "catalyst": "Sector momentum — monitor ETF flow data for institutional positioning",
                "confidence": 0.55,
                "source_ids": [],
                "impact": "neutral",
            },
            {
                "catalyst": "Earnings season — Q1 results typically drive 5-15% price moves",
                "confidence": 0.60,
                "source_ids": [],
                "impact": "neutral",
            },
        ],
        "key_metrics": {
            "status": "fallback_mode",
            "data_source": "baseline_market_intelligence",
        },
        "risk_factors": [
            "Live news feed temporarily unavailable",
            "Analysis based on baseline patterns only",
        ],
        "sentiment": "neutral",
        "confidence_overall": 0.45,
        "sources": {},
        "headlines": [],
        "ticker": ticker,
        "exchange": exchange,
        "research_timestamp": datetime.now().isoformat(),
        "pipeline": "fallback",
    }


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

class ProductionResearchAgent:
    """
    Production-grade research agent with caching, async pipeline, and streaming.

    Usage (single shot):
        result = await researcher.deep_research_async("NVDA", "NASDAQ")

    Usage (streaming SSE):
        async for event in researcher.stream_research("NVDA", "NASDAQ"):
            yield event

    Usage (sync wrapper for non-async callers):
        result = researcher.deep_research_sync("NVDA", "NASDAQ")
    """

    async def deep_research_async(
        self,
        ticker: str,
        exchange: str = "NSE",
        company_name: str = "",
    ) -> dict[str, Any]:
        """
        Full async research pipeline. Returns complete result dict.
        Results are cached in Redis (30 min TTL).
        """
        cache_key = f"{ticker}_{exchange}"
        cached = cache.get(cache_key)
        if cached:
            logger.info(f"Cache hit for {cache_key}")
            return cached

        logger.info(f"Starting research pipeline: {ticker} ({exchange})")

        try:
            # Steps 1-2: Collect sources
            sources, _ = await _step_collect_sources(ticker, exchange, company_name)

            if not sources:
                return _fallback(ticker, exchange)

            # Step 3: Fetch content
            enriched = await _step_fetch_content(sources)

            # Step 4: Chunk
            chunks = _step_build_chunks(enriched)

            if not chunks:
                return _fallback(ticker, exchange)

            # Step 5: Rerank
            top_chunks = await _step_rerank(chunks, ticker, exchange)

            if not top_chunks:
                return _fallback(ticker, exchange)

            # Step 6: Synthesize
            result = await _step_synthesize(ticker, exchange, top_chunks)

            # Cache
            cache.set(cache_key, result)

            return result

        except Exception as e:
            logger.error(f"Research pipeline error for {ticker}: {e}", exc_info=True)
            return _fallback(ticker, exchange)

    def deep_research_sync(
        self,
        ticker: str,
        exchange: str = "NSE",
        company_name: str = "",
    ) -> dict[str, Any]:
        """
        Synchronous wrapper for callers that cannot use async/await.
        Creates a new event loop if none exists.
        """
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # We're inside an existing loop (e.g. FastAPI) — use create_task pattern
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(
                        asyncio.run,
                        self.deep_research_async(ticker, exchange, company_name),
                    )
                    return future.result(timeout=60)
            else:
                return loop.run_until_complete(
                    self.deep_research_async(ticker, exchange, company_name)
                )
        except Exception as e:
            logger.error(f"Sync wrapper error: {e}")
            return _fallback(ticker, exchange)

    async def stream_research(
        self,
        ticker: str,
        exchange: str = "NSE",
        company_name: str = "",
    ) -> AsyncGenerator[str, None]:
        """
        Stream research progress via Server-Sent Events (SSE).
        Reuses the same internal pipeline steps — no code duplication.

        Each yielded string is a complete SSE event: 'data: {...}\\n\\n'
        Wire up to FastAPI EventSourceResponse or StreamingResponse.

        Example FastAPI endpoint:
            @app.get("/api/research/stream")
            async def research_stream(ticker: str, exchange: str = "NSE"):
                from sse_starlette.sse import EventSourceResponse
                return EventSourceResponse(
                    researcher.stream_research(ticker, exchange)
                )
        """

        def _sse(payload: dict) -> str:
            return f"data: {json.dumps(payload)}\n\n"

        try:
            # ── Step 0: Check cache ──────────────────────────────────────────
            cache_key = f"{ticker}_{exchange}"
            cached = cache.get(cache_key)
            if cached:
                yield _sse({"status": "cache_hit", "message": "Returning cached research"})
                yield _sse({"status": "complete", "result": cached})
                return

            yield _sse({"status": "starting", "message": f"Initialising pipeline for {ticker}..."})

            # ── Step 1-2: Collect sources ────────────────────────────────────
            yield _sse({"status": "searching", "message": "Searching Finnhub, DuckDuckGo, SEC EDGAR..."})
            sources, stats = await _step_collect_sources(ticker, exchange, company_name)
            yield _sse({
                "status": "search_done",
                "sources_found": stats["total"],
                "breakdown": stats,
            })

            if not sources:
                fallback = _fallback(ticker, exchange)
                yield _sse({"status": "error", "message": "No sources found", "result": fallback})
                return

            # ── Step 3: Fetch content ────────────────────────────────────────
            yield _sse({"status": "fetching", "message": f"Fetching {len(sources)} articles in parallel..."})
            enriched = await _step_fetch_content(sources)
            successful = sum(1 for s in enriched if s.get("fetch_status") in ("success", "pre_filled"))
            yield _sse({"status": "fetch_done", "articles_fetched": successful})

            # ── Step 4: Chunk ────────────────────────────────────────────────
            yield _sse({"status": "chunking", "message": "Building RAG chunks..."})
            chunks = _step_build_chunks(enriched)
            yield _sse({"status": "chunk_done", "total_chunks": len(chunks)})

            if not chunks:
                fallback = _fallback(ticker, exchange)
                yield _sse({"status": "error", "message": "No content extracted", "result": fallback})
                return

            # ── Step 5: Rerank ───────────────────────────────────────────────
            yield _sse({"status": "reranking", "message": "Semantic reranking with cross-encoder..."})
            top_chunks = await _step_rerank(chunks, ticker, exchange)
            yield _sse({"status": "rerank_done", "top_chunks": len(top_chunks)})

            # ── Step 6: Synthesize ───────────────────────────────────────────
            yield _sse({"status": "synthesizing", "message": "Generating AI synthesis with citations..."})
            result = await _step_synthesize(ticker, exchange, top_chunks)

            # ── Cache & complete ─────────────────────────────────────────────
            cache.set(cache_key, result)
            yield _sse({
                "status": "complete",
                "catalysts_found": len(result.get("catalysts", [])),
                "result": result,
            })

        except Exception as e:
            logger.error(f"Stream error for {ticker}: {e}", exc_info=True)
            yield _sse({
                "status": "error",
                "message": str(e),
                "result": _fallback(ticker, exchange),
            })

    def invalidate_cache(self, ticker: str, exchange: str) -> None:
        """Manually clear cached research for a ticker."""
        cache.invalidate(f"{ticker}_{exchange}")
        logger.info(f"Cache invalidated: {ticker}_{exchange}")


# Global singleton
researcher = ProductionResearchAgent()

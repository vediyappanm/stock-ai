"""
FastAPI Research Endpoints
- POST /api/research          → Full result (cached, async)
- GET  /api/research/stream   → SSE streaming with live progress
- DELETE /api/research/cache  → Invalidate cache for a ticker
"""
import logging
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from tools.researcher import researcher

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/research", tags=["research"])


# ─────────────────────────────────────────────
# Request / Response Models
# ─────────────────────────────────────────────

class ResearchRequest(BaseModel):
    ticker: str = Field(..., examples=["NVDA"], description="Stock ticker symbol")
    exchange: str = Field("NASDAQ", examples=["NASDAQ"], description="Exchange: NYSE, NASDAQ, NSE, BSE")
    company_name: str = Field("", examples=["Nvidia Corporation"], description="Optional company name for better search")


class CatalystItem(BaseModel):
    catalyst: str
    confidence: float
    source_ids: list[int]
    impact: str


class ResearchResponse(BaseModel):
    ticker: str
    exchange: str
    synthesis: str
    catalysts: list[CatalystItem]
    key_metrics: dict
    risk_factors: list[str]
    sentiment: str
    confidence_overall: float
    sources: dict
    headlines: list[str]
    research_timestamp: str
    pipeline: str


# ─────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────

@router.post("", response_model=ResearchResponse, summary="Full research (cached)")
async def deep_research(request: ResearchRequest):
    """
    Run the full Perplexity-style research pipeline.

    - Multi-source search (Finnhub + DuckDuckGo + SEC EDGAR)
    - Parallel async fetch with Jina AI fallback
    - RAG chunking + semantic reranking
    - LLM synthesis with inline citations

    Results are cached in Redis for 30 minutes.
    """
    try:
        result = await researcher.deep_research_async(
            ticker=request.ticker.upper(),
            exchange=request.exchange.upper(),
            company_name=request.company_name,
        )
        return result
    except Exception as e:
        logger.error(f"Research endpoint error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stream", summary="Streaming research (SSE)")
async def stream_research(
    ticker: str = Query(..., examples=["NVDA"]),
    exchange: str = Query("NASDAQ", examples=["NASDAQ"]),
    company_name: str = Query("", examples=["Nvidia Corporation"]),
):
    """
    Stream research progress via Server-Sent Events.

    Frontend can listen with EventSource:
    ```js
    const es = new EventSource(`/api/research/stream?ticker=NVDA&exchange=NASDAQ`);
    es.onmessage = (e) => {
      const event = JSON.parse(e.data);
      if (event.status === 'complete') {
        showResult(event.result);
        es.close();
      } else {
        updateProgress(event.message);
      }
    };
    ```

    Events emitted (in order):
    - starting
    - searching
    - search_done
    - fetching
    - fetch_done
    - chunking
    - chunk_done
    - reranking
    - rerank_done
    - synthesizing
    - complete  (contains full result)
    - error     (contains fallback result)
    """
    return StreamingResponse(
        researcher.stream_research(
            ticker=ticker.upper(),
            exchange=exchange.upper(),
            company_name=company_name,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
            "Connection": "keep-alive",
        },
    )


@router.delete("/cache", summary="Invalidate research cache")
def invalidate_cache(
    ticker: str = Query(..., examples=["NVDA"]),
    exchange: str = Query("NASDAQ", examples=["NASDAQ"]),
):
    """
    Manually invalidate cached research for a ticker.
    Useful after major news events or when fresh data is required.
    """
    researcher.invalidate_cache(ticker.upper(), exchange.upper())
    return {"message": f"Cache invalidated for {ticker.upper()} ({exchange.upper()})"}

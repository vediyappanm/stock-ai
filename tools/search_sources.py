"""
Multi-Source Search Module
- DuckDuckGo (primary, free)
- Finnhub News (US stocks, requires API key)
- SEC EDGAR (fallback for US stocks, no API key needed)

All search functions are truly async (no blocking the event loop).
"""
import asyncio
import httpx
import logging
from datetime import datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)

EDGAR_BASE = "https://efts.sec.gov/LATEST/search-index"
FINNHUB_BASE = "https://finnhub.io/api/v1"


# ─────────────────────────────────────────────
# DuckDuckGo
# ─────────────────────────────────────────────

async def search_duckduckgo(query: str, max_results: int = 5) -> list[dict]:
    """
    Async DuckDuckGo text search.
    Runs DDGS in a thread to avoid blocking the event loop.
    Uses a pinned browser profile to avoid 'impersonate not exist' warnings.
    """
    def _sync_search():
        try:
            try:
                from ddgs import DDGS
            except ImportError:
                from duckduckgo_search import DDGS

            # Use default settings to avoid impersonate issues
            try:
                with DDGS() as ddgs:
                    return list(ddgs.text(query, max_results=max_results, timelimit="w"))
            except Exception as inner_e:
                # Fallback without timelimit if that fails
                logger.debug(f"DDG timelimit failed, trying without: {inner_e}")
                with DDGS() as ddgs:
                    return list(ddgs.text(query, max_results=max_results))
        except Exception as e:
            logger.debug(f"DDG search error for '{query}': {e}")
            return []

    try:
        results = await asyncio.wait_for(asyncio.to_thread(_sync_search), timeout=3.0)  # Reduced from 10s
    except asyncio.TimeoutError:
        logger.debug(f"DDG search timeout for '{query}'")
        results = []

    formatted = [
        {
            "title": r.get("title", ""),
            "url": r.get("href", ""),
            "snippet": r.get("body", ""),
            "source": "duckduckgo",
            "content": r.get("body", ""),  # Snippet as initial content
        }
        for r in results
        if r.get("href")
    ]
    logger.debug(f"DDG: {len(formatted)} results for '{query}'")
    return formatted


async def multi_query_search(queries: list[str], results_per_query: int = 4) -> list[dict]:
    """
    Run multiple DDG queries in parallel and deduplicate by URL.
    """
    tasks = [search_duckduckgo(q, results_per_query) for q in queries]
    all_lists = await asyncio.gather(*tasks)

    seen_urls: set[str] = set()
    deduped: list[dict] = []

    for result_list in all_lists:
        for result in result_list:
            url = result.get("url", "")
            if url and url not in seen_urls:
                deduped.append(result)
                seen_urls.add(url)

    logger.info(f"Multi-query: {len(deduped)} unique results from {len(queries)} queries")
    return deduped


def decompose_queries(ticker: str, exchange: str, company_name: str = "") -> list[str]:
    """
    Break a single ticker into 3 targeted sub-queries (reduced for speed).
    """
    name = company_name or ticker
    year = datetime.now().year

    return [
        f"{ticker} stock news {year}",
        f"{name} earnings revenue forecast",
        f"{ticker} price target analyst upgrade downgrade",
    ]


# ─────────────────────────────────────────────
# Finnhub
# ─────────────────────────────────────────────

async def fetch_finnhub_news(
    ticker: str,
    exchange: str,
    api_key: str,
    days_back: int = 7,
) -> list[dict]:
    """
    Fetch Finnhub company news (US stocks only on free tier).
    Returns empty list silently for Indian/unsupported stocks.
    """
    if not api_key or exchange not in ("NYSE", "NASDAQ"):
        return []

    end_date = datetime.now()
    start_date = end_date - timedelta(days=days_back)

    url = (
        f"{FINNHUB_BASE}/company-news?"
        f"symbol={ticker}"
        f"&from={start_date.strftime('%Y-%m-%d')}"
        f"&to={end_date.strftime('%Y-%m-%d')}"
        f"&token={api_key}"
    )

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, timeout=10)

        if resp.status_code != 200:
            logger.debug(f"Finnhub {resp.status_code} for {ticker}")
            return []

        items = resp.json()
        results = []
        for item in items[:8]:
            headline = item.get("headline", "").strip()
            if not headline:
                continue
            results.append({
                "title": headline,
                "url": item.get("url", ""),
                "snippet": item.get("summary", ""),
                "content": item.get("summary", ""),  # Use summary directly
                "source": "finnhub",
                "timestamp": item.get("datetime", ""),
            })

        logger.info(f"Finnhub: {len(results)} articles for {ticker}")
        return results

    except Exception as e:
        logger.debug(f"Finnhub fetch error for {ticker}: {e}")
        return []


# ─────────────────────────────────────────────
# SEC EDGAR (structured fallback for US stocks)
# ─────────────────────────────────────────────

async def fetch_sec_edgar(ticker: str, max_results: int = 5) -> list[dict]:
    """
    Fetch latest SEC filings for a ticker from EDGAR full-text search.
    Free, no API key, works for all US-listed companies.
    Good structured fallback when other sources fail.
    """
    url = (
        f"https://efts.sec.gov/LATEST/search-index?q=%22{ticker}%22"
        f"&dateRange=custom&startdt={datetime.now().year}-01-01"
        f"&forms=8-K,10-Q,10-K&hits.hits._source=period_of_report,display_date_filed,"
        f"file_date,form_type,entity_name,file_num,period_of_report"
    )

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, timeout=10)

        if resp.status_code != 200:
            return []

        data = resp.json()
        hits = data.get("hits", {}).get("hits", [])

        results = []
        for hit in hits[:max_results]:
            src = hit.get("_source", {})
            form_type = src.get("form_type", "")
            entity = src.get("entity_name", ticker)
            date = src.get("file_date", "")
            accession = hit.get("_id", "").replace(":", "-")

            doc_url = f"https://www.sec.gov/Archives/edgar/data/{accession}.txt"
            title = f"{entity} SEC Filing: {form_type} ({date})"

            results.append({
                "title": title,
                "url": doc_url,
                "snippet": f"{form_type} filing by {entity} on {date}",
                "content": f"{form_type} filing by {entity} on {date}",
                "source": "sec_edgar",
                "timestamp": date,
            })

        logger.info(f"SEC EDGAR: {len(results)} filings for {ticker}")
        return results

    except Exception as e:
        logger.debug(f"SEC EDGAR fetch error for {ticker}: {e}")
        return []

"""
Async Content Fetcher
- Fetches URLs in parallel with semaphore throttling
- Jina AI fallback for JS-rendered / paywalled pages
- Correctly handles Jina markdown vs raw HTML
"""
import asyncio
import logging
import re
from typing import Optional
import httpx

logger = logging.getLogger(__name__)

JINA_BASE = "https://r.jina.ai"
REQUEST_TIMEOUT = 4        # Reduced from 12s — skip slow sources fast
MAX_CONCURRENT = 5         # Reduced from 8 — avoid thundering herd
MAX_CONTENT_CHARS = 1500   # Reduced from 3000 — enough signal, less noise


async def _fetch_direct(client: httpx.AsyncClient, url: str) -> Optional[str]:
    """Try direct HTTP fetch and extract text via trafilatura."""
    try:
        resp = await client.get(url, timeout=REQUEST_TIMEOUT, follow_redirects=True)
        if resp.status_code == 200:
            html = resp.text
            try:
                import trafilatura
                text = trafilatura.extract(
                    html,
                    no_fallback=False,
                    include_comments=False,
                    include_tables=True,
                )
                if text and len(text) > 150:
                    return text[:MAX_CONTENT_CHARS]
            except Exception:
                pass

            # Basic HTML strip fallback
            text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL)
            text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL)
            text = re.sub(r"<[^>]+>", " ", text)
            text = re.sub(r"\s+", " ", text).strip()
            return text[:MAX_CONTENT_CHARS] if len(text) > 150 else None
    except Exception as e:
        logger.debug(f"Direct fetch failed {url}: {e}")
    return None


async def _fetch_jina(client: httpx.AsyncClient, url: str) -> Optional[str]:
    """
    Fetch via Jina AI reader (r.jina.ai/{url}).
    Jina returns clean markdown — do NOT pass through trafilatura.
    """
    try:
        jina_url = f"{JINA_BASE}/{url}"
        headers = {"Accept": "text/markdown"}
        resp = await client.get(jina_url, timeout=REQUEST_TIMEOUT, headers=headers)
        if resp.status_code == 200:
            text = resp.text.strip()
            if len(text) > 150:
                logger.debug(f"Jina fallback success: {url}")
                return text[:MAX_CONTENT_CHARS]
    except Exception as e:
        logger.debug(f"Jina fallback failed {url}: {e}")
    return None


async def fetch_single(client: httpx.AsyncClient, url: str) -> Optional[str]:
    """
    Fetch a URL: try direct first, then Jina AI.
    Returns clean text content or None.
    """
    if not url or not url.startswith("http"):
        return None

    content = await _fetch_direct(client, url)
    if content:
        return content

    content = await _fetch_jina(client, url)
    return content


async def fetch_all_parallel(sources: list[dict]) -> list[dict]:
    """
    Fetch content from all sources in parallel.
    Each source dict should have a 'url' key.
    Adds 'content' and 'fetch_status' to each source in-place.

    Args:
        sources: List of source dicts with 'url' key

    Returns:
        Enriched sources with 'content' added
    """
    semaphore = asyncio.Semaphore(MAX_CONCURRENT)

    async def bounded_fetch(source: dict) -> dict:
        async with semaphore:
            url = source.get("url", "")
            if not url:
                source["fetch_status"] = "no_url"
                return source

            # If source already has good content (e.g., Finnhub summary), skip fetch
            existing = source.get("content", "")
            if existing and len(existing) > 200:
                source["fetch_status"] = "pre_filled"
                return source

            content = await fetch_single(client, url)
            if content:
                source["content"] = content
                source["fetch_status"] = "success"
            else:
                # Use snippet as last resort
                snippet = source.get("snippet", "")
                source["content"] = snippet
                source["fetch_status"] = "snippet_only" if snippet else "failed"

            return source

    async with httpx.AsyncClient(
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
            )
        }
    ) as client:
        tasks = [bounded_fetch(source) for source in sources]
        enriched = await asyncio.gather(*tasks, return_exceptions=False)

    successful = sum(1 for s in enriched if s.get("fetch_status") == "success")
    pre_filled = sum(1 for s in enriched if s.get("fetch_status") == "pre_filled")
    logger.info(
        f"Fetch complete: {successful} fetched, {pre_filled} pre-filled, "
        f"{len(enriched) - successful - pre_filled} failed"
    )

    return list(enriched)

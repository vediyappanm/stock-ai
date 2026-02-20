"""
RAG Pipeline Utilities
- Content chunking with overlap
- Source-tracked chunk building
- Citation map construction
"""
from typing import Any


def chunk_text(text: str, chunk_size: int = 400, overlap: int = 80) -> list[str]:
    """
    Split text into overlapping word-level chunks.
    Overlap ensures context continuity between adjacent chunks.

    Args:
        text: Raw text to chunk
        chunk_size: Words per chunk
        overlap: Overlapping words between consecutive chunks

    Returns:
        List of text chunks (only meaningful ones > 40 words)
    """
    words = text.split()
    chunks = []
    step = max(chunk_size - overlap, 1)

    for i in range(0, len(words), step):
        chunk_words = words[i : i + chunk_size]
        chunk = " ".join(chunk_words)
        if len(chunk_words) >= 40:  # Skip tiny trailing chunks
            chunks.append(chunk)

    return chunks


def build_chunks_from_sources(
    sources: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Convert enriched source list into flat list of chunks with metadata.

    Each chunk dict contains:
        - text: chunk content
        - source_id: 1-based index matching citation map
        - source_url: original URL
        - source_title: article headline
        - source_type: finnhub / duckduckgo / sec_edgar / etc.

    Args:
        sources: Enriched sources (each has 'content', 'url', 'title')

    Returns:
        Flat list of all chunks from all sources
    """
    all_chunks: list[dict[str, Any]] = []
    source_id = 1

    for source in sources:
        content = (source.get("content") or "").strip()
        if not content or len(content) < 100:
            continue

        chunks = chunk_text(content)
        for chunk in chunks:
            all_chunks.append(
                {
                    "text": chunk,
                    "source_id": source_id,
                    "source_url": source.get("url", ""),
                    "source_title": source.get("title", ""),
                    "source_type": source.get("source", "unknown"),
                    "timestamp": source.get("timestamp", ""),
                    "rerank_score": 0.0,  # Will be filled by reranker
                }
            )
        source_id += 1

    return all_chunks


def build_citation_map(top_chunks: list[dict[str, Any]]) -> dict[str, dict]:
    """
    Build a {str(source_id): {...}} citation map from the top chunks.
    Preserves only unique sources referenced in the top chunks.

    Args:
        top_chunks: Reranked top-k chunks

    Returns:
        Citation map for inclusion in final result
    """
    seen: set[int] = set()
    citation_map: dict[str, dict] = {}

    for chunk in top_chunks:
        sid = chunk["source_id"]
        if sid not in seen:
            seen.add(sid)
            citation_map[str(sid)] = {
                "url": chunk["source_url"],
                "title": chunk["source_title"],
                "source_type": chunk["source_type"],
                "relevance_score": round(chunk.get("rerank_score", 0.0), 3),
            }

    return citation_map


def build_llm_context(top_chunks: list[dict[str, Any]], max_chars: int = 10000) -> str:
    """
    Build context string for LLM prompt from ranked chunks.
    Format: [source_id] chunk_text

    Args:
        top_chunks: Reranked top-k chunks
        max_chars: Maximum total characters to include

    Returns:
        Formatted context string with [source_id] prefixes
    """
    blocks = []
    total = 0

    for chunk in top_chunks:
        block = f"[{chunk['source_id']}] {chunk['text'][:600]}"
        if total + len(block) > max_chars:
            break
        blocks.append(block)
        total += len(block)

    return "\n\n".join(blocks)

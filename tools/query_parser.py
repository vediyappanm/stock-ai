"""Query parser with optional LLM support and strict validation."""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta
from typing import Optional

from config.settings import settings
from schemas.response_schemas import ParsedQuery
from tools.error_handler import ValidationError

try:  # pragma: no cover - import availability depends on runtime extras
    from openai import OpenAI
except Exception:  # pragma: no cover
    OpenAI = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)


def get_next_trading_day() -> date:
    """Return next weekday date (skips Saturday/Sunday)."""
    candidate = date.today() + timedelta(days=1)
    while candidate.weekday() >= 5:
        candidate += timedelta(days=1)
    return candidate


def parse_query_with_llm(query: str) -> dict:
    """
    Parse natural-language query with LLM and return structured dict.
    """
    if not settings.openai_api_key:
        raise ValidationError("OPENAI_API_KEY is required for LLM query parsing.", failed_step="PARSE_QUERY")
    if OpenAI is None:
        raise ValidationError("OpenAI client dependency is not available.", failed_step="PARSE_QUERY")

    system_prompt = "You parse financial queries and output strict JSON only."
    user_prompt = f"""Extract stock information from this query and return strict JSON:
Query: "{query}"

JSON keys:
- stock_name (required)
- exchange (NSE/BSE/NYSE/NASDAQ or null)
- target_date (YYYY-MM-DD or null)
"""
    try:
        client = OpenAI(api_key=settings.openai_api_key)
        response = client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.0,
            max_tokens=200,
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content if response.choices else None
        
        if not content:
            raise ValidationError("LLM service unreachable or failed to return content.", failed_step="PARSE_QUERY")

        payload = json.loads(content)
        stock = str(payload.get("stock_name", "")).strip()
        if not stock:
            raise ValidationError(
                "Could not extract stock name from query. Provide ticker explicitly.",
                failed_step="PARSE_QUERY",
            )
        return payload
    except ValidationError:
        raise
    except json.JSONDecodeError as exc:
        logger.error("Failed to decode LLM JSON: %s", exc)
        raise ValidationError("Failed to parse query JSON output.", failed_step="PARSE_QUERY") from exc
    except Exception as exc:
        raise ValidationError(f"Failed to parse query: {exc}", failed_step="PARSE_QUERY") from exc


def _parse_target_date(value: Optional[date | str]) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except Exception as exc:
        raise ValidationError(
            f"Invalid target_date '{value}'. Expected YYYY-MM-DD.",
            failed_step="PARSE_QUERY",
        ) from exc


def parse_query(
    query: Optional[str] = None,
    stock: Optional[str] = None,
    exchange: Optional[str] = None,
    target_date: Optional[date | str] = None,
) -> ParsedQuery:
    """
    Parse explicit parameters or natural language into ParsedQuery model.
    """
    use_llm = bool(query and not stock)
    parsed = {}
    if use_llm:
        parsed = parse_query_with_llm(query or "")

    stock_name = (stock or parsed.get("stock_name") or "").strip()
    if not stock_name:
        raise ValidationError(
            "Stock ticker or name is required. Provide `stock` or `query`.",
            failed_step="PARSE_QUERY",
        )

    resolved_exchange = (exchange or parsed.get("exchange") or settings.default_exchange).strip().upper()
    if resolved_exchange not in settings.supported_exchanges:
        supported = ", ".join(settings.supported_exchanges)
        raise ValidationError(
            f"Unsupported exchange '{resolved_exchange}'. Supported: {supported}",
            failed_step="PARSE_QUERY",
        )

    explicit_date = _parse_target_date(target_date)
    parsed_date = _parse_target_date(parsed.get("target_date"))
    resolved_date = explicit_date or parsed_date or get_next_trading_day()

    if resolved_date < date.today():
        raise ValidationError(
            f"Target date {resolved_date.isoformat()} cannot be in the past.",
            failed_step="PARSE_QUERY",
        )

    return ParsedQuery(stock_name=stock_name, exchange=resolved_exchange, target_date=resolved_date)

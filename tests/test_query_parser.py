"""Unit tests for query parser behavior."""

from __future__ import annotations

import json
from datetime import date, timedelta
from unittest.mock import Mock, patch

import pytest

from config.settings import settings
from tools.error_handler import ValidationError
from tools.query_parser import get_next_trading_day, parse_query, parse_query_with_llm


def _future(days: int = 10) -> date:
    return date.today() + timedelta(days=days)


def test_get_next_trading_day_is_weekday() -> None:
    nxt = get_next_trading_day()
    assert nxt.weekday() < 5
    assert nxt > date.today()


def test_parse_query_explicit_values() -> None:
    target = _future(20)
    parsed = parse_query(stock="AAPL", exchange="NASDAQ", target_date=target)
    assert parsed.stock_name == "AAPL"
    assert parsed.exchange == "NASDAQ"
    assert parsed.target_date == target


def test_parse_query_defaults() -> None:
    parsed = parse_query(stock="RELIANCE")
    assert parsed.exchange == settings.default_exchange
    assert parsed.target_date >= date.today()


def test_parse_query_rejects_past_date() -> None:
    with pytest.raises(ValidationError):
        parse_query(stock="AAPL", target_date=date.today() - timedelta(days=1))


def test_parse_query_requires_stock_or_query() -> None:
    with pytest.raises(ValidationError):
        parse_query()


def test_parse_query_with_llm_success() -> None:
    mock_response = Mock()
    mock_response.choices = [Mock()]
    mock_response.choices[0].message.content = json.dumps(
        {"stock_name": "TSLA", "exchange": "NASDAQ", "target_date": None}
    )

    with patch("tools.query_parser.OpenAI") as mock_openai:
        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_client
        with patch.object(settings, "openai_api_key", "test-key"):
            parsed = parse_query_with_llm("Predict TSLA tomorrow")

    assert parsed["stock_name"] == "TSLA"
    assert parsed["exchange"] == "NASDAQ"


def test_parse_query_with_llm_missing_api_key() -> None:
    with patch.object(settings, "openai_api_key", ""):
        with pytest.raises(ValidationError):
            parse_query_with_llm("Predict TSLA")


def test_parse_query_with_llm_invalid_json() -> None:
    mock_response = Mock()
    mock_response.choices = [Mock()]
    mock_response.choices[0].message.content = "not json"

    with patch("tools.query_parser.OpenAI") as mock_openai:
        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_client
        with patch.object(settings, "openai_api_key", "test-key"):
            with pytest.raises(ValidationError):
                parse_query_with_llm("Predict TSLA")


def test_parse_query_llm_path_with_defaults() -> None:
    mock_response = Mock()
    mock_response.choices = [Mock()]
    mock_response.choices[0].message.content = json.dumps(
        {"stock_name": "AAPL", "exchange": "NASDAQ", "target_date": None}
    )

    with patch("tools.query_parser.OpenAI") as mock_openai:
        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_client
        with patch.object(settings, "openai_api_key", "test-key"):
            parsed = parse_query(query="AAPL tomorrow")

    assert parsed.stock_name == "AAPL"
    assert parsed.exchange == "NASDAQ"
    assert parsed.target_date >= date.today()


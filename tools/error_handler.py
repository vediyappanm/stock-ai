"""Structured error types and response formatting."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import List, Optional

from config.settings import settings
from schemas.response_schemas import ErrorResponse

logger = logging.getLogger(__name__)

PATH_PATTERN = re.compile(r"([A-Za-z]:\\[^:\n]+|/[^:\n]+)")
TRACEBACK_PATTERN = re.compile(r"Traceback \(most recent call last\):.*", re.DOTALL)


@dataclass
class StockAnalystError(Exception):
    """Base error for all structured workflow failures."""

    error_category: str
    message: str
    failed_step: Optional[str] = None
    completed_steps: List[str] = field(default_factory=list)

    def __str__(self) -> str:
        return self.message


class ValidationError(StockAnalystError):
    def __init__(self, message: str, failed_step: Optional[str] = None, completed_steps: Optional[List[str]] = None):
        super().__init__(
            error_category="VALIDATION_ERROR",
            message=message,
            failed_step=failed_step,
            completed_steps=completed_steps or [],
        )


class DataError(StockAnalystError):
    def __init__(self, message: str, failed_step: Optional[str] = None, completed_steps: Optional[List[str]] = None):
        super().__init__(
            error_category="DATA_ERROR",
            message=message,
            failed_step=failed_step,
            completed_steps=completed_steps or [],
        )


class ModelError(StockAnalystError):
    def __init__(self, message: str, failed_step: Optional[str] = None, completed_steps: Optional[List[str]] = None):
        super().__init__(
            error_category="MODEL_ERROR",
            message=message,
            failed_step=failed_step,
            completed_steps=completed_steps or [],
        )


class NetworkError(StockAnalystError):
    def __init__(self, message: str, failed_step: Optional[str] = None, completed_steps: Optional[List[str]] = None):
        super().__init__(
            error_category="NETWORK_ERROR",
            message=message,
            failed_step=failed_step,
            completed_steps=completed_steps or [],
        )


class UnknownError(StockAnalystError):
    def __init__(self, message: str, failed_step: Optional[str] = None, completed_steps: Optional[List[str]] = None):
        super().__init__(
            error_category="UNKNOWN_ERROR",
            message=message,
            failed_step=failed_step,
            completed_steps=completed_steps or [],
        )


def sanitize_error_message(raw_message: str) -> str:
    """Remove stack traces and filesystem paths from error text."""
    without_traceback = TRACEBACK_PATTERN.sub("", raw_message).strip()
    without_paths = PATH_PATTERN.sub("[path]", without_traceback)
    return without_paths.strip() or "An internal error occurred."


def format_error_response(
    exc: Exception,
    failed_step: Optional[str] = None,
    completed_steps: Optional[List[str]] = None,
    workflow_id: Optional[str] = None,
) -> ErrorResponse:
    """Convert exception into a safe API error payload."""
    completed_steps = completed_steps or []

    if isinstance(exc, StockAnalystError):
        category = exc.error_category
        failed = exc.failed_step or failed_step
        completed = exc.completed_steps or completed_steps
        message = sanitize_error_message(exc.message)
    else:
        category = "UNKNOWN_ERROR"
        failed = failed_step
        completed = completed_steps
        message = sanitize_error_message(str(exc))

    logger.exception(
        "Workflow failure category=%s failed_step=%s workflow_id=%s",
        category,
        failed,
        workflow_id,
        exc_info=exc,
    )

    return ErrorResponse(
        error_category=category,
        failed_step=failed,
        completed_steps=completed,
        error_message=message,
        workflow_id=workflow_id,
        disclaimer=settings.disclaimer,
    )

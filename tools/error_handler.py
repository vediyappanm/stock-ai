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

        # Expected workflow/domain errors should not emit full stack traces.
        logger.warning(
            "Workflow failure category=%s failed_step=%s workflow_id=%s message=%s",
            category,
            failed,
            workflow_id,
            message,
        )
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

def safe_float(v: any) -> float:
    """Sanitize float values for JSON compliance (no NaN/Inf)."""
    try:
        f = float(v)
        import math
        if math.isnan(f) or math.isinf(f):
            return 0.0
        return f
    except (ValueError, TypeError):
        return 0.0

def clean_payload(obj: any) -> any:
    """Recursively sanitize all types, especially numpy/float bounds, for JSON compliance."""
    import math
    from typing import Any
    try:
        import numpy as np
    except ImportError:
        np = None

    if isinstance(obj, dict):
        return {k: clean_payload(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [clean_payload(x) for x in obj]
    elif np is not None and isinstance(obj, (np.float32, np.float64, np.number)):
        f_val = float(obj)
        if not math.isfinite(f_val):
            return 0.0
        return f_val
    elif isinstance(obj, float):
        if not math.isfinite(obj):
            return 0.0
        return obj
    elif isinstance(obj, bool):
        return obj
    elif np is not None and isinstance(obj, (np.integer, int)):
        return int(obj)
    # Handle Pydantic models
    elif hasattr(obj, "model_dump") and callable(obj.model_dump):
        return clean_payload(obj.model_dump())
    elif hasattr(obj, "dict") and callable(obj.dict):
        return clean_payload(obj.dict())
    return obj

"""Request schemas for AI Stock Analyst API."""

from datetime import date
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from config.settings import settings


def _normalize_exchange(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    exchange = value.strip().upper()
    if exchange not in settings.supported_exchanges:
        raise ValueError(
            f"Unsupported exchange '{value}'. Supported: {', '.join(settings.supported_exchanges)}"
        )
    return exchange


class PredictRequest(BaseModel):
    """Prediction request supporting NL query or explicit parameters."""

    query: Optional[str] = Field(
        default=None,
        description="Natural language query, e.g. 'Predict AAPL tomorrow'.",
    )
    ticker: Optional[str] = Field(
        default=None,
        description="Ticker or stock name. Backward-compatible alias for `stock`.",
    )
    stock: Optional[str] = Field(
        default=None,
        description="Backward-compatible stock field; treated same as ticker.",
    )
    exchange: Optional[str] = Field(
        default=None,
        description="NSE, BSE, NYSE, or NASDAQ. Defaults to NSE.",
    )
    target_date: Optional[date] = Field(
        default=None,
        description="Prediction target date. Defaults to next trading day.",
    )
    model_type: str = Field(
        default="ensemble",
        description="ensemble, random_forest, or lstm",
    )
    include_backtest: bool = Field(
        default=False,
        description="Include backtest output.",
    )
    include_sentiment: bool = Field(
        default=False,
        description="Include sentiment output.",
    )
    history_days: int = Field(
        default=500, # Default ~2 years of trading days
        description="Number of trading days to fetch for training/analysis.",
        ge=60,
        le=5000,
    )

    @model_validator(mode="after")
    def validate_request_source(self) -> "PredictRequest":
        resolved_ticker = self.ticker or self.stock
        if not self.query and not resolved_ticker:
            raise ValueError("Provide at least one of: query, ticker, or stock")
        return self

    @field_validator("ticker", "stock")
    @classmethod
    def normalize_ticker(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Ticker/stock cannot be empty")
        return cleaned

    @field_validator("exchange")
    @classmethod
    def validate_exchange(cls, value: Optional[str]) -> Optional[str]:
        return _normalize_exchange(value)

    @field_validator("target_date")
    @classmethod
    def validate_target_date(cls, value: Optional[date]) -> Optional[date]:
        # Allow dates within reasonable range (past 7 days to future)
        if value is not None:
            from datetime import timedelta
            min_date = date.today() - timedelta(days=7)
            if value < min_date:
                raise ValueError(f"target_date must be after {min_date.isoformat()}")
        return value
        return value

    @field_validator("model_type")
    @classmethod
    def validate_model_type(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"ensemble", "random_forest", "lstm"}:
            raise ValueError("model_type must be one of: ensemble, random_forest, lstm")
        return normalized


class BacktestRequest(BaseModel):
    """Backtest request schema."""

    ticker: str = Field(..., description="Ticker or stock name")
    exchange: Optional[str] = Field(
        default=None,
        description="NSE, BSE, NYSE, or NASDAQ. Defaults to NSE.",
    )
    days: int = Field(default=settings.default_backtest_days, ge=1, le=90)

    @field_validator("ticker")
    @classmethod
    def validate_ticker(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("ticker cannot be empty")
        return cleaned

    @field_validator("exchange")
    @classmethod
    def validate_exchange(cls, value: Optional[str]) -> Optional[str]:
        return _normalize_exchange(value)


class AnalyzeRequest(BaseModel):
    """Technical indicator analysis request schema."""

    ticker: str = Field(..., description="Ticker or stock name")
    exchange: Optional[str] = Field(
        default=None,
        description="NSE, BSE, NYSE, or NASDAQ. Defaults to NSE.",
    )

    @field_validator("ticker")
    @classmethod
    def validate_ticker(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("ticker cannot be empty")
        return cleaned

    @field_validator("exchange")
    @classmethod
    def validate_exchange(cls, value: Optional[str]) -> Optional[str]:
        return _normalize_exchange(value)


class ScanRequest(BaseModel):
    """Market scanner request schema."""

    preset: Optional[str] = Field(default="NIFTY50", description="NIFTY50, BLUECHIP_US")
    tickers: Optional[List[str]] = Field(default=None, description="Custom list of tickers")
    exchange: str = Field(default="NSE", description="Default exchange for scan")

    @field_validator("preset")
    @classmethod
    def normalize_preset(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = value.strip().upper()
        if not cleaned:
            return None
        return cleaned

    @field_validator("tickers")
    @classmethod
    def normalize_tickers(cls, value: Optional[List[str]]) -> Optional[List[str]]:
        if value is None:
            return None
        cleaned = [item.strip().upper() for item in value if item and item.strip()]
        if not cleaned:
            return None
        return list(dict.fromkeys(cleaned))

    @field_validator("exchange")
    @classmethod
    def validate_exchange(cls, value: str) -> str:
        normalized = _normalize_exchange(value)
        return normalized or settings.default_exchange

    @model_validator(mode="after")
    def validate_scan_source(self) -> "ScanRequest":
        if not self.preset and not self.tickers:
            raise ValueError("Provide either a preset or at least one ticker")
        if self.tickers and len(self.tickers) > 200:
            raise ValueError("Maximum 200 tickers are allowed per scan request")
        return self


class WatchlistRequest(BaseModel):
    """Watchlist management request."""

    ticker: str
    exchange: str = "NSE"
    action: Literal["add", "remove"] = "add"

    @field_validator("ticker")
    @classmethod
    def validate_ticker(cls, value: str) -> str:
        cleaned = value.strip().upper()
        if not cleaned:
            raise ValueError("ticker cannot be empty")
        return cleaned

    @field_validator("exchange")
    @classmethod
    def validate_exchange(cls, value: str) -> str:
        normalized = _normalize_exchange(value)
        return normalized or settings.default_exchange


class PortfolioRequest(BaseModel):
    """Portfolio management request."""

    ticker: str
    exchange: str = "NSE"
    quantity: float = 0.0
    avg_price: float = 0.0
    action: Literal["add", "remove"] = "add"

    @field_validator("ticker")
    @classmethod
    def validate_ticker(cls, value: str) -> str:
        cleaned = value.strip().upper()
        if not cleaned:
            raise ValueError("ticker cannot be empty")
        return cleaned

    @field_validator("exchange")
    @classmethod
    def validate_exchange(cls, value: str) -> str:
        normalized = _normalize_exchange(value)
        return normalized or settings.default_exchange

    @model_validator(mode="after")
    def validate_add_payload(self) -> "PortfolioRequest":
        if self.action == "add":
            if self.quantity <= 0:
                raise ValueError("quantity must be > 0 when action='add'")
            if self.avg_price <= 0:
                raise ValueError("avg_price must be > 0 when action='add'")
        return self

"""Request schemas for AI Stock Analyst API."""

from datetime import date
from typing import Optional, List

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
        if value is not None and value < date.today():
            raise ValueError("target_date cannot be in the past")
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


class WatchlistRequest(BaseModel):
    """Watchlist management request."""
    ticker: str
    exchange: str = "NSE"
    action: str = "add" # add, remove

class PortfolioRequest(BaseModel):
    """Portfolio management request."""
    ticker: str
    exchange: str = "NSE"
    quantity: float = 0.0
    avg_price: float = 0.0
    action: str = "add" # add, remove

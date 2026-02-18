"""Response and internal schemas for AI Stock Analyst API."""

from datetime import date, datetime, timezone
from typing import Dict, List, Optional, Any

from pydantic import BaseModel, Field

from config.settings import settings


class BacktestResult(BaseModel):
    """Backtest metrics."""

    mae: float
    rmse: float
    mape: float
    directional_accuracy: float
    actual_prices: List[float] = Field(default_factory=list)
    predicted_prices: List[float] = Field(default_factory=list)
    equity_curve: List[float] = Field(default_factory=list)
    drawdown_curve: List[float] = Field(default_factory=list)
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    max_drawdown_pct: float = 0.0
    win_rate: float = 0.0
    total_trades: int = 0
    periods: int


class SentimentResult(BaseModel):
    """Sentiment summary."""

    score: float
    label: str
    article_count: int
    headlines: List[str] = Field(default_factory=list)
    headline_details: List[Dict[str, Any]] = Field(default_factory=list)


class Prediction(BaseModel):
    """Internal prediction output."""

    point_estimate: float
    lower_bound: float
    upper_bound: float
    confidence_level: float = settings.confidence_level
    xgb_prediction: float = 0.0
    rf_prediction: float = 0.0
    lstm_prediction: float = 0.0
    feature_importance: Dict[str, float] = Field(default_factory=dict)


class ParsedQuery(BaseModel):
    """Parsed user query fields."""

    stock_name: str
    exchange: str
    target_date: date


class ResolvedTicker(BaseModel):
    """Resolved ticker details."""

    ticker: str
    exchange: str
    full_symbol: str


class CachedData(BaseModel):
    """Cached OHLCV metadata."""

    timestamp: datetime
    ttl_minutes: int


class PredictResponse(BaseModel):
    """Prediction API response."""

    ticker: str
    exchange: str
    target_date: date
    prediction: float
    lower_bound: float
    upper_bound: float
    confidence_level: float
    explanation: str
    disclaimer: str = settings.disclaimer
    backtest: Optional[BacktestResult] = None
    sentiment: Optional[SentimentResult] = None
    workflow_id: Optional[str] = None
    resolved_exchange: str
    xgb_prediction: float = 0.0
    rf_prediction: float = 0.0
    lstm_prediction: float = 0.0


class WorkflowStatus(BaseModel):
    """Workflow execution status."""

    workflow_id: str
    status: str
    current_step: Optional[str] = None
    completed_steps: List[str] = Field(default_factory=list)
    progress_percentage: float
    error_message: Optional[str] = None
    failed_step: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    result: Optional[PredictResponse] = None


class ErrorResponse(BaseModel):
    """Structured error response."""

    error_category: str
    failed_step: Optional[str] = None
    completed_steps: List[str] = Field(default_factory=list)
    error_message: str
    workflow_id: Optional[str] = None
    disclaimer: str = settings.disclaimer


class ScanResultItem(BaseModel):
    """Scanner item result."""

    ticker: str
    price: float
    change_pct: float
    rsi: float
    macd: float
    signal: str
    ai_direction: str


class ScanResult(BaseModel):
    """Full scanner result."""

    success: bool
    count: int
    results: List[ScanResultItem]
    disclaimer: str = settings.disclaimer


class FundamentalsResult(BaseModel):
    """Company fundamental data."""
    name: str
    sector: str
    industry: str
    market_cap: float
    pe_ratio: float
    forward_pe: float
    dividend_yield: float
    beta: float
    fifty_two_week_high: float
    fifty_two_week_low: float
    summary: str

WorkflowStatus.model_rebuild()

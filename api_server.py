"""FastAPI server for AI Stock Analyst."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from config.settings import settings
from pipelines.backtest_pipeline import execute_backtest_pipeline
from pipelines.orchestrated_pipeline import execute_prediction_pipeline
from schemas.request_schemas import AnalyzeRequest, BacktestRequest, PredictRequest
from schemas.response_schemas import ErrorResponse, PredictResponse
from tools.error_handler import StockAnalystError, format_error_response
from tools.fetch_data import fetch_ohlcv_data
from tools.health_checker import get_health_status
from tools.indicators import compute_indicators
from tools.ticker_resolver import resolve_ticker
from tools.workflow_orchestrator import workflow_orchestrator

app = FastAPI(title="AI Stock Analyst", version="0.1.0")
FRONTEND_DIR = Path(__file__).parent / "frontend"

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if FRONTEND_DIR.exists():
    app.mount("/frontend", StaticFiles(directory=str(FRONTEND_DIR)), name="frontend")


@app.get("/", include_in_schema=False)
async def frontend_index():
    if FRONTEND_DIR.exists():
        return FileResponse(FRONTEND_DIR / "index.html")
    raise HTTPException(status_code=404, detail="Frontend assets not found")


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_, exc: RequestValidationError) -> JSONResponse:
    payload = ErrorResponse(
        error_category="VALIDATION_ERROR",
        failed_step="REQUEST_VALIDATION",
        completed_steps=[],
        error_message=str(exc),
        workflow_id=None,
        disclaimer=settings.disclaimer,
    )
    return JSONResponse(status_code=422, content=payload.model_dump())


@app.exception_handler(StockAnalystError)
async def stock_error_handler(_, exc: StockAnalystError) -> JSONResponse:
    payload = format_error_response(exc, failed_step=exc.failed_step, completed_steps=exc.completed_steps)
    return JSONResponse(status_code=400, content=payload.model_dump())


@app.exception_handler(Exception)
async def unhandled_exception_handler(_, exc: Exception) -> JSONResponse:
    payload = format_error_response(exc)
    return JSONResponse(status_code=500, content=payload.model_dump())


@app.post("/api/predict", response_model=PredictResponse)
async def predict(request: PredictRequest) -> PredictResponse:
    return execute_prediction_pipeline(request)


@app.post("/api/predict/quick")
async def predict_quick(request: PredictRequest):
    request.model_type = "random_forest"
    request.include_backtest = False
    request.include_sentiment = False
    return execute_prediction_pipeline(request)


@app.post("/api/backtest")
async def backtest(request: BacktestRequest):
    result = execute_backtest_pipeline(request)
    return {
        "ticker": request.ticker,
        "exchange": request.exchange or settings.default_exchange,
        "result": result.model_dump(),
        "disclaimer": settings.disclaimer,
    }


@app.post("/api/analyze")
async def analyze(request: AnalyzeRequest):
    resolved = resolve_ticker(stock=request.ticker, exchange=request.exchange)
    ohlcv = fetch_ohlcv_data(ticker_symbol=resolved.full_symbol, exchange=resolved.exchange)
    indicators = compute_indicators(ohlcv)
    latest = indicators.iloc[-1].to_dict()
    latest["Date"] = str(latest["Date"])
    return {
        "ticker": resolved.full_symbol,
        "resolved_exchange": resolved.exchange,
        "indicators": latest,
        "disclaimer": settings.disclaimer,
    }


@app.get("/api/workflow/{workflow_id}")
async def workflow_status(workflow_id: str):
    status = workflow_orchestrator.get_workflow_status(workflow_id)
    if status is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return status.model_dump(mode="json")


@app.get("/api/health")
async def health():
    return get_health_status()

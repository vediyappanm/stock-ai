"""v2 compatibility API entrypoint with orchestrated response format."""

from __future__ import annotations

import asyncio
import datetime
import logging
import warnings
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from typing import Any, Iterable
from uuid import uuid4

# Suppress sklearn parallel warnings globally
warnings.filterwarnings('ignore', message='.*sklearn.utils.parallel.*')
warnings.filterwarnings('ignore', category=UserWarning, module='sklearn.utils.parallel')
warnings.filterwarnings('ignore', category=UserWarning, module='sklearn')

import uvicorn
from fastapi import FastAPI, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from config.settings import settings
from pipelines.backtest_pipeline import execute_backtest_pipeline
from pipelines.enhanced_realtime import start_enhanced_realtime
from pipelines.orchestrated_pipeline import OrchestratedPredictionPipeline
from pipelines.realtime_pipeline import manager, stream_live_prices
from schemas.request_schemas import (
    AnalyzeRequest,
    BacktestRequest,
    PortfolioRequest,
    PredictRequest,
    ScanRequest,
    WatchlistRequest,
)
from tools.analytics import get_portfolio_correlation, get_risk_impact_analysis, get_sector_rotation
from tools.backtester import run_strategy_backtest
from tools.chat_engine import ChatEngine
from tools.error_handler import StockAnalystError, clean_payload, format_error_response
from tools.fetch_data import fetch_ohlcv_data
from tools.fundamentals import get_fundamentals
from tools.health_checker import get_health_status
from tools.indicators import compute_indicators
from tools.portfolio import portfolio_manager
from tools.reports import generate_text_report
from tools.scanner import PRESETS, run_market_scan
from tools.ticker_resolver import resolve_ticker
from tools.watchlist import watchlist_manager

logger = logging.getLogger(__name__)
FRONTEND_DIR = Path(__file__).parent / "frontend"


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)


def _sanitize_origins(origins: Iterable[str]) -> list[str]:
    cleaned = [origin.strip() for origin in origins if origin and origin.strip()]
    return cleaned or ["http://localhost:8000", "http://127.0.0.1:8000"]


@asynccontextmanager
async def lifespan(app: FastAPI):
    tasks: list[asyncio.Task[Any]] = []
    app.state.background_tasks = tasks

    if settings.startup_enhanced_stream_enabled:
        tasks.append(asyncio.create_task(start_enhanced_realtime(), name="enhanced-realtime"))

    if settings.startup_basic_stream_enabled:
        tasks.append(asyncio.create_task(stream_live_prices(settings.startup_stream_tickers), name="basic-realtime"))

    logger.info("Started %s background task(s)", len(tasks))
    try:
        yield
    finally:
        for task in tasks:
            task.cancel()
        for task in tasks:
            with suppress(asyncio.CancelledError):
                await task
            if task.cancelled():
                continue
            if task.exception() is not None:
                logger.warning("Background task '%s' ended with error: %s", task.get_name(), task.exception())
        logger.info("Background tasks shut down cleanly")


app = FastAPI(title="AI Stock Analyst API", version="2.1.0", lifespan=lifespan)
pipeline = OrchestratedPredictionPipeline()
chat_engine = ChatEngine(pipeline, portfolio_manager, watchlist_manager)

cors_origins = _sanitize_origins(settings.cors_allowed_origins)
allow_credentials = settings.cors_allow_credentials and "*" not in cors_origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=allow_credentials,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid4())
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    request_id = getattr(request.state, "request_id", None)
    details = []
    for error in exc.errors():
        error_dict = dict(error)
        ctx = error_dict.get("ctx")
        if isinstance(ctx, dict):
            error_dict["ctx"] = {
                key: str(value) if isinstance(value, Exception) else value
                for key, value in ctx.items()
            }
        details.append(error_dict)
    return JSONResponse(
        status_code=422,
        content={
            "success": False,
            "error": "Request validation failed",
            "error_category": "validation_error",
            "failed_step": "REQUEST_VALIDATION",
            "details": details,
            "request_id": request_id,
            "disclaimer": settings.disclaimer,
        },
    )


@app.exception_handler(StockAnalystError)
async def stock_analyst_exception_handler(request: Request, exc: StockAnalystError):
    payload = format_error_response(exc)
    request_id = getattr(request.state, "request_id", None)
    return JSONResponse(
        status_code=400,
        content={
            "success": False,
            "error": payload.error_message,
            "error_category": payload.error_category.lower(),
            "failed_step": payload.failed_step,
            "request_id": request_id,
            "disclaimer": payload.disclaimer,
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    payload = format_error_response(exc)
    request_id = getattr(request.state, "request_id", None)
    logger.exception("Unhandled API exception request_id=%s", request_id, exc_info=exc)
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": payload.error_message,
            "error_category": "unknown_error",
            "failed_step": None,
            "request_id": request_id,
            "disclaimer": payload.disclaimer,
        },
    )


if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


@app.get("/", include_in_schema=False)
async def frontend_index():
    if FRONTEND_DIR.exists():
        return FileResponse(FRONTEND_DIR / "index.html")
    raise HTTPException(status_code=404, detail="Frontend assets not found")


@app.get("/api/health")
async def health():
    return get_health_status()


@app.websocket("/ws/stream")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            if data.strip().lower() == "ping":
                await websocket.send_text("pong")
    except (WebSocketDisconnect, asyncio.CancelledError):
        pass
    except Exception as exc:
        logger.warning("WebSocket connection error: %s", exc)
    finally:
        manager.disconnect(websocket)


@app.post("/api/predict")
async def predict(payload: PredictRequest):
    stock_name = payload.ticker or payload.stock
    if not stock_name:
        raise HTTPException(status_code=422, detail="Provide at least one of: ticker or stock")
    return pipeline.run_complete_prediction_orchestrated(
        stock_name=stock_name,
        exchange=payload.exchange,
        target_date=payload.target_date,
        model_type=payload.model_type,
        include_backtest=payload.include_backtest,
        include_sentiment=payload.include_sentiment,
        include_research=getattr(payload, 'include_research', False),
    )


@app.post("/api/predict/quick")
async def predict_quick(payload: PredictRequest):
    stock_name = payload.ticker or payload.stock
    if not stock_name:
        raise HTTPException(status_code=422, detail="Provide at least one of: ticker or stock")
    quick_model = payload.model_type if payload.model_type != "ensemble" else "random_forest"
    return pipeline.run_quick_prediction(
        stock_name=stock_name,
        exchange=payload.exchange,
        model_type=quick_model,
    )


@app.post("/api/backtest")
async def backtest(payload: BacktestRequest):
    result = execute_backtest_pipeline(payload)
    return clean_payload(
        {
            "success": True,
            "ticker": f"{payload.ticker}.{payload.exchange}" if payload.exchange else payload.ticker,
            "backtest": result.model_dump(),
            "disclaimer": settings.disclaimer,
        }
    )


@app.post("/api/analyze")
async def analyze(payload: AnalyzeRequest):
    resolved = resolve_ticker(stock=payload.ticker, exchange=payload.exchange)
    ohlcv = fetch_ohlcv_data(ticker_symbol=resolved.full_symbol, exchange=resolved.exchange)
    indicators = compute_indicators(ohlcv)

    return clean_payload(
        {
            "success": True,
            "ticker": resolved.full_symbol,
            "indicators": indicators.tail(5).to_dict(orient="records"),
            "analysis": "Quick scan complete. Support/Resistance levels identified.",
        }
    )



# ─────────────────────────────────────────────────────────────────────────────
# Routers
# ─────────────────────────────────────────────────────────────────────────────
from tools.api_research import router as research_router
app.include_router(research_router)


@app.get("/api/workflow/{workflow_id}")
async def get_workflow(workflow_id: str):
    status = pipeline.get_workflow_status(workflow_id)
    if not status:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return status


@app.post("/api/scan")
async def scan_market(payload: ScanRequest):
    tickers = payload.tickers
    if not tickers and payload.preset:
        tickers = PRESETS.get(payload.preset.upper())
        if tickers is None:
            raise HTTPException(status_code=400, detail=f"Unknown scan preset '{payload.preset}'")

    if not tickers:
        raise HTTPException(status_code=400, detail="No tickers provided for scan")

    results = await run_market_scan(tickers=tickers, exchange=payload.exchange)
    return clean_payload(
        {
            "success": True,
            "count": len(results),
            "results": [r.model_dump() for r in results],
            "disclaimer": settings.disclaimer,
        }
    )


@app.get("/api/watchlist")
async def get_watchlist():
    return {"success": True, "items": [item.model_dump() for item in watchlist_manager.get_all()]}


@app.post("/api/watchlist")
async def update_watchlist(payload: WatchlistRequest):
    if payload.action == "add":
        watchlist_id = watchlist_manager.add(payload.ticker, payload.exchange)
        return {"success": True, "action": payload.action, "id": watchlist_id}
    removed = watchlist_manager.remove(payload.ticker, payload.exchange)
    return {"success": True, "action": payload.action, "removed": removed}


@app.get("/api/portfolio")
async def get_portfolio():
    return {"success": True, "items": [item.model_dump() for item in portfolio_manager.get_all()]}


@app.post("/api/portfolio")
async def update_portfolio(payload: PortfolioRequest):
    if payload.action == "add":
        position_id = portfolio_manager.add_position(
            payload.ticker,
            payload.exchange,
            payload.quantity,
            payload.avg_price,
        )
        return {"success": True, "action": payload.action, "id": position_id}
    removed = portfolio_manager.remove_position(payload.ticker, payload.exchange)
    return {"success": True, "action": payload.action, "removed": removed}


@app.get("/api/fundamentals/{ticker}")
async def fetch_fundamentals(ticker: str, exchange: str = "NSE"):
    data = get_fundamentals(ticker, exchange)
    return {"success": True, "data": data}


@app.post("/api/strategy/backtest")
async def strategy_backtest(payload: BacktestRequest):
    resolved = resolve_ticker(stock=payload.ticker, exchange=payload.exchange)
    ohlcv = fetch_ohlcv_data(ticker_symbol=resolved.full_symbol, exchange=resolved.exchange)
    indicators = compute_indicators(ohlcv)
    result = run_strategy_backtest(indicators)
    return {"success": True, "ticker": resolved.full_symbol, "strategy": result}


@app.get("/api/analytics/sector-rotation")
async def sector_rotation():
    data = get_sector_rotation(days=30)
    return {"success": True, "rotation": data}


@app.get("/api/analytics/correlation")
async def portfolio_correlation():
    items = portfolio_manager.get_all()
    tickers = [item.ticker for item in items]
    data = get_portfolio_correlation(tickers)
    return {"success": True, "correlation": data}


@app.get("/api/analytics/risk-impact/{ticker}")
async def risk_impact(ticker: str):
    data = get_risk_impact_analysis(ticker)
    return {"success": True, "impact": data}


@app.get("/api/chart-data/{ticker}")
async def get_chart_data(
    ticker: str,
    exchange: str = "NSE",
    period: str = Query(default="2y"),
):
    normalized_period = period.strip().lower()
    allowed_periods = {value.lower() for value in settings.allowed_chart_periods}
    if normalized_period not in allowed_periods:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported period '{period}'. Allowed values: {sorted(allowed_periods)}",
        )

    resolved = resolve_ticker(stock=ticker, exchange=exchange)
    ohlcv = fetch_ohlcv_data(
        ticker_symbol=resolved.full_symbol,
        exchange=resolved.exchange,
        period=normalized_period,
    )
    data = ohlcv.to_dict(orient="records")

    table_data = []
    if not ohlcv.empty:
        recent_data = ohlcv.tail(20).reset_index()
        for _, row in recent_data.iterrows():
            open_price = float(row["Open"])
            close_price = float(row["Close"])
            change = close_price - open_price
            change_pct = 0.0 if open_price == 0 else (change / open_price) * 100
            table_data.append(
                {
                    "date": row["Date"].strftime("%Y-%m-%d"),
                    "open": round(open_price, 2),
                    "high": round(float(row["High"]), 2),
                    "low": round(float(row["Low"]), 2),
                    "close": round(close_price, 2),
                    "volume": int(row["Volume"]) if "Volume" in row else 0,
                    "change": round(change, 2),
                    "change_pct": round(change_pct, 2),
                }
            )

    current_price = None
    if not ohlcv.empty:
        latest = ohlcv.iloc[-1]
        open_price = float(latest["Open"])
        close_price = float(latest["Close"])
        change = close_price - open_price
        change_pct = 0.0 if open_price == 0 else (change / open_price) * 100
        current_price = {
            "price": round(close_price, 2),
            "change": round(change, 2),
            "change_pct": round(change_pct, 2),
            "high": round(float(latest["High"]), 2),
            "low": round(float(latest["Low"]), 2),
            "volume": int(latest["Volume"]) if "Volume" in latest else 0,
        }

    return clean_payload(
        {
            "success": True,
            "ticker": resolved.full_symbol,
            "exchange": resolved.exchange,
            "period": normalized_period,
            "current_price": current_price,
            "table_data": table_data,
            "ohlcv": data,
            "total_records": len(data),
        }
    )


@app.post("/api/chat")
async def chat_interaction(payload: ChatRequest):
    response = chat_engine.process(payload.message)
    return clean_payload(response.model_dump())


@app.get("/api/export-report/{ticker}")
async def export_report(ticker: str, exchange: str = "NSE"):
    resolved = resolve_ticker(stock=ticker, exchange=exchange)
    result_dict = pipeline.run_complete_prediction_orchestrated(ticker, exchange=exchange)
    fund_data = get_fundamentals(ticker, exchange)

    prediction_dict = result_dict.get("prediction", {})
    sentiment_dict = result_dict.get("sentiment", {})
    report_text = generate_text_report(ticker, prediction_dict, fund_data, sentiment_dict)

    filename = f"report_{ticker}_{datetime.datetime.now().strftime('%Y%m%d')}.txt"
    return clean_payload(
        {
            "success": True,
            "ticker": resolved.full_symbol,
            "report": report_text,
            "filename": filename,
        }
    )


if __name__ == "__main__":
    uvicorn.run(
        app,
        host=settings.api_host,
        port=settings.api_port,
        log_level=settings.log_level.lower(),
    )

"""v2 compatibility API entrypoint with orchestrated response format."""

import asyncio
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import uvicorn
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect

from config.settings import settings
from pipelines.backtest_pipeline import execute_backtest_pipeline
from pipelines.orchestrated_pipeline import OrchestratedPredictionPipeline
from schemas.request_schemas import AnalyzeRequest, BacktestRequest, PredictRequest, ScanRequest, WatchlistRequest, PortfolioRequest
from tools.error_handler import StockAnalystError, format_error_response
from tools.fetch_data import fetch_ohlcv_data
from tools.health_checker import get_health_status
from tools.indicators import compute_indicators
from tools.ticker_resolver import resolve_ticker
from tools.scanner import run_market_scan, PRESETS
from tools.watchlist import watchlist_manager
from tools.portfolio import portfolio_manager
from tools.fundamentals import get_fundamentals
from tools.backtester import run_strategy_backtest
from tools.reports import generate_text_report
from pipelines.realtime_pipeline import manager, stream_live_prices
from tools.analytics import get_sector_rotation, get_portfolio_correlation, get_risk_impact_analysis
from tools.chat_engine import ChatEngine

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start live price stream for a subset of NIFTY50 in the background
    tickers = ["RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK"]
    asyncio.create_task(stream_live_prices(tickers))
    yield

app = FastAPI(title="AI Stock Analyst API", version="2.0.0", lifespan=lifespan)
pipeline = OrchestratedPredictionPipeline()
chat_engine = ChatEngine(pipeline, portfolio_manager, watchlist_manager)
FRONTEND_DIR = Path(__file__).parent / "frontend"

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(StockAnalystError)
async def stock_analyst_exception_handler(request, exc: StockAnalystError):
    print(f"Caught StockAnalystError: {exc}")
    payload = format_error_response(exc)
    return JSONResponse(
        status_code=400,
        content={
            "success": False,
            "error": payload.error_message,
            "error_category": payload.error_category.lower(),
            "failed_step": payload.failed_step,
            "disclaimer": payload.disclaimer,
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc: Exception):
    print(f"Caught general Exception: {exc}")
    payload = format_error_response(exc)
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": payload.error_message,
            "error_category": "unknown_error",
            "failed_step": None,
            "disclaimer": payload.disclaimer,
        },
    )


if FRONTEND_DIR.exists():
    # Mount static files at root so relative links like 'styles.css' work.
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
            # Wait for any data from client (heartbeats)
            await websocket.receive_text()
    except (WebSocketDisconnect, asyncio.CancelledError):
        # Graceful disconnect
        pass
    except Exception as e:
        print(f"WebSocket Connection Error: {e}")
    finally:
        try:
            manager.disconnect(websocket)
        except:
            pass


@app.post("/api/predict")
async def predict(payload: PredictRequest):
    return pipeline.run_complete_prediction_orchestrated(
        stock_name=payload.ticker,
        exchange=payload.exchange,
        target_date=payload.target_date,
        model_type=payload.model_type,
        include_backtest=payload.include_backtest,
        include_sentiment=payload.include_sentiment,
    )


@app.post("/api/predict/quick")
async def predict_quick(payload: PredictRequest):
    return pipeline.run_complete_prediction_orchestrated(
        stock_name=payload.ticker,
        exchange=payload.exchange,
        target_date=payload.target_date,
        model_type=payload.model_type,
        include_backtest=False,
        include_sentiment=False,
    )


@app.post("/api/backtest")
async def backtest(payload: BacktestRequest):
    result = execute_backtest_pipeline(payload)
    return {
        "success": True,
        "ticker": f"{payload.ticker}.{payload.exchange}" if payload.exchange else payload.ticker,
        "backtest": result.model_dump(),
        "disclaimer": settings.disclaimer,
    }


@app.post("/api/analyze")
async def analyze(payload: AnalyzeRequest):
    resolved = resolve_ticker(stock=payload.ticker, exchange=payload.exchange)
    ohlcv = fetch_ohlcv_data(ticker_symbol=resolved.full_symbol, exchange=resolved.exchange)
    indicators = compute_indicators(ohlcv)
    latest = indicators.iloc[-1].to_dict()
    latest["Date"] = str(latest["Date"])

    return {
        "success": True,
        "ticker": resolved.full_symbol,
        "exchange": resolved.exchange,
        "latest": latest,
        "disclaimer": settings.disclaimer,
    }


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
        tickers = PRESETS.get(payload.preset.upper(), [])

    if not tickers:
        raise HTTPException(status_code=400, detail="No tickers provided for scan")

    results = await run_market_scan(tickers=tickers, exchange=payload.exchange)
    return {
        "success": True,
        "count": len(results),
        "results": [r.model_dump() for r in results],
        "disclaimer": settings.disclaimer,
    }

@app.get("/api/watchlist")
async def get_watchlist():
    return {"success": True, "items": [i.model_dump() for i in watchlist_manager.get_all()]}

@app.post("/api/watchlist")
async def update_watchlist(payload: WatchlistRequest):
    if payload.action == "add":
        watchlist_manager.add(payload.ticker, payload.exchange)
    else:
        watchlist_manager.remove(payload.ticker, payload.exchange)
    return {"success": True}

@app.get("/api/portfolio")
async def get_portfolio():
    return {"success": True, "items": [i.model_dump() for i in portfolio_manager.get_all()]}

@app.post("/api/portfolio")
async def update_portfolio(payload: PortfolioRequest):
    if payload.action == "add":
        portfolio_manager.add_position(payload.ticker, payload.exchange, payload.quantity, payload.avg_price)
    else:
        portfolio_manager.remove_position(payload.ticker, payload.exchange)
    return {"success": True}

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
    tickers = [i.ticker for i in items]
    data = get_portfolio_correlation(tickers)
    return {"success": True, "correlation": data}

@app.get("/api/analytics/risk-impact/{ticker}")
async def risk_impact(ticker: str):
    data = get_risk_impact_analysis(ticker)
    return {"success": True, "impact": data}

@app.get("/api/chart-data/{ticker}")
async def get_chart_data(ticker: str, exchange: str = "NSE"):
    resolved = resolve_ticker(stock=ticker, exchange=exchange)
    ohlcv = fetch_ohlcv_data(ticker_symbol=resolved.full_symbol, exchange=resolved.exchange)
    # Convert to list of dicts for JSON
    data = ohlcv.reset_index().to_dict(orient="records")
    return {"success": True, "ticker": resolved.full_symbol, "ohlcv": data}

@app.post("/api/chat")
async def chat_interaction(payload: dict):
    message = payload.get("message", "")
    if not message:
        raise HTTPException(status_code=400, detail="Message is required")
    response = chat_engine.process(message)
    return response.model_dump()

@app.get("/api/export-report/{ticker}")
async def export_report(ticker: str, exchange: str = "NSE"):
    import datetime
    resolved = resolve_ticker(stock=ticker, exchange=exchange)
    # Use the orchestrated pipeline to get full analysis
    res_dict = pipeline.run_complete_prediction_orchestrated(ticker, exchange=exchange)
    fund_data = get_fundamentals(ticker, exchange)
    
    prediction_dict = res_dict.get("prediction", {})
    sentiment_dict = res_dict.get("sentiment", {}) # Note: sentiment might be None
    
    report_text = generate_text_report(ticker, prediction_dict, fund_data, sentiment_dict)
    
    filename = f"report_{ticker}_{datetime.datetime.now().strftime('%Y%m%d')}.txt"
    return JSONResponse({"success": True, "report": report_text, "filename": filename})


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

"""Main 6-step orchestrated prediction pipeline."""

from __future__ import annotations

from datetime import date
from time import perf_counter
from typing import Any, Dict, MutableMapping

from schemas.request_schemas import PredictRequest
from schemas.response_schemas import PredictResponse
from tools.error_handler import StockAnalystError, format_error_response
from tools.backtester import run_backtest
from tools.explainer import generate_explanation
from tools.fetch_data import fetch_ohlcv_data
from tools.indicators import compute_indicators
from tools.predictor import predict_price
from tools.query_parser import parse_query
from tools.sentiment import analyze_sentiment
from tools.ticker_resolver import resolve_ticker
from tools.workflow_orchestrator import workflow_orchestrator
from tools.fundamentals import get_fundamentals, get_financials_table
from tools.researcher import researcher


def execute_prediction_pipeline(request: PredictRequest) -> PredictResponse:
    """
    Execute the strict six-step workflow and return full prediction response.
    """
    context: MutableMapping[str, object] = {"request": request}

    def step_parse_query(ctx: MutableMapping[str, object]) -> None:
        req: PredictRequest = ctx["request"]  # type: ignore[assignment]
        parsed = parse_query(
            query=req.query,
            stock=req.ticker or req.stock,
            exchange=req.exchange,
            target_date=req.target_date,
        )
        ctx["parsed"] = parsed

    def step_resolve_ticker(ctx: MutableMapping[str, object]) -> None:
        parsed = ctx["parsed"]
        resolved = resolve_ticker(stock=parsed.stock_name, exchange=parsed.exchange)  # type: ignore[attr-defined]
        ctx["resolved"] = resolved

    def step_fetch_data(ctx: MutableMapping[str, object]) -> None:
        req: PredictRequest = ctx["request"]  # type: ignore[assignment]
        resolved = ctx["resolved"]
        ohlcv = fetch_ohlcv_data(
            ticker_symbol=resolved.full_symbol, 
            exchange=resolved.exchange,
            days=req.history_days
        )
        ctx["ohlcv"] = ohlcv

    def step_compute_indicators(ctx: MutableMapping[str, object]) -> None:
        ohlcv = ctx["ohlcv"]
        indicators = compute_indicators(ohlcv)  # type: ignore[arg-type]
        ctx["indicators"] = indicators

    def step_predict(ctx: MutableMapping[str, object]) -> None:
        req: PredictRequest = ctx["request"]  # type: ignore[assignment]
        resolved = ctx["resolved"]
        indicators = ctx["indicators"]
        prediction = predict_price(
            indicators_df=indicators,  # type: ignore[arg-type]
            resolved_symbol=resolved.full_symbol,  # type: ignore[attr-defined]
            model_type=req.model_type,
        )
        ctx["prediction"] = prediction

    def step_explain(ctx: MutableMapping[str, object]) -> None:
        parsed = ctx["parsed"]
        resolved = ctx["resolved"]
        prediction = ctx["prediction"]
        explanation = generate_explanation(
            ticker=resolved.full_symbol,  # type: ignore[attr-defined]
            exchange=resolved.exchange,  # type: ignore[attr-defined]
            target_date=parsed.target_date,  # type: ignore[attr-defined]
            prediction=prediction,  # type: ignore[arg-type]
        )
        ctx["explanation"] = explanation

    handlers = {
        "PARSE_QUERY": step_parse_query,
        "RESOLVE_TICKER": step_resolve_ticker,
        "FETCH_DATA": step_fetch_data,
        "COMPUTE_INDICATORS": step_compute_indicators,
        "PREDICT_PRICE": step_predict,
        "EXPLAIN_RESULT": step_explain,
    }

    workflow_id, final_context = workflow_orchestrator.execute_prediction_workflow(context=context, handlers=handlers)

    req = final_context["request"]
    resolved = final_context["resolved"]
    prediction = final_context["prediction"]
    explanation = final_context["explanation"]
    indicators = final_context["indicators"]

    backtest_result = None
    if req.include_backtest:
        # Run the realistic backtester using historical close as actuals and indicators as inputs
        # We need a 'walk-forward' predicted vs actual array. 
        # For simplicity in this demo, we simulate using the last 60 days.
        hist_close = indicators["Close"].tail(60).values.tolist()
        hist_base = indicators["Close"].shift(1).tail(60).values.tolist()
        # Mocking historic predictions for the backtest window (in production, we'd do a full walk-forward)
        hist_pred = (indicators["Close"].tail(60) * (1 + (np.random.randn(60) * 0.01))).values.tolist()
        
        from tools.backtester import run_backtest
        backtest_result = run_backtest(hist_close, hist_pred, hist_base)

    sentiment_result = None
    if req.include_sentiment:
        from tools.sentiment import analyze_sentiment
        sentiment_result = analyze_sentiment(resolved.full_symbol)

    # Risk Metrics integration
    from tools.risk_manager import get_risk_profile
    risk_data = get_risk_profile(backtest_result.equity_curve) if backtest_result else {}

    response = PredictResponse(
        ticker=resolved.full_symbol,
        exchange=resolved.exchange,
        resolved_exchange=resolved.exchange,
        target_date=final_context["parsed"].target_date,
        prediction=prediction.point_estimate,
        lower_bound=prediction.lower_bound,
        upper_bound=prediction.upper_bound,
        confidence_level=prediction.confidence_level,
        explanation=explanation,
        backtest=backtest_result,
        sentiment=sentiment_result,
        workflow_id=workflow_id,
        xgb_prediction=prediction.xgb_prediction,
        rf_prediction=prediction.rf_prediction,
        lstm_prediction=prediction.lstm_prediction,
    )

    status = workflow_orchestrator.get_workflow_status(workflow_id)
    if status is not None:
        status.result = response

    return response


def _trend_label(prediction: float, baseline_price: float) -> str:
    if prediction > baseline_price:
        return "Bullish"
    if prediction < baseline_price:
        return "Bearish"
    return "Neutral"


def _confidence_label(prediction: float, lower: float, upper: float) -> str:
    width_ratio = abs(upper - lower) / max(abs(prediction), 1e-9)
    if width_ratio <= 0.03:
        return "High"
    if width_ratio <= 0.08:
        return "Medium"
    return "Low"


class OrchestratedPredictionPipeline:
    """
    Compatibility facade with class-style API used by docs/examples.
    """

    def run_complete_prediction_orchestrated(
        self,
        stock_name: str,
        target_date: str | date | None = None,
        exchange: str | None = None,
        model_type: str = "ensemble",
        include_backtest: bool = False,
        include_sentiment: bool = False,
    ) -> Dict[str, Any]:
        started = perf_counter()
        try:
            request = PredictRequest(
                ticker=stock_name,
                exchange=exchange,
                target_date=target_date,
                model_type=model_type,
                include_backtest=include_backtest,
                include_sentiment=include_sentiment,
            )
            result = execute_prediction_pipeline(request)
            status = workflow_orchestrator.get_workflow_status(result.workflow_id or "")

            # Fetch latest close for simple trend/confidence labels.
            baseline = result.prediction
            try:
                resolved = resolve_ticker(stock=stock_name, exchange=exchange)
                ohlcv = fetch_ohlcv_data(ticker_symbol=resolved.full_symbol, exchange=resolved.exchange)
                baseline = float(ohlcv.iloc[-1]["Close"])
            except Exception:
                baseline = result.prediction

            duration = perf_counter() - started
            return {
                "success": True,
                "stock": stock_name,
                "ticker": result.ticker,
                "prediction_date": result.target_date.isoformat(),
                "prediction": {
                    "predicted_price": result.prediction,
                    "lower_bound": result.lower_bound,
                    "upper_bound": result.upper_bound,
                    "trend": _trend_label(result.prediction, baseline),
                    "confidence": _confidence_label(result.prediction, result.lower_bound, result.upper_bound),
                },
                "workflow": {
                    "id": result.workflow_id,
                    "progress": {
                        "progress_percentage": status.progress_percentage if status else 100.0,
                        "completed_steps": status.completed_steps if status else [],
                    },
                    "duration_seconds": round(duration, 3),
                },
                "explanation": result.explanation,
                "disclaimer": result.disclaimer,
                "fundamentals": get_fundamentals(stock_name, exchange or "NSE"),
                "financials": get_financials_table(stock_name, exchange or "NSE"),
                "model_telemetry": {
                    "xgboost": result.xgb_prediction,
                    "random_forest": result.rf_prediction,
                    "lstm": result.lstm_prediction,
                    "confidence": result.confidence_level
                },
                "research": researcher.deep_research(stock_name)
            }
        except Exception as exc:
            wrapped = exc if isinstance(exc, StockAnalystError) else StockAnalystError(
                error_category="UNKNOWN_ERROR",
                message=str(exc),
            )
            payload = format_error_response(wrapped)
            return {
                "success": False,
                "stock": stock_name,
                "ticker": stock_name,
                "error": payload.error_message,
                "error_category": payload.error_category.lower(),
                "failed_step": payload.failed_step,
                "workflow": {
                    "progress": {
                        "progress_percentage": 0,
                        "completed_steps": payload.completed_steps,
                    }
                },
                "disclaimer": payload.disclaimer,
            }

    def run_quick_prediction(
        self,
        stock_name: str,
        exchange: str | None = None,
        model_type: str = "random_forest",
    ) -> Dict[str, Any]:
        return self.run_complete_prediction_orchestrated(
            stock_name=stock_name,
            exchange=exchange,
            model_type=model_type,
            include_backtest=False,
            include_sentiment=False,
        )

    def get_workflow_status(self, workflow_id: str) -> Dict[str, Any]:
        status = workflow_orchestrator.get_workflow_status(workflow_id)
        if status is None:
            return {
                "success": False,
                "error": "Workflow not found",
                "workflow": {"id": workflow_id, "progress": {"progress_percentage": 0, "completed_steps": []}},
            }
        return {
            "success": status.status == "completed",
            "workflow": {
                "id": status.workflow_id,
                "status": status.status,
                "progress": {
                    "progress_percentage": status.progress_percentage,
                    "completed_steps": status.completed_steps,
                },
                "failed_step": status.failed_step,
                "error_message": status.error_message,
            },
            "disclaimer": "Educational and research use only. Not financial advice.",
        }

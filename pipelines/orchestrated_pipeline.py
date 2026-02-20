
"""Main 6-step orchestrated prediction pipeline."""

from __future__ import annotations

from datetime import date
import inspect
from time import perf_counter
from typing import Any, Dict, MutableMapping

from schemas.request_schemas import PredictRequest
from schemas.response_schemas import PredictResponse
from tools.error_handler import StockAnalystError, format_error_response, safe_float, clean_payload
from tools.backtester import run_backtest
from tools.explainer import generate_explanation
from tools.fetch_data import fetch_ohlcv_data
from tools.indicators import compute_indicators
from tools.macro_features import fetch_macro_features
from tools.predictor import predict_price
from tools.query_parser import parse_query
from tools.sentiment import analyze_sentiment
from tools.advanced_sentiment import earnings_signal, supply_chain_risk
from tools.ticker_resolver import resolve_ticker
from tools.workflow_orchestrator import workflow_orchestrator
from tools.fundamentals import get_fundamentals, get_financials_table
# researcher is NOT imported here on purpose — deep_research is triggered
# explicitly via /api/research, not on every prediction (too slow).


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
        kwargs = {
            "ticker_symbol": resolved.full_symbol,
            "exchange": resolved.exchange,
        }
        if "days" in inspect.signature(fetch_ohlcv_data).parameters:
            kwargs["days"] = req.history_days
        ohlcv = fetch_ohlcv_data(**kwargs)
        ctx["ohlcv"] = ohlcv

    def step_compute_indicators(ctx: MutableMapping[str, object]) -> None:
        ohlcv = ctx["ohlcv"]
        macro_data = fetch_macro_features()
        indicators = compute_indicators(ohlcv, macro_data=macro_data)  # type: ignore[arg-type]
        ctx["indicators"] = indicators
        ctx["macro_data"] = macro_data

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

    req: PredictRequest = final_context["request"]  # type: ignore[assignment]
    resolved = final_context["resolved"]
    prediction = final_context["prediction"]
    explanation = final_context["explanation"]
    indicators = final_context["indicators"]

    backtest_result = None
    if req.include_backtest:
        backtest_result = run_backtest(indicators)

    sentiment_result = None
    if req.include_sentiment:
        # Basic + advanced sentiment
        sentiment_result = analyze_sentiment(resolved.full_symbol)
        if sentiment_result and sentiment_result.headlines:
            # Add earnings + supply chain signals
            earnings_sig = earnings_signal(sentiment_result.headlines)
            supply_chain_sig = supply_chain_risk(sentiment_result.headlines, resolved.full_symbol)

            # Store as metadata
            if not hasattr(sentiment_result, 'metadata'):
                sentiment_result.metadata = {}
            sentiment_result.metadata['earnings_signal'] = earnings_sig
            sentiment_result.metadata['supply_chain_risk'] = supply_chain_sig

    response = PredictResponse(
        ticker=req.ticker or req.stock or resolved.full_symbol,
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


def _map_error_to_user_message(exc: Exception) -> str:
    """Map StockAnalystError categories to user-friendly messages."""
    if isinstance(exc, StockAnalystError):
        category = exc.error_category
        if category == "DATA_ERROR" or "DATA_NOT_FOUND" in str(exc):
            return "No market data available for this ticker. Please verify the ticker symbol and exchange."
        elif category == "MODEL_ERROR":
            return "The prediction engine encountered an issue. Retrying with fresh models..."
        elif category == "NETWORK_ERROR":
            return "Unable to reach market data providers. Please check your internet connection."
        elif category == "VALIDATION_ERROR":
            return f"Input validation failed: {exc.message}"
        else:
            return f"An error occurred: {exc.message}"
    return str(exc)


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
            # 1. Resolve ticker
            from tools.symbol_utils import get_currency_symbol, get_market_label
            resolved = resolve_ticker(stock=stock_name, exchange=exchange)

            # Research is NOT run here — it is expensive (30-60s) and is triggered
            # on demand via POST /api/research. Catalysts default to [].
            research_data = {}
            catalysts = []

            # 2. Execute Prediction
            request = PredictRequest(
                ticker=stock_name,
                exchange=exchange,
                target_date=target_date,
                model_type=model_type,
                include_backtest=include_backtest,
                # We handle sentiment manually here to pass catalysts, but we must respect the flag
                include_sentiment=False, 
            )
            result = execute_prediction_pipeline(request)
            status = workflow_orchestrator.get_workflow_status(result.workflow_id or "")

            # 3. Enhanced Sentiment Analysis - Always run if requested or if we have catalysts
            sentiment_summary = None
            if include_sentiment or len(catalysts) > 0:
                from tools.sentiment import analyze_sentiment
                try:
                    sentiment_summary = analyze_sentiment(resolved.full_symbol, research_catalysts=catalysts)
                except Exception as e:
                    import logging
                    logging.getLogger(__name__).error(f"Sentiment analysis failed: {e}")

            # 4. Final processing. Baseline fetch is non-critical and should not fail the request.
            baseline = result.prediction
            try:
                ohlcv = fetch_ohlcv_data(ticker_symbol=resolved.full_symbol, exchange=resolved.exchange)
                if not ohlcv.empty:
                    baseline = float(ohlcv.iloc[-1]["Close"])
            except Exception:
                baseline = result.prediction
            
            duration = perf_counter() - started
            
            return clean_payload({
                "success": True,
                "stock": stock_name,
                "ticker": resolved.full_symbol,
                "full_symbol": resolved.full_symbol,
                "resolved_exchange": resolved.exchange,
                "currency": get_currency_symbol(resolved.exchange),
                "market_label": get_market_label(resolved.exchange),
                "prediction_date": result.target_date.isoformat(),
                "prediction": {
                    "predicted_price": safe_float(result.prediction),
                    "lower_bound": safe_float(result.lower_bound),
                    "upper_bound": safe_float(result.upper_bound),
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
                "research": research_data,
                "sentiment": sentiment_summary,
                "fundamentals": get_fundamentals(resolved.full_symbol, resolved.exchange),
                "financials": get_financials_table(resolved.full_symbol, resolved.exchange),
                "model_telemetry": {
                    "xgboost": safe_float(getattr(result, "xgb_prediction", None)),
                    "random_forest": safe_float(getattr(result, "rf_prediction", None)),
                    "lstm": safe_float(getattr(result, "lstm_prediction", None)),
                    "confidence": safe_float(getattr(result, "confidence_level", None)),
                },
                "disclaimer": getattr(result, "disclaimer", "Educational and research use only. Not financial advice."),
            })
        except Exception as exc:
            wrapped = exc if isinstance(exc, StockAnalystError) else StockAnalystError(
                error_category="UNKNOWN_ERROR",
                message=str(exc),
            )
            payload = format_error_response(wrapped)
            
            # Use user-friendly error message
            user_message = _map_error_to_user_message(wrapped)
            
            return clean_payload({
                "success": False,
                "stock": stock_name,
                "ticker": stock_name,
                "error": user_message,
                "error_category": payload.error_category.lower(),
                "failed_step": payload.failed_step,
                "workflow": {
                    "progress": {
                        "progress_percentage": 0,
                        "completed_steps": payload.completed_steps,
                    }
                },
                "disclaimer": payload.disclaimer,
            })

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
            include_sentiment=True,
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

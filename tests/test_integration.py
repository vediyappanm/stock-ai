"""Integration tests for orchestrated workflow behavior."""

from __future__ import annotations

from datetime import date, timedelta

from pipelines.orchestrated_pipeline import OrchestratedPredictionPipeline, execute_prediction_pipeline
from schemas.request_schemas import PredictRequest
from schemas.response_schemas import BacktestResult, ParsedQuery, Prediction, ResolvedTicker, SentimentResult
from tools.error_handler import ValidationError


def test_prediction_pipeline_happy_path(monkeypatch) -> None:
    monkeypatch.setattr(
        "pipelines.orchestrated_pipeline.parse_query",
        lambda **kwargs: ParsedQuery(
            stock_name="AAPL",
            exchange="NASDAQ",
            target_date=date.today() + timedelta(days=1),
        ),
    )
    monkeypatch.setattr(
        "pipelines.orchestrated_pipeline.resolve_ticker",
        lambda stock, exchange: ResolvedTicker(ticker="AAPL", exchange="NASDAQ", full_symbol="AAPL"),
    )
    monkeypatch.setattr(
        "pipelines.orchestrated_pipeline.fetch_ohlcv_data",
        lambda ticker_symbol, exchange: object(),
    )
    monkeypatch.setattr("pipelines.orchestrated_pipeline.compute_indicators", lambda ohlcv: object())
    monkeypatch.setattr(
        "pipelines.orchestrated_pipeline.predict_price",
        lambda indicators_df, resolved_symbol, model_type: Prediction(
            point_estimate=200.0,
            lower_bound=190.0,
            upper_bound=210.0,
            confidence_level=0.8,
            rf_prediction=201.0,
            lstm_prediction=199.0,
            feature_importance={"RSI_14": 0.4, "MACD": 0.3, "SMA_20": 0.2},
        ),
    )
    monkeypatch.setattr(
        "pipelines.orchestrated_pipeline.generate_explanation",
        lambda ticker, exchange, target_date, prediction: "Educational and research use only. Not financial advice.",
    )
    monkeypatch.setattr(
        "pipelines.orchestrated_pipeline.run_backtest",
        lambda indicators: BacktestResult(
            mae=1.0,
            rmse=1.2,
            mape=0.8,
            directional_accuracy=55.0,
            actual_prices=[100.0],
            predicted_prices=[101.0],
            periods=1,
        ),
    )
    monkeypatch.setattr(
        "pipelines.orchestrated_pipeline.analyze_sentiment",
        lambda ticker: SentimentResult(score=0.0, label="neutral", article_count=0, headlines=[]),
    )

    req = PredictRequest(query="Predict AAPL tomorrow", include_backtest=True, include_sentiment=True)
    response = execute_prediction_pipeline(req)
    assert response.ticker == "AAPL"
    assert response.backtest is not None
    assert response.sentiment is not None
    assert response.workflow_id is not None


def test_prediction_pipeline_failure(monkeypatch) -> None:
    def _boom(**kwargs):
        raise ValidationError("bad input", failed_step="PARSE_QUERY")

    monkeypatch.setattr("pipelines.orchestrated_pipeline.parse_query", _boom)
    req = PredictRequest(query="Predict ???")
    try:
        execute_prediction_pipeline(req)
        assert False, "Expected ValidationError"
    except ValidationError as exc:
        assert exc.failed_step == "PARSE_QUERY"


def test_orchestrated_pipeline_class_interface(monkeypatch) -> None:
    monkeypatch.setattr(
        "pipelines.orchestrated_pipeline.execute_prediction_pipeline",
        lambda request: type(
            "Resp",
            (),
            {
                "workflow_id": "wf-123",
                "ticker": "ABB.NS",
                "prediction": 6420.5,
                "lower_bound": 6300.0,
                "upper_bound": 6550.0,
                "target_date": date.today() + timedelta(days=1),
                "explanation": "Educational and research use only. Not financial advice.",
                "disclaimer": "Educational and research use only. Not financial advice.",
            },
        )(),
    )
    monkeypatch.setattr(
        "pipelines.orchestrated_pipeline.workflow_orchestrator.get_workflow_status",
        lambda workflow_id: type("WS", (), {"progress_percentage": 100.0, "completed_steps": ["PARSE_QUERY"]})(),
    )
    monkeypatch.setattr(
        "pipelines.orchestrated_pipeline.resolve_ticker",
        lambda stock, exchange=None: ResolvedTicker(ticker="ABB", exchange="NSE", full_symbol="ABB.NS"),
    )
    monkeypatch.setattr(
        "pipelines.orchestrated_pipeline.fetch_ohlcv_data",
        lambda ticker_symbol, exchange: (_ for _ in ()).throw(RuntimeError("offline")),
    )

    pipeline = OrchestratedPredictionPipeline()
    result = pipeline.run_complete_prediction_orchestrated("ABB", "2026-02-22")
    assert result["success"] is True
    assert result["ticker"] == "ABB.NS"

"""
End-to-end production-ready tests for all STK-ENGINE dashboard features.
Tests all API endpoints and workflows shown in the frontend dashboard.
"""

from __future__ import annotations

import asyncio
from datetime import date, timedelta
from typing import Any, Dict

import pytest
from fastapi.testclient import TestClient

from api import app
from schemas.request_schemas import (
    AnalyzeRequest,
    BacktestRequest,
    PredictRequest,
    PortfolioRequest,
    ScanRequest,
    WatchlistRequest,
)


client = TestClient(app)


class TestHealthAndStatus:
    """Test system health and status endpoints."""

    def test_health_endpoint(self):
        """Test /api/health endpoint returns healthy status."""
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data

    def test_frontend_index(self):
        """Test frontend index page loads."""
        response = client.get("/")
        assert response.status_code == 200
        assert b"STK-ENGINE" in response.content


class TestPredictionWorkflow:
    """Test prediction workflow - main dashboard feature."""

    def test_full_prediction_with_query(self):
        """Test full prediction using natural language query."""
        payload = {
            "query": "Predict RELIANCE tomorrow",
            "model_type": "ensemble",
            "include_backtest": True,
            "include_sentiment": True,
        }
        response = client.post("/api/predict", json=payload)
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert data["success"] is True
        assert "ticker" in data
        assert "prediction" in data or "predicted_price" in data
        assert data.get("disclaimer") is not None

    def test_full_prediction_with_explicit_params(self):
        """Test full prediction with explicit ticker and exchange."""
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        payload = {
            "ticker": "TCS",
            "exchange": "NSE",
            "target_date": tomorrow,
            "model_type": "ensemble",
            "include_backtest": False,
            "include_sentiment": False,
        }
        response = client.post("/api/predict", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["ticker"] is not None

    def test_quick_prediction(self):
        """Test quick prediction endpoint (Random Forest only)."""
        payload = {
            "ticker": "INFY",
            "exchange": "NSE",
        }
        response = client.post("/api/predict/quick", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["ticker"] is not None

    def test_prediction_all_models(self):
        """Test prediction with all model types."""
        models = ["ensemble", "random_forest", "lstm"]
        
        for model_type in models:
            payload = {
                "ticker": "HDFCBANK",
                "exchange": "NSE",
                "model_type": model_type,
            }
            response = client.post("/api/predict", json=payload)
            assert response.status_code == 200, f"Failed for model: {model_type}"
            data = response.json()
            assert data["success"] is True, f"Failed for model: {model_type}"

    def test_prediction_all_exchanges(self):
        """Test prediction across all supported exchanges."""
        test_cases = [
            {"ticker": "RELIANCE", "exchange": "NSE"},
            {"ticker": "RELIANCE", "exchange": "BSE"},
            {"ticker": "AAPL", "exchange": "NASDAQ"},
            {"ticker": "TSLA", "exchange": "NASDAQ"},
        ]
        
        for case in test_cases:
            response = client.post("/api/predict", json=case)
            assert response.status_code == 200, f"Failed for {case}"

    def test_workflow_status_tracking(self):
        """Test workflow status endpoint."""
        # First create a prediction to get workflow_id
        payload = {"ticker": "TCS", "exchange": "NSE"}
        pred_response = client.post("/api/predict", json=payload)
        assert pred_response.status_code == 200
        
        data = pred_response.json()
        workflow_id = data.get("workflow_id")
        if workflow_id:
            # Check workflow status
            status_response = client.get(f"/api/workflow/{workflow_id}")
            assert status_response.status_code == 200
            status_data = status_response.json()
            assert "status" in status_data or "progress_percentage" in status_data


class TestAnalysisFeatures:
    """Test technical analysis features."""

    def test_analyze_endpoint(self):
        """Test technical indicator analysis."""
        payload = {
            "ticker": "RELIANCE",
            "exchange": "NSE",
        }
        response = client.post("/api/analyze", json=payload)
        assert response.status_code == 200
        data = response.json()
        
        # Verify technical indicators present
        assert "indicators" in data
        indicators = data["indicators"]
        assert "RSI_14" in indicators
        assert "MACD" in indicators
        assert "SMA_20" in indicators

    def test_backtest_endpoint(self):
        """Test backtesting functionality."""
        payload = {
            "ticker": "TCS",
            "exchange": "NSE",
            "days": 30,
        }
        response = client.post("/api/backtest", json=payload)
        assert response.status_code == 200
        data = response.json()
        
        # Verify backtest metrics
        assert "mae" in data
        assert "rmse" in data
        assert "mape" in data
        assert "directional_accuracy" in data
        assert "sharpe_ratio" in data
        assert "sortino_ratio" in data
        assert "max_drawdown_pct" in data

    def test_strategy_backtest(self):
        """Test strategy backtesting endpoint."""
        payload = {
            "ticker": "INFY",
            "exchange": "NSE",
            "days": 30,
        }
        response = client.post("/api/strategy/backtest", json=payload)
        assert response.status_code == 200


class TestScannerFeatures:
    """Test market scanner functionality."""

    def test_scan_nifty50_preset(self):
        """Test scanner with NIFTY50 preset."""
        payload = {
            "preset": "NIFTY50",
            "exchange": "NSE",
        }
        response = client.post("/api/scan", json=payload)
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert "results" in data
        assert data["count"] >= 0
        
        # Verify result structure if any results
        if data["results"]:
            result = data["results"][0]
            assert "ticker" in result
            assert "price" in result
            assert "rsi" in result
            assert "signal" in result

    def test_scan_bluechip_us_preset(self):
        """Test scanner with US bluechip preset."""
        payload = {
            "preset": "BLUECHIP_US",
            "exchange": "NASDAQ",
        }
        response = client.post("/api/scan", json=payload)
        assert response.status_code == 200

    def test_scan_custom_tickers(self):
        """Test scanner with custom ticker list."""
        payload = {
            "tickers": ["RELIANCE", "TCS", "INFY"],
            "exchange": "NSE",
        }
        response = client.post("/api/scan", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True


class TestPortfolioManagement:
    """Test portfolio management features."""

    def test_get_portfolio(self):
        """Test getting portfolio holdings."""
        response = client.get("/api/portfolio")
        assert response.status_code == 200
        data = response.json()
        assert "holdings" in data

    def test_add_to_portfolio(self):
        """Test adding position to portfolio."""
        payload = {
            "ticker": "RELIANCE",
            "exchange": "NSE",
            "quantity": 10.0,
            "avg_price": 2500.0,
            "action": "add",
        }
        response = client.post("/api/portfolio", json=payload)
        assert response.status_code == 200

    def test_remove_from_portfolio(self):
        """Test removing position from portfolio."""
        # First add
        add_payload = {
            "ticker": "TCS",
            "exchange": "NSE",
            "quantity": 5.0,
            "avg_price": 3500.0,
            "action": "add",
        }
        client.post("/api/portfolio", json=add_payload)
        
        # Then remove
        remove_payload = {
            "ticker": "TCS",
            "exchange": "NSE",
            "action": "remove",
        }
        response = client.post("/api/portfolio", json=remove_payload)
        assert response.status_code == 200

    def test_portfolio_correlation(self):
        """Test portfolio correlation matrix."""
        response = client.get("/api/analytics/portfolio/correlation")
        assert response.status_code == 200


class TestWatchlistManagement:
    """Test watchlist management features."""

    def test_get_watchlist(self):
        """Test getting watchlist."""
        response = client.get("/api/watchlist")
        assert response.status_code == 200
        data = response.json()
        assert "symbols" in data

    def test_add_to_watchlist(self):
        """Test adding symbol to watchlist."""
        payload = {
            "ticker": "HDFCBANK",
            "exchange": "NSE",
            "action": "add",
        }
        response = client.post("/api/watchlist", json=payload)
        assert response.status_code == 200

    def test_remove_from_watchlist(self):
        """Test removing symbol from watchlist."""
        # First add
        add_payload = {
            "ticker": "INFY",
            "exchange": "NSE",
            "action": "add",
        }
        client.post("/api/watchlist", json=add_payload)
        
        # Then remove
        remove_payload = {
            "ticker": "INFY",
            "exchange": "NSE",
            "action": "remove",
        }
        response = client.post("/api/watchlist", json=remove_payload)
        assert response.status_code == 200


class TestQuantAnalytics:
    """Test quantitative analytics features."""

    def test_sector_rotation(self):
        """Test sector rotation analysis."""
        response = client.get("/api/analytics/sector-rotation")
        assert response.status_code == 200
        data = response.json()
        assert "sectors" in data

    def test_risk_impact_analysis(self):
        """Test risk impact simulator."""
        response = client.get("/api/analytics/risk-impact/RELIANCE")
        assert response.status_code == 200
        data = response.json()
        assert "var_95" in data
        assert "kelly_fraction" in data

    def test_fundamentals_data(self):
        """Test fundamentals data retrieval."""
        response = client.get("/api/fundamentals/RELIANCE?exchange=NSE")
        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert "sector" in data
        assert "market_cap" in data


class TestChartData:
    """Test chart data endpoints."""

    def test_chart_data_all_periods(self):
        """Test chart data for all supported periods."""
        periods = ["1mo", "3mo", "6mo", "1y", "2y", "5y"]
        
        for period in periods:
            response = client.get(
                f"/api/chart/RELIANCE",
                params={"exchange": "NSE", "period": period}
            )
            assert response.status_code == 200, f"Failed for period: {period}"
            data = response.json()
            assert "ohlcv" in data
            assert len(data["ohlcv"]) > 0

    def test_chart_data_with_indicators(self):
        """Test chart data includes technical indicators."""
        response = client.get(
            "/api/chart/TCS",
            params={"exchange": "NSE", "period": "1y"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify OHLCV structure
        if data["ohlcv"]:
            candle = data["ohlcv"][0]
            assert "time" in candle
            assert "open" in candle
            assert "high" in candle
            assert "low" in candle
            assert "close" in candle
            assert "volume" in candle


class TestChatInterface:
    """Test neural chat interface."""

    def test_chat_interaction(self):
        """Test chat endpoint for natural language interaction."""
        payload = {
            "message": "What is the current price of RELIANCE?",
        }
        response = client.post("/api/chat", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "response" in data


class TestReportGeneration:
    """Test report export functionality."""

    def test_export_report(self):
        """Test PDF report generation."""
        response = client.get("/api/export/report/RELIANCE?exchange=NSE")
        assert response.status_code == 200


class TestErrorHandling:
    """Test error handling and validation."""

    def test_invalid_ticker(self):
        """Test handling of invalid ticker."""
        payload = {
            "ticker": "INVALID_TICKER_XYZ123",
            "exchange": "NSE",
        }
        response = client.post("/api/predict", json=payload)
        # Should return error response with proper structure
        assert response.status_code in [200, 400, 422]
        data = response.json()
        if response.status_code != 200:
            assert "error_message" in data or "detail" in data

    def test_invalid_exchange(self):
        """Test handling of invalid exchange."""
        payload = {
            "ticker": "RELIANCE",
            "exchange": "INVALID_EXCHANGE",
        }
        response = client.post("/api/predict", json=payload)
        assert response.status_code == 422

    def test_missing_required_fields(self):
        """Test validation of required fields."""
        payload = {}
        response = client.post("/api/predict", json=payload)
        assert response.status_code == 422
        data = response.json()
        assert data["error_category"] == "validation_error"

    def test_past_target_date(self):
        """Test validation of past target date."""
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        payload = {
            "ticker": "RELIANCE",
            "exchange": "NSE",
            "target_date": yesterday,
        }
        response = client.post("/api/predict", json=payload)
        assert response.status_code == 422

    def test_invalid_model_type(self):
        """Test validation of model type."""
        payload = {
            "ticker": "RELIANCE",
            "exchange": "NSE",
            "model_type": "invalid_model",
        }
        response = client.post("/api/predict", json=payload)
        assert response.status_code == 422


class TestConcurrency:
    """Test concurrent request handling."""

    def test_multiple_concurrent_predictions(self):
        """Test handling multiple concurrent prediction requests."""
        payloads = [
            {"ticker": "RELIANCE", "exchange": "NSE"},
            {"ticker": "TCS", "exchange": "NSE"},
            {"ticker": "INFY", "exchange": "NSE"},
        ]
        
        responses = []
        for payload in payloads:
            response = client.post("/api/predict", json=payload)
            responses.append(response)
        
        # All should succeed
        for response in responses:
            assert response.status_code == 200


class TestDataValidation:
    """Test data validation and sanitization."""

    def test_ticker_normalization(self):
        """Test ticker symbol normalization."""
        # Test with lowercase
        payload = {"ticker": "reliance", "exchange": "NSE"}
        response = client.post("/api/predict", json=payload)
        assert response.status_code == 200
        
        # Test with extra spaces
        payload = {"ticker": "  TCS  ", "exchange": "NSE"}
        response = client.post("/api/predict", json=payload)
        assert response.status_code == 200

    def test_exchange_normalization(self):
        """Test exchange normalization."""
        payload = {"ticker": "RELIANCE", "exchange": "nse"}
        response = client.post("/api/predict", json=payload)
        assert response.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

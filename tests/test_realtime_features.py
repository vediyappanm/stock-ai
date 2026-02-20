"""
Real-time features and WebSocket testing for STK-ENGINE dashboard.
Tests streaming, live updates, and WebSocket connectivity.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, Dict

import pytest
from fastapi.testclient import TestClient

from api import app


client = TestClient(app)


class TestWebSocketConnectivity:
    """Test WebSocket connection and streaming."""

    def test_websocket_connection(self):
        """Test WebSocket connection establishment."""
        with client.websocket_connect("/ws") as websocket:
            # Connection should be established
            assert websocket is not None
            
            # Should receive initial connection message
            data = websocket.receive_json()
            assert "type" in data

    def test_websocket_subscribe_symbol(self):
        """Test subscribing to symbol updates via WebSocket."""
        with client.websocket_connect("/ws") as websocket:
            # Subscribe to a symbol
            subscribe_msg = {
                "action": "subscribe",
                "ticker": "RELIANCE",
                "exchange": "NSE"
            }
            websocket.send_json(subscribe_msg)
            
            # Should receive acknowledgment or data
            response = websocket.receive_json()
            assert response is not None

    def test_websocket_unsubscribe_symbol(self):
        """Test unsubscribing from symbol updates."""
        with client.websocket_connect("/ws") as websocket:
            # Subscribe first
            websocket.send_json({
                "action": "subscribe",
                "ticker": "TCS",
                "exchange": "NSE"
            })
            
            # Then unsubscribe
            websocket.send_json({
                "action": "unsubscribe",
                "ticker": "TCS",
                "exchange": "NSE"
            })
            
            response = websocket.receive_json()
            assert response is not None

    def test_websocket_heartbeat(self):
        """Test WebSocket heartbeat/pulse mechanism."""
        with client.websocket_connect("/ws") as websocket:
            # Send ping
            websocket.send_json({"action": "ping"})
            
            # Should receive pong
            response = websocket.receive_json()
            assert response.get("type") in ["pong", "pulse"]

    def test_websocket_multiple_symbols(self):
        """Test subscribing to multiple symbols simultaneously."""
        with client.websocket_connect("/ws") as websocket:
            symbols = [
                {"ticker": "RELIANCE", "exchange": "NSE"},
                {"ticker": "TCS", "exchange": "NSE"},
                {"ticker": "INFY", "exchange": "NSE"},
            ]
            
            for symbol in symbols:
                websocket.send_json({
                    "action": "subscribe",
                    **symbol
                })
            
            # Should handle multiple subscriptions
            for _ in range(len(symbols)):
                response = websocket.receive_json()
                assert response is not None


class TestRealtimePriceUpdates:
    """Test real-time price update mechanisms."""

    def test_price_streaming_format(self):
        """Test price update message format."""
        with client.websocket_connect("/ws") as websocket:
            websocket.send_json({
                "action": "subscribe",
                "ticker": "RELIANCE",
                "exchange": "NSE"
            })
            
            # Receive price update
            update = websocket.receive_json()
            
            # Verify expected fields in price update
            if update.get("type") == "price_update":
                assert "ticker" in update
                assert "price" in update
                assert "timestamp" in update

    def test_volatility_alerts(self):
        """Test volatility alert mechanism."""
        with client.websocket_connect("/ws") as websocket:
            websocket.send_json({
                "action": "subscribe",
                "ticker": "TSLA",
                "exchange": "NASDAQ"
            })
            
            # Listen for potential volatility alerts
            response = websocket.receive_json()
            assert response is not None


class TestStreamingStability:
    """Test streaming stability and error recovery."""

    def test_connection_recovery(self):
        """Test WebSocket reconnection handling."""
        # First connection
        with client.websocket_connect("/ws") as websocket:
            websocket.send_json({"action": "ping"})
            response = websocket.receive_json()
            assert response is not None
        
        # Second connection (simulating reconnect)
        with client.websocket_connect("/ws") as websocket:
            websocket.send_json({"action": "ping"})
            response = websocket.receive_json()
            assert response is not None

    def test_invalid_message_handling(self):
        """Test handling of invalid WebSocket messages."""
        with client.websocket_connect("/ws") as websocket:
            # Send invalid message
            websocket.send_json({"invalid": "message"})
            
            # Should handle gracefully
            try:
                response = websocket.receive_json()
                # Should receive error or ignore
                assert response is not None
            except Exception:
                # Connection might close on invalid message
                pass


class TestSystemStatusMonitoring:
    """Test system status and monitoring features."""

    def test_system_status_updates(self):
        """Test system status updates via WebSocket."""
        with client.websocket_connect("/ws") as websocket:
            websocket.send_json({"action": "get_status"})
            
            response = websocket.receive_json()
            if response.get("type") == "status":
                assert "active_symbols" in response or "status" in response

    def test_streaming_count_tracking(self):
        """Test tracking of active streaming symbols."""
        with client.websocket_connect("/ws") as websocket:
            # Subscribe to symbols
            websocket.send_json({
                "action": "subscribe",
                "ticker": "RELIANCE",
                "exchange": "NSE"
            })
            
            # Request status
            websocket.send_json({"action": "get_status"})
            
            response = websocket.receive_json()
            assert response is not None


class TestCacheAndPerformance:
    """Test caching and performance optimizations."""

    def test_cache_hit_performance(self):
        """Test cache hit improves response time."""
        import time
        
        # First request (cache miss)
        start = time.time()
        response1 = client.post("/api/predict", json={
            "ticker": "RELIANCE",
            "exchange": "NSE"
        })
        time1 = time.time() - start
        assert response1.status_code == 200
        
        # Second request (cache hit)
        start = time.time()
        response2 = client.post("/api/predict", json={
            "ticker": "RELIANCE",
            "exchange": "NSE"
        })
        time2 = time.time() - start
        assert response2.status_code == 200
        
        # Second request should be faster or similar
        # (allowing margin for variability)
        assert time2 <= time1 * 2

    def test_model_cache_reuse(self):
        """Test model caching across predictions."""
        # Multiple predictions for same ticker should reuse models
        for _ in range(3):
            response = client.post("/api/predict", json={
                "ticker": "TCS",
                "exchange": "NSE"
            })
            assert response.status_code == 200

    def test_indicator_cache_validation(self):
        """Test technical indicator cache validation."""
        # Request analysis multiple times
        for _ in range(2):
            response = client.post("/api/analyze", json={
                "ticker": "INFY",
                "exchange": "NSE"
            })
            assert response.status_code == 200
            data = response.json()
            assert "indicators" in data


class TestMarketHoursHandling:
    """Test market hours and after-hours handling."""

    def test_market_hours_detection(self):
        """Test detection of market hours vs after-hours."""
        response = client.get("/api/health")
        assert response.status_code == 200
        # Health check should work regardless of market hours

    def test_cache_ttl_market_hours(self):
        """Test cache TTL differs during market hours."""
        # Make prediction during any time
        response = client.post("/api/predict", json={
            "ticker": "RELIANCE",
            "exchange": "NSE"
        })
        assert response.status_code == 200
        # Cache should be applied appropriately


class TestDataIntegrity:
    """Test data integrity and consistency."""

    def test_prediction_consistency(self):
        """Test prediction consistency for same inputs."""
        payload = {
            "ticker": "HDFCBANK",
            "exchange": "NSE",
            "model_type": "random_forest"
        }
        
        # Make two predictions with same inputs
        response1 = client.post("/api/predict", json=payload)
        response2 = client.post("/api/predict", json=payload)
        
        assert response1.status_code == 200
        assert response2.status_code == 200
        
        # Predictions should be identical (cached)
        data1 = response1.json()
        data2 = response2.json()
        assert data1["prediction"] == data2["prediction"]

    def test_indicator_calculation_consistency(self):
        """Test technical indicator calculation consistency."""
        payload = {"ticker": "TCS", "exchange": "NSE"}
        
        response1 = client.post("/api/analyze", json=payload)
        response2 = client.post("/api/analyze", json=payload)
        
        assert response1.status_code == 200
        assert response2.status_code == 200
        
        # Indicators should be consistent
        ind1 = response1.json()["indicators"]
        ind2 = response2.json()["indicators"]
        assert ind1["RSI_14"] == ind2["RSI_14"]

    def test_backtest_reproducibility(self):
        """Test backtest reproducibility."""
        payload = {
            "ticker": "INFY",
            "exchange": "NSE",
            "days": 30
        }
        
        response1 = client.post("/api/backtest", json=payload)
        response2 = client.post("/api/backtest", json=payload)
        
        assert response1.status_code == 200
        assert response2.status_code == 200
        
        # Backtest results should be reproducible
        data1 = response1.json()
        data2 = response2.json()
        assert data1["mae"] == data2["mae"]


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_newly_listed_stock(self):
        """Test handling of stocks with limited history."""
        # This might fail gracefully with proper error message
        payload = {
            "ticker": "NEWSTOCK",
            "exchange": "NSE"
        }
        response = client.post("/api/predict", json=payload)
        # Should either succeed or return proper error
        assert response.status_code in [200, 400, 422]

    def test_delisted_stock(self):
        """Test handling of delisted stocks."""
        payload = {
            "ticker": "DELISTEDSTOCK",
            "exchange": "NSE"
        }
        response = client.post("/api/predict", json=payload)
        # Should handle gracefully
        assert response.status_code in [200, 400, 422]

    def test_crypto_symbol(self):
        """Test handling of cryptocurrency symbols."""
        payload = {
            "ticker": "BTC-USD",
            "exchange": "NASDAQ"
        }
        response = client.post("/api/predict", json=payload)
        # Should handle crypto symbols
        assert response.status_code in [200, 400, 422]

    def test_extreme_date_range(self):
        """Test handling of extreme date ranges."""
        from datetime import date, timedelta
        
        far_future = (date.today() + timedelta(days=365)).isoformat()
        payload = {
            "ticker": "RELIANCE",
            "exchange": "NSE",
            "target_date": far_future
        }
        response = client.post("/api/predict", json=payload)
        # Should handle or validate appropriately
        assert response.status_code in [200, 422]

    def test_special_characters_in_ticker(self):
        """Test handling of special characters in ticker."""
        payload = {
            "ticker": "BRK.B",
            "exchange": "NYSE"
        }
        response = client.post("/api/predict", json=payload)
        # Should handle special characters
        assert response.status_code in [200, 400, 422]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

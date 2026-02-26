# STK-ENGINE Technical Documentation

## 1. System Overview
STK-ENGINE is an asynchronous, modular financial intelligence system. It is designed to operate in cloud environments (like Render or AWS) where standard scraping techniques are frequently blocked. The system uses a "Cloud-Resilient" strategy, prioritizing authenticated APIs and direct JSON endpoints.

---

## 2. Core Modules

### 2.1 Backend (api.py)
The core API is built on **FastAPI**. It handles:
- **REST Endpoints**: `/api/predict`, `/api/chart-data`, `/api/health`, etc.
- **WebSocket Streaming**: `/ws/stream` for real-time broadcasts.
- **Lifespan Management**: Initializes background streaming tasks and cache managers on startup.

### 2.2 Prediction Pipeline (pipelines/orchestrated_pipeline.py)
Every prediction goes through a 6-step `OrchestratedPredictionPipeline`:
1.  **Ticker Resolution**: Uses `tools/ticker_resolver.py` to map common names to canonical exchange symbols.
2.  **Market Data**: Uses `tools/fetch_data.py` to pull OHLCV data.
3.  **Feature Engineering**: Uses `tools/indicators.py` to calculate RSI, MACD, Bollinger Bands, and merges Macro features (VIX, 10Y Yield) via `tools/macro_features.py`.
4.  **Ensemble Inference**: Uses `tools/predictor.py` to run models in parallel.
5.  **Uncertainty Estimation**: Computes an 80% confidence interval based on model residuals.
6.  **Explanation**: Uses `tools/explainer.py` to generate a human-readable summary.

### 2.3 Machine Learning (stk_models/)
- **XGBoost**: Primary gradient-boosted model for high-stability predictions.
- **Random Forest**: Secondary model used for ensemble robustness.
- **Ensemble Logic**: Uses a weighted combination. If volatility is high, the system adjusts weights dynamically to favor more trend-aware components.
- **Resilience**: The system is "Torch-Optional". If PyTorch is unavailable (image size limits), the LSTM component gracefully degrades without crashing the pipeline.

---

## 3. Data Strategy (The "Resilience Matrix")

To ensure 100% uptime in cloud environments, `fetch_data.py` follows this priority:
1.  **Local/Redis Cache**: Checks for fresh data (15m TTL during market hours).
2.  **Alpaca Markets**: Primary source for US (NYSE/NASDAQ) stocks via API Key.
3.  **Finnhub**: Primary source for Global/Indian stocks via API Key.
4.  **Yahoo v8 Direct**: Direct JSON chart API (bypass crumb/cookie blocks).
5.  **yfinance library**: Last-resort fallback for local debugging.

---

## 4. Frontend Architecture (frontend/)
Built using **Vanilla Javascript** and **Modern CSS**.
- **Charts**: Integration with **TradingView Lightweight Charts** (v4/v5 compatibility).
- **KPI Dash**: Real-time update of live price, forecast, and trend.
- **Modular Components**: Separate scripts for enhanced charts, real-time indicators, and price tables.
- **State Management**: Local `state` object in `app.js` to manage active tickers and cache.

---

## 5. API Reference

| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `/api/predict` | `POST` | Full 6-step prediction with optional backtest/sentiment. |
| `/api/chart-data/{ticker}` | `GET` | Fetches historical data for chart rendering. |
| `/api/research/{ticker}` | `GET` | Triggers the Deep Research agent (news + synthesis). |
| `/api/health` | `GET` | Returns system health, cache status, and latency metrics. |
| `/ws/stream` | `WS` | Real-time price updates channel. |

---

## 6. Skills Architecture
The system includes a production-grade "Skills" engine that extends the platform's capabilities:
- **skill-creator**: Tools for scaffolding and packaging new AI tools.
- **frontend-design**: A living design system for ensuring premium UI/UX consistency.
- **web-artifacts-builder**: Automated React/Vite/shadcn/ui toolchain for generating interactive web artifacts.
- **mcp-builder**: Integration layer for Model Context Protocol (MCP) servers (stdio, SSE).
- **Clean Architecture**: Follows a strict domain/infrastructure separation with typed boundaries and a "Result" pattern for fallible operations.

---

## 7. Deployment Guide

### Render / Docker
Standard `Dockerfile` setup. The app requires `requirements.txt` and an `.env` with at least `FINNHUB_API_KEY`.

### Scaling Caching
The system defaults to in-memory caching but automatically switches to **Redis** if `REDIS_URL` is detected. This is essential for horizontally scaled deployments.

---

## 8. Developer Notes
- **Ticker Aliases**: Located in `tools/ticker_resolver.py`. Update this table to add support for common stock names.
- **Technical Indicators**: Managed in `tools/indicators.py`. The "Reality Gap" is minimized by ensuring features used in training exactly match the real-time pipeline.
- **Error Handling**: Custom `StockAnalystError` levels provide user-friendly messages vs. raw tracebacks.

---
*Created by the STK-ENGINE Core Team. Updated February 2026. (v2.2.0)*

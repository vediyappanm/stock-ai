# STK-ENGINE: AI-Powered Stock Intelligence Platform

![STK-ENGINE Banner](https://img.shields.io/badge/Status-Production--Ready-brightgreen)
![Python Version](https://img.shields.io/badge/Python-3.11+-blue)
![FastAPI](https://img.shields.io/badge/Framework-FastAPI-009688)
![ML](https://img.shields.io/badge/Models-XGBoost%20|%20RF-orange)

STK-ENGINE is a high-performance, production-grade stock analysis and prediction platform. It combines machine learning ensembles, real-time market data telemetry, and deep research agents to provide institutional-grade insights for retail traders.

## 🚀 Quick Start

### 1. Prerequisites
- Python 3.11 or higher
- Redis (Optional, recommended for caching)
- API Keys: Finnhub (Global data), Alpaca (US Data)

### 2. Installation
```bash
git clone https://github.com/vediyappanm/stock-ai.git
cd stock-ai
pip install -r requirements.txt
```

### 3. Configuration
Create a `.env` file in the root directory:
```env
FINNHUB_API_KEY=your_key_here
APCA_API_KEY_ID=your_key_here
APCA_API_SECRET_KEY=your_key_here
OPENAI_API_KEY=your_key_here
REDIS_URL=redis://localhost:6379
```

### 4. Running the App
```bash
python api.py
```
Visit `http://localhost:8000` to access the dashboard.

---

## 🛠️ Key Features

- **Ensemble Prediction Engine**: Combines XGBoost and Random Forest models with a graceful fallback system.
- **Deep Research Agent**: Automated research synthesis using RAG (Retrieval-Augmented Generation) and web search.
- **Multi-Source Data Strategy**: Resilient data fetching prioritizing Alpaca (US) and Finnhub (Global) with direct Yahoo v8/v7 fallbacks to bypass IP blocking.
- **Real-time Monitoring**: WebSocket-based live price streaming for watchlists and portfolios.
- **Production Dashboard**: Interactive charts (TradingView Lightweight Charts), technical indicators, and fundamental analytics.
- **Quant Analytics**: Backtesting, correlation matrices, and sector rotation analysis.

---

## 🏗️ System Architecture

STK-ENGINE follows a strict orchestrated pipeline for every prediction:

1.  **Query Parsing**: Normalizes user input and target dates.
2.  **Ticker Resolution**: Deterministic mapping of aliases (e.g., "RELIANCE" -> "RELIANCE.NS").
3.  **Data Fetching**: Multi-tier failover retrieval of OHLCV and volume.
4.  **Indicator Computation**: Feature engineering of 20+ technical and macro indicators (VIX, 10Y Yield).
5.  **Ensemble Prediction**: Parallel execution of ML models with uncertainty estimation.
6.  **Explanation Synthesis**: Clean-language generation of the "Why" behind the numbers.

---

## 📂 Project Structure

- `api.py`: FastAPI entry point and WebSocket manager.
- `pipelines/`: Orchestrated, Real-time, and Backtest logic.
- `stk_models/`: Ensembles, XGBoost, and Random Forest implementations.
- `tools/`: Core utility modules (Predictor, Researcher, Fetcher, Indicators).
- `frontend/`: Vanilla JS + CSS dashboard integrated with the backend API.
- `stk_cache/`: Validation and storage logic for multi-tier caching.

---

## 📜 Documentation

For a detailed deep-dive into the codebase, data strategies, and deployment, see [DOCUMENTATION.md](./DOCUMENTATION.md).

## ⚖️ Disclaimer
*Educational and research use only. Not financial advice. Always verify trends with a certified financial advisor.*

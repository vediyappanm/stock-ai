# STK-ENGINE v2.0: Official User Manual & Technical Documentation

## 🚩 Introduction
Welcome to the official documentation for the **STK-ENGINE v2.0**. This platform is a consolidated algorithmic trading research workstation designed to provide retail traders with institutional-grade analytical depth.

---

## 🛠️ System Overview

### 1. Neural Prediction Pipeline
The engine uses a "Multimodal Prediction" approach. It doesn't just look at price; it analyzes:
- **Technical Regimes**: 40+ indicators across momentum, trend, and volatility.
- **Sentiment State**: Real-time parsing of market news and headlines.
- **Time-Series Memory**: LSTM networks that remember seasonal patterns.

### 2. The Integrated Dashboard
The dashboard is split into several "Intelligence Modules":
- **PREDICT**: The core interface for running neural ensemble forecasts.
- **SCANNER**: A parallel processing engine that finds opportunities across entire indices (NIFTY50, NASDAQ).
- **ANALYSIS**: Deep technical dive into specific tickers.
- **PORTFOLIO**: Real-time P&L tracking with live WebSocket telemetry.
- **QUANT_ANALYTICS**: The quantitative hub for sector rotation and correlation matrix analysis.

---

## 🧭 Using the Platform

### Natural Language Control (Neural Chat)
Located in the bottom-right of the dashboard, the **Neural Chat** is your primary way to control the system without clicking buttons.
- **Command**: `Analyze RELIANCE`
- **Result**: System resolves the ticker and populates the analysis tab instantly.

### Portfolio Hygiene
Before placing a trade, use the **Correlation Matrix** in the Quant tab. 
- *Why?* If you own 10 stocks in the IT sector, your portfolio is 90% correlated. One sector dip will wipe out your gains. The Correlation Matrix helps you diversify mathematically.

### Risk Simulation
The **Risk Impact Simulator** allows you to test:
- "What if I just held the stock?" (Buy and Hold)
- vs.
- "What if I used the STK-ENGINE's ATR trailing stop rules?" (Dynamic Risk Managed)

---

## 📡 Live Telemetry (WebSockets)
Once the server is running, you will see a **SYSTEM_LIVE** pill in the navbar. This means the engine is connected to a live simulated data feed.
- **Scanner results** will pulse and update prices automatically.
- **Portfolio P&L** will fluctuate in real-time.
- **Volatility Alerts** will slide in from the top right if a stock moves >0.15% in a single second.

---

## 👨‍💻 Administrator Setup
1.  **Dependencies**: Ensure `FastAPI`, `uvicorn`, `pandas`, `xgboost`, and `tensorflow` are installed via `requirements.txt`.
2.  **API Key**: Add your OpenAI API Key to the `.env` file to enable advanced natural language parsing.
3.  **Startup**: Run `python api.py` and wait for the "Application startup complete" message.

---
**Version**: 2.0.0-PROD  
**Environment**: Windows / Python 3.10+  
**Documentation Generated**: 2026-02-18

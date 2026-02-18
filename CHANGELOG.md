# Changelog

## 2.1.0 - 2026-02-18
- **Adaptive Ticker Resolution**: Implemented multi-exchange fallback strategy (NSE/NYSE/NASDAQ) to handle delisted or regional symbols (e.g., ABB).
- **Neural Memory**: Added short-term conversational context to `ChatEngine` for smarter multi-turn interactions.
- **WebSocket Stability**: Implemented 20s bi-directional "Pulse" heartbeat to prevent keepalive timeouts.
- **Analytics Hardening**: Fixed `ValueError` in portfolio correlation by enforcing unified index and series coercion.
- **UX Upgrades**: Added "Neural Send" button to chat, auto-scrolling message area, and input locking during processing.
- **Resilience**: Improved error reporting for delisted symbols and insufficient historical data.

## 2.0.0 - 2026-02-17
- Added strict 6-step workflow orchestration.
- Added standardized error handling and workflow tracking.
- Added compatibility entrypoints: `api.py`, `app.py`.
- Added class API: `OrchestratedPredictionPipeline`.
- Added quick prediction endpoint and expanded tests.

extract the details of ABB over the last 5 years and predict the estimated share price on 22nd feb 2026
# AI Stock Analysis and Prediction System

Python-based AI stock analysis and prediction system using LangChain and yfinance with natural-language query support and ML-based predictions.

## Educational Use Only
This tool is for educational and research purposes only. Stock market predictions are uncertain and not financial advice.

## Version 2.0.0
- Workflow orchestration with strict 6-step execution
- Standardized error responses with disclaimer
- Workflow progress/status tracking
- Skill packaging structure (`ai-stock-analyst/`)

See `CHANGELOG.md` for details.

## Features
- Natural language query parsing
- Technical indicators (SMA, RSI, MACD, etc.)
- Random Forest + LSTM prediction models
- Ensemble prediction intervals
- Natural-language explanations
- 6-step workflow enforcement

## Strict Workflow
1. `PARSE_QUERY`
2. `RESOLVE_TICKER`
3. `FETCH_DATA`
4. `COMPUTE_INDICATORS`
5. `PREDICT_PRICE`
6. `EXPLAIN_RESULT`

## Tech Stack
- Python 3.10+
- FastAPI
- LangChain + OpenAI
- yfinance
- pandas / numpy
- ta
- scikit-learn
- PyTorch

## Installation
```bash
pip install -r requirements.txt
```

Set environment:
```bash
export OPENAI_API_KEY="your-openai-api-key"
```

## Usage

### API server (v2 compatibility)
```bash
python api.py
```

Frontend:
- `http://localhost:8000/`

Endpoints:
- `POST /api/predict`
- `POST /api/predict/quick`
- `POST /api/backtest`
- `POST /api/analyze`
- `GET /api/workflow/{workflow_id}`
- `GET /api/health`

### API server (typed responses)
```bash
python -m uvicorn api_server:app --host 0.0.0.0 --port 8000
```

### Interactive mode
```bash
python app.py
```

## Programmatic usage
```python
from pipelines.orchestrated_pipeline import OrchestratedPredictionPipeline

pipeline = OrchestratedPredictionPipeline()
result = pipeline.run_complete_prediction_orchestrated(
    stock_name="ABB",
    target_date="2026-02-22"
)
print(result["prediction"]["predicted_price"])
```

## Project structure
```text
.
├── api.py
├── api_server.py
├── app.py
├── cli_agent.py
├── CHANGELOG.md
├── tools/
├── models/
├── pipelines/
├── config/
├── schemas/
├── ai-stock-analyst/
└── skill-creator/
```

## Testing
```bash
python -m pytest -q
```

## License
MIT

# AI Stock Analysis and Prediction System

A Python-based AI stock analysis and prediction system using LangChain and yfinance that accepts natural language queries and provides ML-based stock price predictions with technical analysis.

## ⚠️ Educational Use Only

**This tool is for educational and research purposes only. Stock market predictions are inherently uncertain and should not be used for making investment decisions. Not financial advice.**

## ✨ Version 2.0.0 - What's New

- **🔄 Workflow Orchestration**: Enforced strict 6-step prediction workflow for data integrity
- **🛡️ Standardized Error Handling**: Consistent error formats with educational disclaimers
- **📊 Progress Tracking**: Real-time workflow status and debugging capabilities
- **📚 Skill System**: Self-contained `ai-stock-analyst` skill package

See [CHANGELOG.md](CHANGELOG.md) for detailed changes.

## Features

- 🤖 **Natural Language Processing**: Parse queries like "Predict ABB stock price on 22 Feb 2026"
- 📊 **Technical Analysis**: Calculate SMA, RSI, MACD, and other indicators
- 🧠 **ML Models**: Random Forest and LSTM models for price prediction
- 🔄 **Ensemble Predictions**: Combine multiple models for better accuracy
- 📝 **Explanations**: Natural language explanations of predictions
- 🛡️ **Safe**: Educational use only with clear disclaimers
- **🔧 Workflow Orchestration**: Strict 6-step pipeline ensures data integrity

## Strict Workflow Pattern

All predictions follow a mandatory 6-step workflow:

```
1. Parse Query      → Extract stock name and target date
2. Resolve Ticker   → Map to NSE symbol (e.g., ABB → ABB.NS)
3. Fetch Data       → Get historical OHLCV from yfinance
4. Compute Indicators → Calculate SMA, RSI, MACD
5. Predict Price    → Run ensemble ML model
6. Explain Result   → Generate natural language explanation
```

This ensures:
- ✅ No predictions without data
- ✅ No computations on missing indicators
- ✅ Proper error handling at each step
- ✅ Full workflow traceability

## Tech Stack

- **Python 3.10+**
- **LangChain**: Agent framework and tools
- **OpenAI**: LLM for natural language processing
- **yfinance**: Stock data fetching
- **pandas/numpy**: Data manipulation
- **ta**: Technical indicators
- **scikit-learn**: Random Forest model
- **PyTorch**: LSTM model
- **FastAPI**: API layer with OpenAPI docs

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd stock-ai
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables:
```bash
export OPENAI_API_KEY="your-openai-api-key"
```

## Usage

### API Server (Recommended)

Run the FastAPI server with orchestrated workflows:

```bash
python api.py
```

Then access:
- API Docs: http://localhost:8000/docs
- Predictions: POST to http://localhost:8000/api/predict

**Example API Request:**
```json
{
  "stock": "ABB",
  "target_date": "2026-02-22",
  "model_type": "ensemble",
  "use_orchestration": true
}
```

**Example API Response:**
```json
{
  "success": true,
  "stock": "ABB",
  "ticker": "ABB.NS",
  "prediction": {
    "predicted_price": 6420.50,
    "trend": "Bullish",
    "confidence": "Medium"
  },
  "workflow": {
    "id": "prediction_a3f2b1c8_20260124_191830",
    "progress": {
      "progress_percentage": 100,
      "completed_steps": ["PARSE_QUERY", "RESOLVE_TICKER", "FETCH_DATA", "COMPUTE_INDICATORS", "PREDICT_PRICE", "EXPLAIN_PREDICTION"]
    },
    "duration_seconds": 2.3
  },
  "disclaimer": "⚠️ Educational and research use only. Not financial advice."
}
```

### Interactive Mode

Run the main application:
```bash
python app.py
```

Example queries:
- "Predict ABB stock price on 22 Feb 2026"
- "What will be the price of RELIANCE next month?"
- "Analyze TCS stock technical indicators"

### Programmatic Usage

```python
from pipelines.orchestrated_pipeline import OrchestratedPredictionPipeline

# Create pipeline
pipeline = OrchestratedPredictionPipeline()

# Run orchestrated prediction
result = pipeline.run_complete_prediction_orchestrated(
    stock_name="ABB",
    target_date="2026-02-22"
)

print(f"Predicted Price: {result['prediction']['predicted_price']}")
print(f"Workflow ID: {result['workflow']['id']}")
print(f"Progress: {result['workflow']['progress']['progress_percentage']}%")
```

### Check Workflow Status

```python
# Get workflow status
status = pipeline.get_workflow_status(workflow_id)
print(status["workflow"]["progress"])
```

## Project Structure

```
stock-ai/
├── api.py                      # FastAPI server (v2.0 with orchestration)
├── app.py                      # Main LangChain entry point
├── CHANGELOG.md                # Version history
├── requirements.txt            # Dependencies
├── README.md                   # This file
│
├── tools/
│   ├── fetch_data.py           # yfinance data fetching
│   ├── indicators.py           # Technical indicators
│   ├── predictor.py            # ML prediction logic
│   ├── explainer.py            # Natural language explanations
│   ├── workflow_orchestrator.py    # NEW: Workflow enforcement
│   └── error_handler.py        # NEW: Standardized errors
│
├── models/
│   ├── random_forest.py        # Random Forest model
│   └── lstm.py                 # LSTM model
│
├── pipelines/
│   ├── data_pipeline.py        # Data processing pipeline
│   ├── prediction_pipeline.py  # Complete prediction pipeline
│   └── orchestrated_pipeline.py # NEW: Orchestrated workflow
│
├── config/
│   └── settings.py             # Configuration settings
│
├── ai-stock-analyst/           # NEW: Skill package
│   ├── SKILL.md                # Skill documentation
│   ├── scripts/                # Bundled prediction scripts
│   └── references/             # Configuration references
│
└── skill-creator/              # Skill creation tools
    ├── SKILL.md                # Skill creator guide
    ├── scripts/                # init_skill.py, package_skill.py
    └── references/             # Workflow patterns
```

## Output Format

The system returns predictions in this structured format:

```json
{
  "success": true,
  "stock": "ABB",
  "ticker": "ABB.NS",
  "prediction_date": "2026-02-22",
  "predicted_price": 6420.50,
  "trend": "Bullish",
  "confidence": "Medium",
  "explanation": "Price trend is bullish due to strong moving averages and RSI momentum.",
  "workflow": {
    "id": "prediction_abc123...",
    "progress": {"progress_percentage": 100},
    "duration_seconds": 2.3
  },
  "disclaimer": "Educational and research use only. Not financial advice."
}
```

## API Reference

### Endpoints

1. **POST /api/predict**: Complete prediction with orchestrated workflow
2. **POST /api/predict/quick**: Fast prediction with minimal processing
3. **POST /api/analyze**: Technical analysis without prediction
4. **GET /api/workflow/{workflow_id}**: Check workflow status
5. **GET /api/health**: Health check

### Tools

1. **parse_stock_query**: Extract stock name and date from natural language
2. **predict_stock_price**: Complete prediction with explanation
3. **quick_stock_prediction**: Fast prediction with minimal processing
4. **analyze_stock_indicators**: Technical analysis without prediction

### Models

1. **RandomForestPredictor**: Tree-based ensemble model
2. **LSTMPredictor**: Deep learning model for time series
3. **Ensemble**: Weighted combination of both models

## Configuration

Edit `config/settings.py` to customize:

- Model parameters (n_estimators, random_state)
- Technical indicator periods
- Confidence thresholds
- Default data periods

## Examples

### Basic Prediction
```python
from pipelines.orchestrated_pipeline import OrchestratedPredictionPipeline

pipeline = OrchestratedPredictionPipeline()
result = pipeline.run_complete_prediction_orchestrated("ABB", "2026-02-22")
print(f"Predicted price: {result['prediction']['predicted_price']}")
print(f"Trend: {result['prediction']['trend']}")
print(f"Confidence: {result['prediction']['confidence']}")
```

### Error Handling
```python
result = pipeline.run_complete_prediction_orchestrated("", "invalid-date")

if not result["success"]:
    print(f"Error: {result['error']}")
    print(f"Failed at step: {result['failed_step']}")
    print(f"Completed steps: {result['workflow']['progress']['completed_steps']}")
```

### Workflow Tracking
```python
result = pipeline.run_complete_prediction_orchestrated("ABB", "2026-02-22")
workflow_id = result["workflow"]["id"]

# Check status later
status = pipeline.get_workflow_status(workflow_id)
print(f"Progress: {status['workflow']['progress']['progress_percentage']}%")
```

## Disclaimer

⚠️ **Educational and research use only. Not financial advice.**

This system is for educational purposes only. Stock market predictions are inherently uncertain and should not be used for making investment decisions. Always consult with qualified financial advisors before making investment choices.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## Testing

Test the orchestrated workflow:

```python
from pipelines.orchestrated_pipeline import OrchestratedPredictionPipeline

pipeline = OrchestratedPredictionPipeline()

# Test valid prediction
result = pipeline.run_complete_prediction_orchestrated("ABB", "2026-02-22")
assert result["success"] == True
assert result["workflow"]["progress"]["progress_percentage"] == 100

# Test validation errors
result = pipeline.run_complete_prediction_orchestrated("", "")
assert result["success"] == False
assert result["error_category"] == "validation_error"
```

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For issues and questions:
1. Check the documentation
2. Review existing issues
3. Create a new issue with details

## Future Enhancements

- [ ] Real-time data integration
- [ ] More sophisticated models (Transformer, GNN)
- [ ] Sentiment analysis integration
- [ ] Portfolio optimization
- [ ] Risk assessment metrics
- [ ] Web interface enhancements
- [ ] Mobile app
- [ ] Workflow visualization dashboard
- [ ] Async workflow execution
- [ ] Workflow replay for debugging
#   s t o c k - a i  
 
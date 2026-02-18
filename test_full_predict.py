from pipelines.orchestrated_pipeline import OrchestratedPredictionPipeline
from datetime import date, timedelta
import json

pipeline = OrchestratedPredictionPipeline()
target_date = (date.today() + timedelta(days=2)).isoformat()
print(f"Running full orchestrated prediction for RELIANCE NSE target {target_date}...")

result = pipeline.run_complete_prediction_orchestrated(
    stock_name="RELIANCE",
    exchange="NSE",
    target_date=target_date,
    model_type="ensemble",
    include_backtest=True,
    include_sentiment=True
)

print(json.dumps(result, indent=2))

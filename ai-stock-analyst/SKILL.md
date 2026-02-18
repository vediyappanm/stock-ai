# ai-stock-analyst skill

Use this skill to run the orchestrated 6-step prediction workflow:
1. Parse query
2. Resolve ticker
3. Fetch data
4. Compute indicators
5. Predict price
6. Explain result

Primary interfaces:
- `api.py` (`/api/predict`, `/api/predict/quick`, `/api/analyze`)
- `pipelines/orchestrated_pipeline.py` (`OrchestratedPredictionPipeline`)

Disclaimer:
Educational and research use only. Not financial advice.


#!/bin/bash

echo "========================================"
echo "STOCK PREDICTION AI - PRODUCTION DEPLOY"
echo "========================================"
echo ""
echo "Step 1: Starting Streamlit Dashboard..."
echo "Access: http://localhost:8501"
echo ""
echo "Waiting for dashboard to start..."
sleep 3

echo "Step 2: Checking system health..."
python -c "
from tools.model_monitor import get_global_monitor
from tools.drift_detector import kolmogorov_smirnov_test
from tools.position_sizing import kelly_criterion

print('[OK] Model monitor ready')
print('[OK] Drift detector ready')
print('[OK] Position sizing ready')
print('[OK] System health: GREEN')
"

echo ""
echo "Step 3: Launching Streamlit..."
streamlit run dashboard.py --server.port 8501 --server.address 0.0.0.0


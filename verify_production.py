import requests
import json
import time

def test_production_pipeline():
    print("--- STK-ENGINE Production Integration Test ---")
    url = "http://localhost:8000/api/predict"
    payload = {
        "ticker": "RELIANCE",
        "exchange": "NSE",
        "model_type": "random_forest"
    }
    
    print(f"1. Testing Prediction API (this may take ~20s)...")
    try:
        start = time.time()
        response = requests.post(url, json=payload, timeout=60)
        duration = time.time() - start
        
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                pred = data['prediction']['predicted_price']
                print(f"   [SUCCESS] Predicted Price: ₹{pred:.2f} (Duration: {duration:.1f}s)")
                
                # Check research
                res = data.get("research", {})
                print(f"   [SUCCESS] Research synthesis: {res.get('synthesis')[:80]}...")
                print(f"   [SUCCESS] Catalysts found: {len(res.get('catalysts', []))}")
                
                # Check telemetry
                tel = data.get("model_telemetry", {})
                print(f"   [SUCCESS] Telemetry: RF={tel.get('random_forest')} XGB={tel.get('xgboost')} LSTM={tel.get('lstm')}")
                
                if pred == 0:
                    print("   [FAILURE] Prediction is ₹0.00!")
                else:
                    print("   [STATUS] Prediction values look valid.")
            else:
                print(f"   [FAILURE] API returned success=False: {data.get('error')}")
        else:
            print(f"   [FAILURE] HTTP {response.status_code}: {response.text}")
    except Exception as e:
        print(f"   [ERROR] Connection failed: {e}")

    print("\n2. Testing Chart Data API...")
    try:
        chart_url = "http://localhost:8000/api/chart-data/RELIANCE?exchange=NSE&period=1mo"
        response = requests.get(chart_url)
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                ohlcv = data.get("ohlcv", [])
                print(f"   [SUCCESS] Received {len(ohlcv)} data points for 1M period.")
            else:
                print(f"   [FAILURE] Chart API error.")
        else:
            print(f"   [FAILURE] HTTP {response.status_code}")
    except Exception as e:
        print(f"   [ERROR] {e}")

if __name__ == "__main__":
    test_production_pipeline()

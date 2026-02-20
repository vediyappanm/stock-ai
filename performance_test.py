#!/usr/bin/env python3
"""Performance diagnostic tool for API response times."""

import time
import asyncio
import httpx
import json
from datetime import datetime

async def test_api_performance():
    """Test API endpoint performance."""
    
    base_url = "http://localhost:8000"
    endpoints = [
        "/api/health",
        "/api/portfolio", 
        "/api/watchlist",
        "/api/chart-data/NVDA?exchange=NASDAQ&period=1d"
    ]
    
    print("🔍 Testing API Performance...")
    print("=" * 60)
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        for endpoint in endpoints:
            try:
                start_time = time.time()
                response = await client.get(f"{base_url}{endpoint}")
                end_time = time.time()
                
                duration = (end_time - start_time) * 1000  # Convert to ms
                
                status = "✅" if response.status_code == 200 else "❌"
                print(f"{status} {endpoint:<40} {duration:>8.0f}ms  ({response.status_code})")
                
                if response.status_code != 200:
                    print(f"   Error: {response.text[:100]}...")
                    
            except Exception as e:
                print(f"❌ {endpoint:<40} TIMEOUT   ({str(e)[:50]}...)")
        
        print("\n🧪 Testing prediction endpoint (this might be slow)...")
        try:
            prediction_payload = {
                "ticker": "NVDA",
                "exchange": "NASDAQ",
                "target_date": "2026-02-22",
                "model_type": "ensemble"
            }
            
            start_time = time.time()
            response = await client.post(f"{base_url}/api/predict", json=prediction_payload)
            end_time = time.time()
            
            duration = (end_time - start_time) * 1000
            status = "✅" if response.status_code == 200 else "❌"
            
            print(f"{status} /api/predict (NVDA)                    {duration:>8.0f}ms  ({response.status_code})")
            
            if response.status_code == 200:
                data = response.json()
                print(f"   📊 Prediction: ${data.get('prediction', {}).get('predicted_price', 'N/A')}")
            
        except Exception as e:
            print(f"❌ /api/predict (NVDA)                    TIMEOUT   ({str(e)[:50]}...)")

if __name__ == "__main__":
    asyncio.run(test_api_performance())

import requests
import json

url = "http://localhost:8000/api/analyze"
payload = {"ticker": "INVALID_TICKER", "exchange": "NSE"}
response = requests.post(url, json=payload)
print(f"Status Code: {response.status_code}")
print(json.dumps(response.json(), indent=2))

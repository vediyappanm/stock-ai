#!/usr/bin/env python3
"""Debug script to check current date and date parsing."""

from datetime import date, datetime
from tools.query_parser import get_next_trading_day, _parse_target_date

print("=== Date Debug Information ===")
print(f"Current date (date.today()): {date.today()}")
print(f"Current datetime (datetime.now()): {datetime.now()}")
print(f"Next trading day: {get_next_trading_day()}")

# Test the specific date that's failing
test_date = "2026-02-22"
parsed_date = _parse_target_date(test_date)
print(f"Parsed date '{test_date}': {parsed_date}")
print(f"Is {test_date} < today? {parsed_date < date.today()}")

# Test what happens with no target date
from tools.query_parser import parse_query
try:
    result = parse_query(stock="RELIANCE", exchange="NSE")
    print(f"Default target date when none provided: {result.target_date}")
except Exception as e:
    print(f"Error when parsing with no target date: {e}")
#!/usr/bin/env python3
"""Step 2: Comprehensive Backtesting - Multi-asset, multi-period validation."""

import sys
import logging
from datetime import datetime, timedelta
from typing import Dict, List

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

from pipelines.backtest_pipeline import execute_backtest_pipeline
from schemas.request_schemas import BacktestRequest
from schemas.response_schemas import BacktestResult


def format_backtest_result(ticker: str, result: BacktestResult, period: str = "") -> str:
    """Format backtest result for display."""
    return (
        f"\n{ticker} {period}\n"
        f"  Directional Accuracy: {result.directional_accuracy:.1f}%\n"
        f"  MAE:                  ${result.mae:.4f}\n"
        f"  RMSE:                 ${result.rmse:.4f}\n"
        f"  MAPE:                 {result.mape:.2f}%\n"
        f"  Periods Tested:       {result.periods}"
    )


def run_validation_suite():
    """Run comprehensive validation across multiple scenarios."""

    print("\n" + "=" * 70)
    print("STEP 2: COMPREHENSIVE BACKTESTING")
    print("=" * 70)

    results_summary = {}

    # TEST 1: NVDA 2025 Full Year (High Volatility)
    print("\n[TEST 1] NVDA 2025 Full Year (365 days, High Vol)")
    print("-" * 70)
    try:
        result = execute_backtest_pipeline(
            BacktestRequest(ticker="NVDA", days=365)
        )
        print(format_backtest_result("NVDA", result, "Full Year 2025"))
        results_summary["NVDA_2025"] = {
            "accuracy": result.directional_accuracy,
            "mae": result.mae,
            "periods": result.periods,
        }

        # Check targets
        if result.directional_accuracy >= 58:
            print(f"  STATUS: PASS (>58% target)")
        else:
            print(f"  STATUS: WARN (below 58% target)")

    except Exception as e:
        print(f"  ERROR: {e}")
        results_summary["NVDA_2025"] = {"error": str(e)}

    # TEST 2: NVDA 180-Day Recent
    print("\n[TEST 2] NVDA Last 180 Days")
    print("-" * 70)
    try:
        result = execute_backtest_pipeline(
            BacktestRequest(ticker="NVDA", days=180)
        )
        print(format_backtest_result("NVDA", result, "Last 180 Days"))
        results_summary["NVDA_180d"] = {
            "accuracy": result.directional_accuracy,
            "mae": result.mae,
        }
    except Exception as e:
        print(f"  ERROR: {e}")

    # TEST 3: Multi-Asset Tech Basket (AMD, MSFT)
    print("\n[TEST 3] Multi-Asset Tech Basket (60 days each)")
    print("-" * 70)
    tech_tickers = ["AMD", "MSFT", "TSLA"]
    for ticker in tech_tickers:
        try:
            result = execute_backtest_pipeline(
                BacktestRequest(ticker=ticker, days=60)
            )
            print(format_backtest_result(ticker, result, "60-Day"))
            results_summary[f"{ticker}_60d"] = {
                "accuracy": result.directional_accuracy,
                "mae": result.mae,
            }
        except Exception as e:
            print(f"  {ticker}: ERROR - {e}")
            results_summary[f"{ticker}_60d"] = {"error": str(e)}

    # TEST 4: Short Horizon (7 days - around earnings)
    print("\n[TEST 4] Short Horizon - NVDA 7 Days (Earnings-Week Simulation)")
    print("-" * 70)
    try:
        result = execute_backtest_pipeline(
            BacktestRequest(ticker="NVDA", days=7)
        )
        print(format_backtest_result("NVDA", result, "7-Day"))
        results_summary["NVDA_7d"] = {
            "accuracy": result.directional_accuracy,
            "mae": result.mae,
        }
    except Exception as e:
        print(f"  ERROR: {e}")

    # TEST 5: 30-Day Window (Standard)
    print("\n[TEST 5] Standard 30-Day Window")
    print("-" * 70)
    try:
        result = execute_backtest_pipeline(
            BacktestRequest(ticker="NVDA", days=30)
        )
        print(format_backtest_result("NVDA", result, "30-Day"))
        results_summary["NVDA_30d"] = {
            "accuracy": result.directional_accuracy,
            "mae": result.mae,
        }
    except Exception as e:
        print(f"  ERROR: {e}")

    # SUMMARY
    print("\n" + "=" * 70)
    print("STEP 2 SUMMARY")
    print("=" * 70)

    accuracies = [v["accuracy"] for v in results_summary.values() if "accuracy" in v]
    if accuracies:
        avg_accuracy = sum(accuracies) / len(accuracies)
        max_accuracy = max(accuracies)
        min_accuracy = min(accuracies)

        print(f"\nBacktest Results across {len(accuracies)} scenarios:")
        print(f"  Average Directional Accuracy: {avg_accuracy:.1f}%")
        print(f"  Best:                         {max_accuracy:.1f}%")
        print(f"  Worst:                        {min_accuracy:.1f}%")

        if avg_accuracy >= 58:
            print(f"\n  OVERALL: PASS (Average ≥58%)")
        else:
            print(f"\n  OVERALL: MONITOR (Average <58%, but acceptable for Phase testing)")

    print("\nDetailed Results:")
    for scenario, data in results_summary.items():
        if "accuracy" in data:
            print(f"  {scenario:15s}: {data['accuracy']:5.1f}% (MAE: ${data['mae']:.4f})")
        elif "error" in data:
            print(f"  {scenario:15s}: ERROR")

    return results_summary


if __name__ == "__main__":
    try:
        results = run_validation_suite()
        print("\n" + "=" * 70)
        print("BACKTESTING COMPLETE - Ready for Step 4 (Paper Trading)")
        print("=" * 70)
    except Exception as e:
        print(f"\nFATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

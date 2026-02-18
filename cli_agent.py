"""Interactive CLI agent for stock analysis."""

from __future__ import annotations

import json
from typing import Optional

from config.settings import settings
from pipelines.backtest_pipeline import execute_backtest_pipeline
from pipelines.orchestrated_pipeline import execute_prediction_pipeline
from schemas.request_schemas import BacktestRequest, PredictRequest
from tools.fetch_data import fetch_ohlcv_data
from tools.indicators import compute_indicators
from tools.ticker_resolver import resolve_ticker

try:
    from langchain.agents import AgentType, initialize_agent
    from langchain.tools import Tool
    from langchain_openai import ChatOpenAI
except Exception:  # pragma: no cover - optional dependency fallback
    AgentType = None
    initialize_agent = None
    Tool = None
    ChatOpenAI = None


def predict_stock_price(query: str) -> str:
    response = execute_prediction_pipeline(PredictRequest(query=query))
    return json.dumps(response.model_dump(mode="json"), indent=2)


def analyze_stock_indicators(ticker: str, exchange: str | None = None) -> str:
    resolved = resolve_ticker(stock=ticker, exchange=exchange)
    data = fetch_ohlcv_data(ticker_symbol=resolved.full_symbol, exchange=resolved.exchange)
    indicators = compute_indicators(data)
    payload = {
        "ticker": resolved.full_symbol,
        "exchange": resolved.exchange,
        "latest": indicators.iloc[-1].to_dict(),
        "disclaimer": settings.disclaimer,
    }
    payload["latest"]["Date"] = str(payload["latest"]["Date"])
    return json.dumps(payload, indent=2)


def run_stock_backtest(ticker: str, exchange: str | None = None, days: int | None = None) -> str:
    req = BacktestRequest(ticker=ticker, exchange=exchange, days=days or settings.default_backtest_days)
    result = execute_backtest_pipeline(req)
    return json.dumps(result.model_dump(), indent=2)


def _build_langchain_agent() -> Optional[object]:
    if not settings.openai_api_key or ChatOpenAI is None or initialize_agent is None or Tool is None:
        return None

    llm = ChatOpenAI(
        model=settings.openai_model,
        openai_api_key=settings.openai_api_key,
        temperature=0.0,
    )
    tools = [
        Tool(
            name="predict_stock_price",
            func=predict_stock_price,
            description="Predict stock price from natural language query.",
        ),
        Tool(
            name="analyze_stock_indicators",
            func=lambda text: analyze_stock_indicators(*text.split()[:2]),
            description="Analyze indicators with input format: '<ticker> [exchange]'.",
        ),
        Tool(
            name="run_stock_backtest",
            func=lambda text: run_stock_backtest(*text.split()[:3]),
            description="Run backtest with input format: '<ticker> [exchange] [days]'.",
        ),
    ]
    return initialize_agent(
        tools=tools,
        llm=llm,
        agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
        verbose=False,
        handle_parsing_errors=True,
    )


def _print_help() -> None:
    print("Commands:")
    print("  predict <natural language query>")
    print("  analyze <ticker> [exchange]")
    print("  backtest <ticker> [exchange] [days]")
    print("  ask <free-text prompt>  (LangChain ReAct mode, if configured)")
    print("  exit")
    print(f"Disclaimer: {settings.disclaimer}")


def run_cli() -> None:
    """
    Lightweight interactive CLI with three stock-analysis tools.
    """
    _print_help()
    agent = _build_langchain_agent()
    while True:
        try:
            raw = input("\nstock-agent> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nbye")
            break

        if not raw:
            continue
        if raw.lower() in {"exit", "quit"}:
            print("bye")
            break

        try:
            parts = raw.split()
            command = parts[0].lower()

            if command == "predict":
                query = raw[len("predict") :].strip()
                if not query:
                    print("Usage: predict <natural language query>")
                    continue
                print(predict_stock_price(query))
            elif command == "analyze":
                if len(parts) < 2:
                    print("Usage: analyze <ticker> [exchange]")
                    continue
                ticker = parts[1]
                exchange = parts[2] if len(parts) > 2 else None
                print(analyze_stock_indicators(ticker, exchange))
            elif command == "backtest":
                if len(parts) < 2:
                    print("Usage: backtest <ticker> [exchange] [days]")
                    continue
                ticker = parts[1]
                exchange = parts[2] if len(parts) > 2 else None
                days = int(parts[3]) if len(parts) > 3 else None
                print(run_stock_backtest(ticker, exchange, days))
            elif command == "ask":
                if agent is None:
                    print("LangChain mode unavailable (missing dependencies or OPENAI_API_KEY).")
                    continue
                prompt = raw[len("ask") :].strip()
                if not prompt:
                    print("Usage: ask <free-text prompt>")
                    continue
                result = agent.run(prompt)
                print(result)
            else:
                print("Unknown command.")
                _print_help()
        except Exception as exc:
            print(f"Error: {exc}")


if __name__ == "__main__":
    run_cli()

"""Centralized configuration for the AI Stock Analyst system."""

from typing import Dict, List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    # API Configuration
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # OpenAI Configuration
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    # Groq Configuration
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"

    # Model Hyperparameters - XGBoost
    xgb_n_estimators: int = 500
    xgb_max_depth: int = 6
    xgb_learning_rate: float = 0.05
    xgb_random_state: int = 42

    # Model Hyperparameters - Random Forest
    rf_n_estimators: int = 200
    rf_max_depth: int = 15
    rf_random_state: int = 42

    # Model Hyperparameters - LSTM
    lstm_hidden_size_1: int = 64
    lstm_hidden_size_2: int = 32
    lstm_dropout: float = 0.2
    lstm_sequence_length: int = 60
    lstm_epochs_prod: int = 30
    lstm_epochs_dev: int = 3
    lstm_batch_size: int = 32
    lstm_learning_rate: float = 0.001
    lstm_random_state: int = 42

    # Ensemble Configuration
    xgb_weight: float = 0.4
    rf_weight: float = 0.3
    lstm_weight: float = 0.3
    confidence_level: float = 0.80
    z_score_80: float = 1.28
    is_dev_mode: bool = False

    # Technical Indicators Configuration
    sma_periods: List[int] = [20, 50, 200]
    rsi_period: int = 14
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    bb_period: int = 20
    bb_std: int = 2
    atr_period: int = 14
    stochastic_k_period: int = 14
    stochastic_d_period: int = 3

    # Data Validation Configuration
    min_rows_indicators: int = 200
    min_rows_rf: int = 60
    min_rows_lstm: int = 120
    indicator_validation_rows: int = 60

    # Cache Configuration
    cache_dir: str = ".cache"
    models_dir: str = ".cache/models"
    cache_ttl_market_hours: int = 15
    cache_ttl_after_hours: int = 1440

    # Market Hours Configuration (NSE/BSE - India)
    nse_bse_open: str = "09:15"
    nse_bse_close: str = "15:30"
    nse_bse_timezone: str = "Asia/Kolkata"

    # Market Hours Configuration (NYSE/NASDAQ - US)
    nyse_nasdaq_open: str = "09:30"
    nyse_nasdaq_close: str = "16:00"
    nyse_nasdaq_timezone: str = "America/New_York"

    # Exchange Resolution Configuration
    default_exchange: str = "NSE"
    supported_exchanges: List[str] = ["NSE", "BSE", "NYSE", "NASDAQ"]
    exchange_suffixes: Dict[str, str] = {
        "NSE": ".NS",
        "BSE": ".BO",
        "NYSE": "",
        "NASDAQ": "",
    }

    # Sentiment Analysis Configuration
    sentiment_timeout: int = 5
    yahoo_rss_template: str = "https://finance.yahoo.com/rss/headline?s={ticker}"
    google_news_template: str = "https://news.google.com/rss/search?q={ticker}+stock"

    # Backtest Configuration
    default_backtest_days: int = 30
    max_backtest_days: int = 90
    min_backtest_days: int = 1

    # Compliance Configuration
    disclaimer: str = "Educational and research use only. Not financial advice."
    forbidden_words: List[str] = ["buy", "sell", "invest", "recommend"]

    # Workflow Configuration
    workflow_retention_hours: int = 1
    total_workflow_steps: int = 6
    workflow_steps: List[str] = [
        "PARSE_QUERY",
        "RESOLVE_TICKER",
        "FETCH_DATA",
        "COMPUTE_INDICATORS",
        "PREDICT_PRICE",
        "EXPLAIN_RESULT",
    ]

    # Logging Configuration
    log_level: str = "INFO"

    # Alert Configuration
    enable_alerts: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="allow",
    )


settings = Settings()

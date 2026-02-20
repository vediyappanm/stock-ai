"""
Unit tests and property-based tests for cache data store.
"""

import json
import uuid
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import pytest
from hypothesis import given, settings, strategies as st

from stk_cache.data_store import CacheManager, CachedData


def _workspace_tmp(name: str) -> str:
    base = Path(".tmp") / name
    base.mkdir(parents=True, exist_ok=True)
    path = base / uuid.uuid4().hex
    path.mkdir(parents=True, exist_ok=True)
    return str(path)


# ============================================================================
# Unit Tests
# ============================================================================

@pytest.fixture
def temp_cache_dir():
    """Create a temporary cache directory for testing."""
    base = Path(".cache_test")
    base.mkdir(parents=True, exist_ok=True)
    path = base / uuid.uuid4().hex
    path.mkdir(parents=True, exist_ok=False)
    return str(path)


@pytest.fixture
def cache_manager(temp_cache_dir):
    """Create a CacheManager instance with temporary directory."""
    return CacheManager(cache_dir=temp_cache_dir)


@pytest.fixture
def sample_dataframe():
    """Create a sample OHLCV DataFrame for testing."""
    return pd.DataFrame({
        'Date': pd.date_range(start='2024-01-01', periods=10, freq='D'),
        'Open': [100.0, 101.0, 102.0, 103.0, 104.0, 105.0, 106.0, 107.0, 108.0, 109.0],
        'High': [102.0, 103.0, 104.0, 105.0, 106.0, 107.0, 108.0, 109.0, 110.0, 111.0],
        'Low': [99.0, 100.0, 101.0, 102.0, 103.0, 104.0, 105.0, 106.0, 107.0, 108.0],
        'Close': [101.0, 102.0, 103.0, 104.0, 105.0, 106.0, 107.0, 108.0, 109.0, 110.0],
        'Volume': [1000000, 1100000, 1200000, 1300000, 1400000, 1500000, 1600000, 1700000, 1800000, 1900000]
    })


def test_cache_manager_init_creates_directories(temp_cache_dir):
    """Test that CacheManager creates all required directories on init."""
    cache_manager = CacheManager(cache_dir=temp_cache_dir)
    
    assert cache_manager.ohlcv_dir.exists()
    assert cache_manager.metadata_dir.exists()
    assert cache_manager.models_dir.exists()
    assert cache_manager.ohlcv_dir.is_dir()
    assert cache_manager.metadata_dir.is_dir()
    assert cache_manager.models_dir.is_dir()


def test_set_stores_data_and_metadata(cache_manager, sample_dataframe):
    """Test that set() stores both data and metadata correctly."""
    key = "AAPL_NYSE"
    ttl_minutes = 15
    
    cache_manager.set(key, sample_dataframe, ttl_minutes)
    
    # Check data file exists
    data_path = cache_manager.ohlcv_dir / f"{key}.parquet"
    assert data_path.exists()
    
    # Check metadata file exists
    meta_path = cache_manager.metadata_dir / f"{key}_meta.json"
    assert meta_path.exists()
    
    # Verify data can be read back
    loaded_data = pd.read_parquet(data_path, engine='pyarrow')
    pd.testing.assert_frame_equal(loaded_data, sample_dataframe)
    
    # Verify metadata content
    with open(meta_path, 'r') as f:
        metadata = json.load(f)
    
    assert 'timestamp' in metadata
    assert metadata['ttl_minutes'] == ttl_minutes
    # Verify timestamp is valid ISO format
    datetime.fromisoformat(metadata['timestamp'])


def test_get_returns_none_when_cache_missing(cache_manager):
    """Test that get() returns None when cache doesn't exist."""
    result = cache_manager.get("NONEXISTENT_NYSE")
    assert result is None


def test_get_returns_cached_data_when_valid(cache_manager, sample_dataframe):
    """Test that get() returns cached data when TTL is valid."""
    key = "AAPL_NYSE"
    ttl_minutes = 15
    
    # Store data
    cache_manager.set(key, sample_dataframe, ttl_minutes)
    
    # Retrieve data
    cached_data = cache_manager.get(key)
    
    assert cached_data is not None
    assert isinstance(cached_data, CachedData)
    pd.testing.assert_frame_equal(cached_data.data, sample_dataframe)
    assert cached_data.ttl_minutes == ttl_minutes
    assert isinstance(cached_data.timestamp, datetime)


def test_get_returns_none_when_cache_expired(cache_manager, sample_dataframe):
    """Test that get() returns None when cache has expired."""
    key = "AAPL_NYSE"
    ttl_minutes = 15
    
    # Store data
    cache_manager.set(key, sample_dataframe, ttl_minutes)
    
    # Manually modify metadata to make it expired
    meta_path = cache_manager.metadata_dir / f"{key}_meta.json"
    expired_timestamp = datetime.now() - timedelta(minutes=20)
    
    metadata = {
        'timestamp': expired_timestamp.isoformat(),
        'ttl_minutes': ttl_minutes
    }
    
    with open(meta_path, 'w') as f:
        json.dump(metadata, f)
    
    # Try to retrieve - should return None
    cached_data = cache_manager.get(key)
    assert cached_data is None


def test_is_valid_returns_true_for_valid_cache():
    """Test that is_valid() returns True when cache is still valid."""
    cache_manager = CacheManager(cache_dir=_workspace_tmp("cache_is_valid_true"))
    
    cached_data = CachedData(
        data=pd.DataFrame(),
        timestamp=datetime.now() - timedelta(minutes=5),
        ttl_minutes=15
    )
    
    assert cache_manager.is_valid(cached_data) is True


def test_is_valid_returns_false_for_expired_cache():
    """Test that is_valid() returns False when cache has expired."""
    cache_manager = CacheManager(cache_dir=_workspace_tmp("cache_is_valid_false"))
    
    cached_data = CachedData(
        data=pd.DataFrame(),
        timestamp=datetime.now() - timedelta(minutes=20),
        ttl_minutes=15
    )
    
    assert cache_manager.is_valid(cached_data) is False


def test_is_valid_boundary_condition():
    """Test is_valid() at exact expiry boundary."""
    cache_manager = CacheManager(cache_dir=_workspace_tmp("cache_is_valid_boundary"))
    
    # Cache that expires exactly now (should be invalid)
    cached_data = CachedData(
        data=pd.DataFrame(),
        timestamp=datetime.now() - timedelta(minutes=15),
        ttl_minutes=15
    )
    
    # Due to time passing during test execution, this should be False
    assert cache_manager.is_valid(cached_data) is False


def test_get_ttl_returns_15_during_market_hours():
    """Test that get_ttl() returns 15 minutes during market hours."""
    cache_manager = CacheManager(cache_dir=_workspace_tmp("cache_ttl_open"))
    
    ttl = cache_manager.get_ttl("NSE", is_market_hours=True)
    assert ttl == 15
    
    ttl = cache_manager.get_ttl("NYSE", is_market_hours=True)
    assert ttl == 15


def test_get_ttl_returns_1440_after_hours():
    """Test that get_ttl() returns 1440 minutes (24 hours) after hours."""
    cache_manager = CacheManager(cache_dir=_workspace_tmp("cache_ttl_closed"))
    
    ttl = cache_manager.get_ttl("NSE", is_market_hours=False)
    assert ttl == 1440
    
    ttl = cache_manager.get_ttl("NYSE", is_market_hours=False)
    assert ttl == 1440


def test_cache_key_format():
    """Test that cache keys follow the {ticker}_{exchange} format."""
    cache_manager = CacheManager(cache_dir=_workspace_tmp("cache_key_format"))
    sample_df = pd.DataFrame({'A': [1, 2, 3]})
    
    key = "RELIANCE_NSE"
    cache_manager.set(key, sample_df, 15)
    
    # Verify files are created with correct naming
    assert (cache_manager.ohlcv_dir / f"{key}.parquet").exists()
    assert (cache_manager.metadata_dir / f"{key}_meta.json").exists()


def test_get_handles_corrupted_metadata(cache_manager, sample_dataframe):
    """Test that get() returns None when metadata is corrupted."""
    key = "AAPL_NYSE"
    
    # Store valid data
    cache_manager.set(key, sample_dataframe, 15)
    
    # Corrupt metadata file
    meta_path = cache_manager.metadata_dir / f"{key}_meta.json"
    with open(meta_path, 'w') as f:
        f.write("invalid json {{{")
    
    # Should return None instead of raising exception
    result = cache_manager.get(key)
    assert result is None


def test_get_handles_missing_metadata_fields(cache_manager, sample_dataframe):
    """Test that get() returns None when metadata is missing required fields."""
    key = "AAPL_NYSE"
    
    # Store valid data
    cache_manager.set(key, sample_dataframe, 15)
    
    # Write incomplete metadata
    meta_path = cache_manager.metadata_dir / f"{key}_meta.json"
    with open(meta_path, 'w') as f:
        json.dump({'timestamp': datetime.now().isoformat()}, f)  # Missing ttl_minutes
    
    # Should return None
    result = cache_manager.get(key)
    assert result is None


def test_parquet_storage_format(cache_manager, sample_dataframe):
    """Test that data is stored in valid Parquet format."""
    key = "AAPL_NYSE"
    cache_manager.set(key, sample_dataframe, 15)
    
    data_path = cache_manager.ohlcv_dir / f"{key}.parquet"
    
    # Should be able to read back with pyarrow engine
    loaded_data = pd.read_parquet(data_path, engine='pyarrow')
    pd.testing.assert_frame_equal(loaded_data, sample_dataframe)


# ============================================================================
# Property-Based Tests
# ============================================================================

@settings(max_examples=100, deadline=None)
@given(
    ticker=st.text(min_size=1, max_size=10, alphabet=st.characters(whitelist_categories=('Lu', 'Nd'))),
    exchange=st.sampled_from(['NSE', 'BSE', 'NYSE', 'NASDAQ']),
    ttl_minutes=st.integers(min_value=1, max_value=10080)  # 1 minute to 1 week
)
def test_property_10_parquet_storage_format(ticker, exchange, ttl_minutes):
    """
    Feature: ai-stock-analyst, Property 10: Parquet Storage Format
    
    **Validates: Requirements 4.6, 15.4**
    
    For any fetched OHLCV data, the Data_Fetcher SHALL store it in valid
    Parquet format that can be read back without errors.
    """
    tmpdir = _workspace_tmp("property_10")
    cache_manager = CacheManager(cache_dir=tmpdir)
        
    # Create sample DataFrame
    sample_df = pd.DataFrame({
        'Date': pd.date_range(start='2024-01-01', periods=5, freq='D'),
        'Open': [100.0, 101.0, 102.0, 103.0, 104.0],
        'High': [102.0, 103.0, 104.0, 105.0, 106.0],
        'Low': [99.0, 100.0, 101.0, 102.0, 103.0],
        'Close': [101.0, 102.0, 103.0, 104.0, 105.0],
        'Volume': [1000000, 1100000, 1200000, 1300000, 1400000]
    })
    
    key = f"{ticker}_{exchange}"
    
    # Store data
    cache_manager.set(key, sample_df, ttl_minutes)
    
    # Verify Parquet file can be read back without errors
    data_path = cache_manager.ohlcv_dir / f"{key}.parquet"
    loaded_data = pd.read_parquet(data_path, engine='pyarrow')
    
    # Verify data integrity
    pd.testing.assert_frame_equal(loaded_data, sample_df)


@settings(max_examples=100, deadline=None)
@given(
    is_market_hours=st.booleans(),
    exchange=st.sampled_from(['NSE', 'BSE', 'NYSE', 'NASDAQ'])
)
def test_property_8_market_hours_aware_ttl(is_market_hours, exchange):
    """
    Feature: ai-stock-analyst, Property 8: Market-Hours-Aware TTL Selection
    
    **Validates: Requirements 4.3, 4.4, 15.2, 15.3**
    
    For any cache operation, the Cache_Manager SHALL use 15-minute TTL when
    current time is within market hours, and 24-hour TTL otherwise.
    """
    cache_manager = CacheManager(cache_dir=_workspace_tmp("cache_ttl_property"))
    
    ttl = cache_manager.get_ttl(exchange, is_market_hours)
    
    if is_market_hours:
        assert ttl == 15, f"Expected 15 minutes TTL during market hours, got {ttl}"
    else:
        assert ttl == 1440, f"Expected 1440 minutes TTL after hours, got {ttl}"


@settings(max_examples=100, deadline=None)
@given(
    minutes_ago=st.integers(min_value=0, max_value=100),
    ttl_minutes=st.integers(min_value=1, max_value=100)
)
def test_property_9_cache_ttl_validation_formula(minutes_ago, ttl_minutes):
    """
    Feature: ai-stock-analyst, Property 9: Cache TTL Validation Formula
    
    **Validates: Requirements 15.5**
    
    For any cached data, the cache SHALL be considered valid if and only if
    (current_time < timestamp + TTL).
    """
    cache_manager = CacheManager(cache_dir=_workspace_tmp("cache_ttl_formula"))
    
    timestamp = datetime.now() - timedelta(minutes=minutes_ago)
    
    cached_data = CachedData(
        data=pd.DataFrame(),
        timestamp=timestamp,
        ttl_minutes=ttl_minutes
    )
    
    is_valid = cache_manager.is_valid(cached_data)
    
    # Calculate expected validity
    current_time = datetime.now()
    expiry_time = timestamp + timedelta(minutes=ttl_minutes)
    expected_valid = current_time < expiry_time
    
    assert is_valid == expected_valid, (
        f"Cache validity mismatch: minutes_ago={minutes_ago}, "
        f"ttl_minutes={ttl_minutes}, is_valid={is_valid}, expected={expected_valid}"
    )


@settings(max_examples=100, deadline=None)
@given(
    ticker=st.text(min_size=1, max_size=10, alphabet=st.characters(whitelist_categories=('Lu', 'Nd'))),
    exchange=st.sampled_from(['NSE', 'BSE', 'NYSE', 'NASDAQ'])
)
def test_property_35_cache_metadata_persistence(ticker, exchange):
    """
    Feature: ai-stock-analyst, Property 35: Cache Metadata Persistence
    
    **Validates: Requirements 15.4**
    
    For any cached data, the Cache_Manager SHALL store metadata including
    timestamp and TTL alongside the data.
    """
    tmpdir = _workspace_tmp("property_35")
    cache_manager = CacheManager(cache_dir=tmpdir)
    
    sample_df = pd.DataFrame({
        'Date': pd.date_range(start='2024-01-01', periods=3, freq='D'),
        'Close': [100.0, 101.0, 102.0]
    })
    
    key = f"{ticker}_{exchange}"
    ttl_minutes = 15
    
    # Store data
    cache_manager.set(key, sample_df, ttl_minutes)
    
    # Verify metadata file exists
    meta_path = cache_manager.metadata_dir / f"{key}_meta.json"
    assert meta_path.exists(), "Metadata file should exist"
    
    # Verify metadata content
    with open(meta_path, 'r') as f:
        metadata = json.load(f)
    
    assert 'timestamp' in metadata, "Metadata should contain timestamp"
    assert 'ttl_minutes' in metadata, "Metadata should contain ttl_minutes"
    assert metadata['ttl_minutes'] == ttl_minutes, "TTL should match stored value"
    
    # Verify timestamp is valid ISO format
    timestamp = datetime.fromisoformat(metadata['timestamp'])
    assert isinstance(timestamp, datetime), "Timestamp should be valid datetime"

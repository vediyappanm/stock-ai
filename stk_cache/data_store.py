"""
Cache data store for OHLCV data with TTL validation.

This module implements the CacheManager class that handles caching of market data
with intelligent TTL based on market hours.
"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, NamedTuple

import pandas as pd


class CachedData(NamedTuple):
    """Container for cached data with metadata."""
    data: pd.DataFrame
    timestamp: datetime
    ttl_minutes: int


class CacheManager:
    """
    Manages cached OHLCV data with TTL validation.
    
    Storage format:
    - Parquet files in .cache/ohlcv/ directory using pyarrow engine
    - Metadata JSON: {ticker}_{exchange}_meta.json with timestamp and TTL
    - Cache key format: {ticker}_{exchange}
    """
    
    def __init__(self, cache_dir: str = ".cache"):
        """
        Initialize cache directories.
        
        Args:
            cache_dir: Base cache directory path
        """
        self.cache_dir = Path(cache_dir)
        self.ohlcv_dir = self.cache_dir / "ohlcv"
        self.metadata_dir = self.cache_dir / "metadata"
        self.models_dir = self.cache_dir / "models"
        
        # Create all directories if they don't exist
        self.ohlcv_dir.mkdir(parents=True, exist_ok=True)
        self.metadata_dir.mkdir(parents=True, exist_ok=True)
        self.models_dir.mkdir(parents=True, exist_ok=True)
    
    def get(self, key: str) -> Optional[CachedData]:
        """
        Retrieve cached data if valid.
        
        Args:
            key: Cache key in format {ticker}_{exchange}
            
        Returns:
            CachedData if cache exists and is valid, None otherwise
        """
        data_path = self.ohlcv_dir / f"{key}.parquet"
        meta_path = self.metadata_dir / f"{key}_meta.json"
        
        # Check if both data and metadata files exist
        if not data_path.exists() or not meta_path.exists():
            return None
        
        try:
            # Load metadata
            with open(meta_path, 'r') as f:
                metadata = json.load(f)
            
            timestamp = datetime.fromisoformat(metadata['timestamp'])
            ttl_minutes = metadata['ttl_minutes']
            
            # Create CachedData object
            cached_data = CachedData(
                data=None,  # Lazy load - only load if valid
                timestamp=timestamp,
                ttl_minutes=ttl_minutes
            )
            
            # Validate cache TTL
            if not self.is_valid(cached_data):
                return None
            
            # Load data only if cache is valid
            data = pd.read_parquet(data_path, engine='pyarrow')
            
            return CachedData(
                data=data,
                timestamp=timestamp,
                ttl_minutes=ttl_minutes
            )
            
        except (json.JSONDecodeError, KeyError, ValueError, Exception):
            # If any error occurs reading cache, treat as cache miss
            return None
    
    def set(self, key: str, data: pd.DataFrame, ttl_minutes: int) -> None:
        """
        Store data with TTL.
        
        Args:
            key: Cache key in format {ticker}_{exchange}
            data: DataFrame to cache
            ttl_minutes: Time-to-live in minutes
        """
        data_path = self.ohlcv_dir / f"{key}.parquet"
        meta_path = self.metadata_dir / f"{key}_meta.json"
        
        # Store data as Parquet
        data.to_parquet(data_path, engine='pyarrow', index=False)
        
        # Store metadata as JSON
        metadata = {
            'timestamp': datetime.now().isoformat(),
            'ttl_minutes': ttl_minutes
        }
        
        with open(meta_path, 'w') as f:
            json.dump(metadata, f, indent=2)
    
    def is_valid(self, cached_data: CachedData) -> bool:
        """
        Validate cache TTL.
        
        Args:
            cached_data: CachedData object to validate
            
        Returns:
            True if cache is still valid, False otherwise
        """
        current_time = datetime.now()
        expiry_time = cached_data.timestamp + timedelta(minutes=cached_data.ttl_minutes)
        return current_time < expiry_time
    
    def get_ttl(self, exchange: str, is_market_hours: bool = False) -> int:
        """
        Get TTL based on market hours.
        
        Args:
            exchange: Exchange name (NSE, BSE, NYSE, NASDAQ)
            is_market_hours: Whether current time is within market hours
            
        Returns:
            TTL in minutes: 15 if market hours active, 1440 (24 hours) otherwise
        """
        if is_market_hours:
            return 15  # 15 minutes during market hours
        else:
            return 1440  # 24 hours (1440 minutes) after hours

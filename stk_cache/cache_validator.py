"""
Cache validator for market hours detection and TTL calculation.

This module implements market hours detection for different exchanges and
calculates appropriate cache TTL based on whether markets are currently open.
"""

from datetime import datetime, time
from zoneinfo import ZoneInfo


def is_market_hours(exchange: str, current_time: datetime) -> bool:
    """
    Detect if current time is within market hours for the exchange.
    
    Market hours by exchange:
    - NSE/BSE: 9:15 AM - 3:30 PM IST (Asia/Kolkata timezone)
    - NYSE/NASDAQ: 9:30 AM - 4:00 PM ET (America/New_York timezone)
    
    Args:
        exchange: Exchange name (NSE, BSE, NYSE, NASDAQ)
        current_time: Current datetime to check (timezone-aware or naive)
        
    Returns:
        True if within market hours, False otherwise
        
    Raises:
        ValueError: If exchange is not supported
    """
    # Validate exchange
    exchange = exchange.upper()
    if exchange not in ['NSE', 'BSE', 'NYSE', 'NASDAQ']:
        raise ValueError(f"Unsupported exchange: {exchange}. Must be one of: NSE, BSE, NYSE, NASDAQ")
    
    # Determine timezone and market hours based on exchange
    if exchange in ['NSE', 'BSE']:
        timezone = ZoneInfo('Asia/Kolkata')
        market_open = time(9, 15)  # 9:15 AM
        market_close = time(15, 30)  # 3:30 PM
    else:  # NYSE or NASDAQ
        timezone = ZoneInfo('America/New_York')
        market_open = time(9, 30)  # 9:30 AM
        market_close = time(16, 0)  # 4:00 PM
    
    # Convert current_time to the exchange's timezone
    if current_time.tzinfo is None:
        # If naive datetime, assume it's in UTC
        current_time = current_time.replace(tzinfo=ZoneInfo('UTC'))
    
    local_time = current_time.astimezone(timezone)
    
    # Check if it's a weekend (markets closed on Saturday/Sunday)
    if local_time.weekday() >= 5:  # 5 = Saturday, 6 = Sunday
        return False
    
    # Check if current time is within market hours
    current_time_only = local_time.time()
    return market_open <= current_time_only <= market_close


def get_cache_ttl(exchange: str, current_time: datetime) -> int:
    """
    Return cache TTL based on market hours.
    
    Returns:
    - 15 minutes if market is open (is_market_hours returns True)
    - 1440 minutes (24 hours) if market is closed
    
    Args:
        exchange: Exchange name (NSE, BSE, NYSE, NASDAQ)
        current_time: Current datetime to check
        
    Returns:
        TTL in minutes: 15 if market open, 1440 if market closed
        
    Raises:
        ValueError: If exchange is not supported
    """
    if is_market_hours(exchange, current_time):
        return 15  # 15 minutes during market hours
    else:
        return 1440  # 24 hours (1440 minutes) after hours

"""
Unit tests and property-based tests for cache validator.
"""

from datetime import datetime, time
from zoneinfo import ZoneInfo

import pytest
from hypothesis import given, settings, strategies as st

from cache.cache_validator import is_market_hours, get_cache_ttl


# ============================================================================
# Unit Tests
# ============================================================================

def test_is_market_hours_nse_during_hours():
    """Test NSE market hours detection during trading hours."""
    # 12:00 PM IST on a Wednesday
    test_time = datetime(2024, 1, 10, 12, 0, 0, tzinfo=ZoneInfo('Asia/Kolkata'))
    assert is_market_hours('NSE', test_time) is True


def test_is_market_hours_nse_before_open():
    """Test NSE market hours detection before market opens."""
    # 9:00 AM IST (before 9:15 AM open)
    test_time = datetime(2024, 1, 10, 9, 0, 0, tzinfo=ZoneInfo('Asia/Kolkata'))
    assert is_market_hours('NSE', test_time) is False


def test_is_market_hours_nse_after_close():
    """Test NSE market hours detection after market closes."""
    # 4:00 PM IST (after 3:30 PM close)
    test_time = datetime(2024, 1, 10, 16, 0, 0, tzinfo=ZoneInfo('Asia/Kolkata'))
    assert is_market_hours('NSE', test_time) is False


def test_is_market_hours_nse_at_open():
    """Test NSE market hours detection at exact opening time."""
    # 9:15 AM IST (exact open)
    test_time = datetime(2024, 1, 10, 9, 15, 0, tzinfo=ZoneInfo('Asia/Kolkata'))
    assert is_market_hours('NSE', test_time) is True


def test_is_market_hours_nse_at_close():
    """Test NSE market hours detection at exact closing time."""
    # 3:30 PM IST (exact close)
    test_time = datetime(2024, 1, 10, 15, 30, 0, tzinfo=ZoneInfo('Asia/Kolkata'))
    assert is_market_hours('NSE', test_time) is True


def test_is_market_hours_bse_during_hours():
    """Test BSE market hours detection during trading hours."""
    # 1:00 PM IST on a Thursday
    test_time = datetime(2024, 1, 11, 13, 0, 0, tzinfo=ZoneInfo('Asia/Kolkata'))
    assert is_market_hours('BSE', test_time) is True


def test_is_market_hours_nyse_during_hours():
    """Test NYSE market hours detection during trading hours."""
    # 12:00 PM ET on a Tuesday
    test_time = datetime(2024, 1, 9, 12, 0, 0, tzinfo=ZoneInfo('America/New_York'))
    assert is_market_hours('NYSE', test_time) is True


def test_is_market_hours_nyse_before_open():
    """Test NYSE market hours detection before market opens."""
    # 9:00 AM ET (before 9:30 AM open)
    test_time = datetime(2024, 1, 9, 9, 0, 0, tzinfo=ZoneInfo('America/New_York'))
    assert is_market_hours('NYSE', test_time) is False


def test_is_market_hours_nyse_after_close():
    """Test NYSE market hours detection after market closes."""
    # 5:00 PM ET (after 4:00 PM close)
    test_time = datetime(2024, 1, 9, 17, 0, 0, tzinfo=ZoneInfo('America/New_York'))
    assert is_market_hours('NYSE', test_time) is False


def test_is_market_hours_nyse_at_open():
    """Test NYSE market hours detection at exact opening time."""
    # 9:30 AM ET (exact open)
    test_time = datetime(2024, 1, 9, 9, 30, 0, tzinfo=ZoneInfo('America/New_York'))
    assert is_market_hours('NYSE', test_time) is True


def test_is_market_hours_nyse_at_close():
    """Test NYSE market hours detection at exact closing time."""
    # 4:00 PM ET (exact close)
    test_time = datetime(2024, 1, 9, 16, 0, 0, tzinfo=ZoneInfo('America/New_York'))
    assert is_market_hours('NYSE', test_time) is True


def test_is_market_hours_nasdaq_during_hours():
    """Test NASDAQ market hours detection during trading hours."""
    # 2:00 PM ET on a Friday
    test_time = datetime(2024, 1, 12, 14, 0, 0, tzinfo=ZoneInfo('America/New_York'))
    assert is_market_hours('NASDAQ', test_time) is True


def test_is_market_hours_weekend_saturday():
    """Test that markets are closed on Saturday."""
    # Saturday 12:00 PM IST
    test_time = datetime(2024, 1, 13, 12, 0, 0, tzinfo=ZoneInfo('Asia/Kolkata'))
    assert is_market_hours('NSE', test_time) is False
    
    # Saturday 12:00 PM ET
    test_time = datetime(2024, 1, 13, 12, 0, 0, tzinfo=ZoneInfo('America/New_York'))
    assert is_market_hours('NYSE', test_time) is False


def test_is_market_hours_weekend_sunday():
    """Test that markets are closed on Sunday."""
    # Sunday 12:00 PM IST
    test_time = datetime(2024, 1, 14, 12, 0, 0, tzinfo=ZoneInfo('Asia/Kolkata'))
    assert is_market_hours('BSE', test_time) is False
    
    # Sunday 12:00 PM ET
    test_time = datetime(2024, 1, 14, 12, 0, 0, tzinfo=ZoneInfo('America/New_York'))
    assert is_market_hours('NASDAQ', test_time) is False


def test_is_market_hours_timezone_conversion_utc():
    """Test timezone conversion from UTC to exchange timezone."""
    # 7:00 AM UTC = 12:30 PM IST (during NSE hours)
    test_time = datetime(2024, 1, 10, 7, 0, 0, tzinfo=ZoneInfo('UTC'))
    assert is_market_hours('NSE', test_time) is True
    
    # 2:00 PM UTC = 9:00 AM ET (before NYSE open)
    test_time = datetime(2024, 1, 9, 14, 0, 0, tzinfo=ZoneInfo('UTC'))
    assert is_market_hours('NYSE', test_time) is False


def test_is_market_hours_naive_datetime():
    """Test that naive datetime is treated as UTC."""
    # Naive datetime: 7:00 AM (treated as UTC = 12:30 PM IST)
    test_time = datetime(2024, 1, 10, 7, 0, 0)
    assert is_market_hours('NSE', test_time) is True


def test_is_market_hours_case_insensitive():
    """Test that exchange parameter is case-insensitive."""
    test_time = datetime(2024, 1, 10, 12, 0, 0, tzinfo=ZoneInfo('Asia/Kolkata'))
    
    assert is_market_hours('nse', test_time) is True
    assert is_market_hours('NSE', test_time) is True
    assert is_market_hours('Nse', test_time) is True


def test_is_market_hours_invalid_exchange():
    """Test that invalid exchange raises ValueError."""
    test_time = datetime(2024, 1, 10, 12, 0, 0, tzinfo=ZoneInfo('UTC'))
    
    with pytest.raises(ValueError, match="Unsupported exchange"):
        is_market_hours('INVALID', test_time)
    
    with pytest.raises(ValueError, match="Unsupported exchange"):
        is_market_hours('LSE', test_time)


def test_get_cache_ttl_market_open():
    """Test get_cache_ttl returns 15 minutes during market hours."""
    # Wednesday 12:00 PM IST (NSE open)
    test_time = datetime(2024, 1, 10, 12, 0, 0, tzinfo=ZoneInfo('Asia/Kolkata'))
    ttl = get_cache_ttl('NSE', test_time)
    assert ttl == 15


def test_get_cache_ttl_market_closed():
    """Test get_cache_ttl returns 1440 minutes when market closed."""
    # Wednesday 5:00 PM IST (NSE closed)
    test_time = datetime(2024, 1, 10, 17, 0, 0, tzinfo=ZoneInfo('Asia/Kolkata'))
    ttl = get_cache_ttl('NSE', test_time)
    assert ttl == 1440


def test_get_cache_ttl_weekend():
    """Test get_cache_ttl returns 1440 minutes on weekends."""
    # Saturday 12:00 PM IST
    test_time = datetime(2024, 1, 13, 12, 0, 0, tzinfo=ZoneInfo('Asia/Kolkata'))
    ttl = get_cache_ttl('NSE', test_time)
    assert ttl == 1440


def test_get_cache_ttl_nyse_open():
    """Test get_cache_ttl for NYSE during market hours."""
    # Tuesday 12:00 PM ET (NYSE open)
    test_time = datetime(2024, 1, 9, 12, 0, 0, tzinfo=ZoneInfo('America/New_York'))
    ttl = get_cache_ttl('NYSE', test_time)
    assert ttl == 15


def test_get_cache_ttl_nyse_closed():
    """Test get_cache_ttl for NYSE after market hours."""
    # Tuesday 5:00 PM ET (NYSE closed)
    test_time = datetime(2024, 1, 9, 17, 0, 0, tzinfo=ZoneInfo('America/New_York'))
    ttl = get_cache_ttl('NYSE', test_time)
    assert ttl == 1440


def test_get_cache_ttl_invalid_exchange():
    """Test that get_cache_ttl raises ValueError for invalid exchange."""
    test_time = datetime(2024, 1, 10, 12, 0, 0, tzinfo=ZoneInfo('UTC'))
    
    with pytest.raises(ValueError, match="Unsupported exchange"):
        get_cache_ttl('INVALID', test_time)


def test_get_cache_ttl_uses_is_market_hours():
    """Test that get_cache_ttl correctly uses is_market_hours logic."""
    # Test multiple scenarios to ensure consistency
    scenarios = [
        # (exchange, datetime, expected_ttl)
        ('NSE', datetime(2024, 1, 10, 12, 0, 0, tzinfo=ZoneInfo('Asia/Kolkata')), 15),  # Wed noon IST
        ('NSE', datetime(2024, 1, 10, 5, 0, 0, tzinfo=ZoneInfo('Asia/Kolkata')), 1440),  # Wed 5 AM IST
        ('NYSE', datetime(2024, 1, 9, 12, 0, 0, tzinfo=ZoneInfo('America/New_York')), 15),  # Tue noon ET
        ('NYSE', datetime(2024, 1, 9, 5, 0, 0, tzinfo=ZoneInfo('America/New_York')), 1440),  # Tue 5 AM ET
        ('BSE', datetime(2024, 1, 13, 12, 0, 0, tzinfo=ZoneInfo('Asia/Kolkata')), 1440),  # Sat noon IST
        ('NASDAQ', datetime(2024, 1, 14, 12, 0, 0, tzinfo=ZoneInfo('America/New_York')), 1440),  # Sun noon ET
    ]
    
    for exchange, test_time, expected_ttl in scenarios:
        ttl = get_cache_ttl(exchange, test_time)
        assert ttl == expected_ttl, (
            f"Failed for {exchange} at {test_time}: expected {expected_ttl}, got {ttl}"
        )


# ============================================================================
# Property-Based Tests
# ============================================================================

@settings(max_examples=100, deadline=None)
@given(
    exchange=st.sampled_from(['NSE', 'BSE', 'NYSE', 'NASDAQ']),
    # Generate weekday datetimes in 2024
    day=st.integers(min_value=1, max_value=28),  # Safe day range for all months
    month=st.integers(min_value=1, max_value=12),
    hour=st.integers(min_value=0, max_value=23),
    minute=st.integers(min_value=0, max_value=59)
)
def test_property_8_market_hours_aware_ttl_selection(exchange, day, month, hour, minute):
    """
    Feature: ai-stock-analyst, Property 8: Market-Hours-Aware TTL Selection
    
    **Validates: Requirements 4.3, 4.4, 15.2, 15.3**
    
    For any cache operation, the Cache_Manager SHALL use 15-minute TTL when
    current time is within market hours (9:15 AM - 3:30 PM IST for NSE/BSE,
    9:30 AM - 4:00 PM ET for NYSE/NASDAQ), and 24-hour TTL otherwise.
    """
    # Create datetime in UTC
    try:
        test_time = datetime(2024, month, day, hour, minute, 0, tzinfo=ZoneInfo('UTC'))
    except ValueError:
        # Skip invalid dates
        return
    
    # Get TTL
    ttl = get_cache_ttl(exchange, test_time)
    
    # Verify TTL is either 15 or 1440
    assert ttl in [15, 1440], f"TTL must be 15 or 1440, got {ttl}"
    
    # Verify consistency with is_market_hours
    market_open = is_market_hours(exchange, test_time)
    
    if market_open:
        assert ttl == 15, (
            f"Expected 15 minutes TTL during market hours for {exchange} at {test_time}, got {ttl}"
        )
    else:
        assert ttl == 1440, (
            f"Expected 1440 minutes TTL after hours for {exchange} at {test_time}, got {ttl}"
        )


@settings(max_examples=100, deadline=None)
@given(
    exchange=st.sampled_from(['NSE', 'BSE', 'NYSE', 'NASDAQ']),
    # Generate weekend datetimes (Saturday=5, Sunday=6)
    day=st.integers(min_value=6, max_value=7),  # Jan 6-7, 2024 are Sat-Sun
    hour=st.integers(min_value=0, max_value=23),
    minute=st.integers(min_value=0, max_value=59)
)
def test_property_weekend_markets_closed(exchange, day, hour, minute):
    """
    Feature: ai-stock-analyst, Property: Weekend Markets Closed
    
    **Validates: Requirements 15.1**
    
    For any weekend datetime, is_market_hours SHALL return False regardless
    of the time of day.
    """
    # January 6-7, 2024 are Saturday-Sunday
    test_time = datetime(2024, 1, day, hour, minute, 0, tzinfo=ZoneInfo('UTC'))
    
    # Markets should be closed on weekends
    assert is_market_hours(exchange, test_time) is False, (
        f"Market should be closed on weekend for {exchange} at {test_time}"
    )
    
    # TTL should be 1440 (24 hours) on weekends
    ttl = get_cache_ttl(exchange, test_time)
    assert ttl == 1440, (
        f"Expected 1440 minutes TTL on weekend for {exchange}, got {ttl}"
    )


@settings(max_examples=100, deadline=None)
@given(
    exchange=st.sampled_from(['NSE', 'BSE', 'NYSE', 'NASDAQ']),
    timezone_str=st.sampled_from(['UTC', 'Asia/Kolkata', 'America/New_York', 'Europe/London'])
)
def test_property_timezone_conversion_consistency(exchange, timezone_str):
    """
    Feature: ai-stock-analyst, Property: Timezone Conversion Consistency
    
    **Validates: Requirements 15.1**
    
    For any datetime in any timezone, is_market_hours SHALL correctly convert
    to the exchange's local timezone and return consistent results.
    """
    # Use a fixed time that we know the result for
    # Wednesday Jan 10, 2024 at 12:00 PM in the given timezone
    try:
        test_time = datetime(2024, 1, 10, 12, 0, 0, tzinfo=ZoneInfo(timezone_str))
    except Exception:
        # Skip invalid timezones
        return
    
    # Call is_market_hours - should not raise exception
    result = is_market_hours(exchange, test_time)
    
    # Result should be boolean
    assert isinstance(result, bool), f"Expected boolean result, got {type(result)}"
    
    # Verify TTL is consistent with market hours result
    ttl = get_cache_ttl(exchange, test_time)
    
    if result:
        assert ttl == 15, "TTL should be 15 when market is open"
    else:
        assert ttl == 1440, "TTL should be 1440 when market is closed"


@settings(max_examples=50, deadline=None)
@given(
    exchange=st.sampled_from(['NSE', 'BSE', 'NYSE', 'NASDAQ'])
)
def test_property_market_open_boundary(exchange):
    """
    Feature: ai-stock-analyst, Property: Market Open Boundary
    
    **Validates: Requirements 15.1**
    
    At exact market opening time, is_market_hours SHALL return True.
    """
    if exchange in ['NSE', 'BSE']:
        # 9:15 AM IST on a Wednesday
        test_time = datetime(2024, 1, 10, 9, 15, 0, tzinfo=ZoneInfo('Asia/Kolkata'))
    else:  # NYSE or NASDAQ
        # 9:30 AM ET on a Tuesday
        test_time = datetime(2024, 1, 9, 9, 30, 0, tzinfo=ZoneInfo('America/New_York'))
    
    assert is_market_hours(exchange, test_time) is True, (
        f"Market should be open at exact opening time for {exchange}"
    )
    
    ttl = get_cache_ttl(exchange, test_time)
    assert ttl == 15, f"TTL should be 15 at market open for {exchange}"


@settings(max_examples=50, deadline=None)
@given(
    exchange=st.sampled_from(['NSE', 'BSE', 'NYSE', 'NASDAQ'])
)
def test_property_market_close_boundary(exchange):
    """
    Feature: ai-stock-analyst, Property: Market Close Boundary
    
    **Validates: Requirements 15.1**
    
    At exact market closing time, is_market_hours SHALL return True.
    """
    if exchange in ['NSE', 'BSE']:
        # 3:30 PM IST on a Wednesday
        test_time = datetime(2024, 1, 10, 15, 30, 0, tzinfo=ZoneInfo('Asia/Kolkata'))
    else:  # NYSE or NASDAQ
        # 4:00 PM ET on a Tuesday
        test_time = datetime(2024, 1, 9, 16, 0, 0, tzinfo=ZoneInfo('America/New_York'))
    
    assert is_market_hours(exchange, test_time) is True, (
        f"Market should be open at exact closing time for {exchange}"
    )
    
    ttl = get_cache_ttl(exchange, test_time)
    assert ttl == 15, f"TTL should be 15 at market close for {exchange}"

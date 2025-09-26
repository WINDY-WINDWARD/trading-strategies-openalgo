# app/utils/time_helpers.py
"""
Time-related utility functions.
"""

import re
from datetime import datetime, timedelta
from typing import Tuple, Optional
import pandas as pd


def parse_timeframe(timeframe: str) -> Tuple[int, str]:
    """
    Parse timeframe string into number and unit.
    
    Args:
        timeframe: Timeframe string (e.g., '1h', '5m', '1d')
        
    Returns:
        Tuple of (number, unit)
        
    Raises:
        ValueError: If timeframe format is invalid
    """
    pattern = r'^(\d+)([mhd])$'
    match = re.match(pattern, timeframe.lower())
    
    if not match:
        raise ValueError(f"Invalid timeframe format: {timeframe}")
    
    number = int(match.group(1))
    unit = match.group(2)
    
    return number, unit


def timeframe_to_seconds(timeframe: str) -> int:
    """
    Convert timeframe string to seconds.
    
    Args:
        timeframe: Timeframe string (e.g., '1h', '5m', '1d')
        
    Returns:
        Number of seconds
        
    Raises:
        ValueError: If timeframe format is invalid
    """
    number, unit = parse_timeframe(timeframe)
    
    multipliers = {
        'm': 60,        # minutes
        'h': 3600,      # hours
        'd': 86400      # days
    }
    
    if unit not in multipliers:
        raise ValueError(f"Unsupported time unit: {unit}")
    
    return number * multipliers[unit]


def timeframe_to_timedelta(timeframe: str) -> timedelta:
    """
    Convert timeframe string to timedelta object.
    
    Args:
        timeframe: Timeframe string
        
    Returns:
        Timedelta object
    """
    seconds = timeframe_to_seconds(timeframe)
    return timedelta(seconds=seconds)


def generate_time_range(
    start: datetime,
    end: datetime,
    timeframe: str
) -> pd.DatetimeIndex:
    """
    Generate datetime range for given timeframe.
    
    Args:
        start: Start datetime
        end: End datetime
        timeframe: Timeframe string
        
    Returns:
        Pandas DatetimeIndex
    """
    number, unit = parse_timeframe(timeframe)
    
    freq_map = {
        'm': f"{number}T",   # minutes
        'h': f"{number}H",   # hours  
        'd': f"{number}D"    # days
    }
    
    freq = freq_map.get(unit)
    if not freq:
        raise ValueError(f"Unsupported time unit for range generation: {unit}")
    
    return pd.date_range(start=start, end=end, freq=freq)


def align_datetime_to_timeframe(dt: datetime, timeframe: str) -> datetime:
    """
    Align datetime to timeframe boundary.
    
    Args:
        dt: Datetime to align
        timeframe: Timeframe string
        
    Returns:
        Aligned datetime
    """
    number, unit = parse_timeframe(timeframe)
    
    if unit == 'm':
        # Align to minute boundary
        minutes = (dt.minute // number) * number
        return dt.replace(minute=minutes, second=0, microsecond=0)
    
    elif unit == 'h':
        # Align to hour boundary
        hours = (dt.hour // number) * number
        return dt.replace(hour=hours, minute=0, second=0, microsecond=0)
    
    elif unit == 'd':
        # Align to day boundary
        return dt.replace(hour=0, minute=0, second=0, microsecond=0)
    
    else:
        raise ValueError(f"Unsupported time unit for alignment: {unit}")


def get_market_hours(exchange: str = "NSE") -> Tuple[int, int]:
    """
    Get market hours for exchange.
    
    Args:
        exchange: Exchange name
        
    Returns:
        Tuple of (open_hour, close_hour) in 24-hour format
    """
    market_hours = {
        "NSE": (9, 15),   # 9:15 AM to 3:30 PM
        "BSE": (9, 15),   # Same as NSE
        "NYSE": (9, 16),  # 9:30 AM to 4:00 PM EST
        "NASDAQ": (9, 16) # Same as NYSE
    }
    
    return market_hours.get(exchange.upper(), (9, 16))


def is_market_open(dt: datetime, exchange: str = "NSE") -> bool:
    """
    Check if market is open at given datetime.
    
    Args:
        dt: Datetime to check
        exchange: Exchange name
        
    Returns:
        True if market is open
    """
    # Skip weekends
    if dt.weekday() >= 5:  # Saturday = 5, Sunday = 6
        return False
    
    open_hour, close_hour = get_market_hours(exchange)
    
    # Basic hour check (simplified)
    if exchange.upper() in ["NSE", "BSE"]:
        # NSE/BSE: 9:15 AM to 3:30 PM
        if dt.hour < 9 or (dt.hour == 9 and dt.minute < 15):
            return False
        if dt.hour > 15 or (dt.hour == 15 and dt.minute > 30):
            return False
    else:
        # Other markets: simple hour check
        if dt.hour < open_hour or dt.hour >= close_hour:
            return False
    
    return True


def format_duration(seconds: float) -> str:
    """
    Format duration in seconds to human readable string.
    
    Args:
        seconds: Duration in seconds
        
    Returns:
        Formatted duration string
    """
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}m"
    elif seconds < 86400:
        hours = seconds / 3600
        return f"{hours:.1f}h"
    else:
        days = seconds / 86400
        return f"{days:.1f}d"


def parse_date_string(date_str: str) -> datetime:
    """
    Parse date string in various formats.
    
    Args:
        date_str: Date string
        
    Returns:
        Parsed datetime
        
    Raises:
        ValueError: If date format is not recognized
    """
    formats = [
        "%Y-%m-%d",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%Y%m%d"
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    
    raise ValueError(f"Unable to parse date string: {date_str}")

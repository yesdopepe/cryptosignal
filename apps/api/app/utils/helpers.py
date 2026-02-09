"""Helper utility functions."""
import hashlib
from datetime import datetime
from typing import Optional, Any


def format_price(price: float, decimals: Optional[int] = None) -> str:
    """
    Format price for display with appropriate decimal places.
    
    Args:
        price: The price to format
        decimals: Optional fixed number of decimals
    
    Returns:
        Formatted price string
    """
    if price is None:
        return "N/A"
    
    if decimals is not None:
        return f"${price:,.{decimals}f}"
    
    # Auto-determine decimals based on price magnitude
    if price >= 1000:
        return f"${price:,.2f}"
    elif price >= 1:
        return f"${price:,.4f}"
    elif price >= 0.0001:
        return f"${price:,.6f}"
    else:
        return f"${price:,.10f}"


def format_percentage(value: float, include_sign: bool = True) -> str:
    """
    Format percentage for display.
    
    Args:
        value: The percentage value
        include_sign: Whether to include + sign for positive values
    
    Returns:
        Formatted percentage string
    """
    if value is None:
        return "N/A"
    
    if include_sign and value > 0:
        return f"+{value:.2f}%"
    return f"{value:.2f}%"


def format_datetime(dt: datetime, format: str = "%Y-%m-%d %H:%M:%S") -> str:
    """
    Format datetime for display.
    
    Args:
        dt: Datetime object
        format: Format string
    
    Returns:
        Formatted datetime string
    """
    if dt is None:
        return "N/A"
    return dt.strftime(format)


def calculate_roi(entry_price: float, current_price: float) -> float:
    """
    Calculate ROI percentage.
    
    Args:
        entry_price: Entry/buy price
        current_price: Current price
    
    Returns:
        ROI as percentage
    """
    if entry_price <= 0:
        return 0.0
    return ((current_price - entry_price) / entry_price) * 100


def generate_cache_key(*args: Any, prefix: str = "") -> str:
    """
    Generate a cache key from arguments.
    
    Args:
        *args: Arguments to include in key
        prefix: Optional prefix for the key
    
    Returns:
        Cache key string
    """
    key_parts = [str(arg) for arg in args]
    key_string = ":".join(key_parts)
    key_hash = hashlib.md5(key_string.encode()).hexdigest()[:12]
    
    if prefix:
        return f"{prefix}:{key_hash}"
    return key_hash


def time_ago(dt: datetime) -> str:
    """
    Get human-readable time ago string.
    
    Args:
        dt: Datetime to compare with now
    
    Returns:
        Human-readable string like "5 minutes ago"
    """
    if dt is None:
        return "N/A"
    
    now = datetime.utcnow()
    diff = now - dt
    
    seconds = diff.total_seconds()
    
    if seconds < 60:
        return "just now"
    elif seconds < 3600:
        minutes = int(seconds / 60)
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    elif seconds < 86400:
        hours = int(seconds / 3600)
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    elif seconds < 604800:
        days = int(seconds / 86400)
        return f"{days} day{'s' if days != 1 else ''} ago"
    elif seconds < 2592000:
        weeks = int(seconds / 604800)
        return f"{weeks} week{'s' if weeks != 1 else ''} ago"
    else:
        months = int(seconds / 2592000)
        return f"{months} month{'s' if months != 1 else ''} ago"


def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """
    Truncate text to maximum length.
    
    Args:
        text: Text to truncate
        max_length: Maximum length
        suffix: Suffix to add if truncated
    
    Returns:
        Truncated text
    """
    if not text:
        return ""
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def sanitize_string(text: str) -> str:
    """
    Sanitize string for safe display.
    
    Args:
        text: Text to sanitize
    
    Returns:
        Sanitized text
    """
    if not text:
        return ""
    
    # Remove potentially dangerous characters
    dangerous_chars = ['<', '>', '"', "'", '&', '\x00']
    result = text
    for char in dangerous_chars:
        result = result.replace(char, '')
    
    return result.strip()

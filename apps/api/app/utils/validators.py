"""Input validation utilities."""
import re
from datetime import datetime
from typing import Optional, Tuple
from fastapi import HTTPException, status


VALID_SENTIMENTS = ["BULLISH", "BEARISH", "NEUTRAL"]
TOKEN_PATTERN = re.compile(r'^[A-Z]{2,10}$')


def validate_token_symbol(symbol: str) -> str:
    """
    Validate and normalize a token symbol.
    
    Args:
        symbol: Token symbol to validate
    
    Returns:
        Normalized (uppercase) symbol
    
    Raises:
        HTTPException: If symbol is invalid
    """
    if not symbol:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token symbol is required"
        )
    
    normalized = symbol.upper().strip()
    
    if not TOKEN_PATTERN.match(normalized):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid token symbol '{symbol}'. Must be 2-10 uppercase letters."
        )
    
    return normalized


def validate_sentiment(sentiment: str) -> str:
    """
    Validate and normalize a sentiment value.
    
    Args:
        sentiment: Sentiment to validate
    
    Returns:
        Normalized (uppercase) sentiment
    
    Raises:
        HTTPException: If sentiment is invalid
    """
    if not sentiment:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sentiment is required"
        )
    
    normalized = sentiment.upper().strip()
    
    if normalized not in VALID_SENTIMENTS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid sentiment '{sentiment}'. Must be one of: {VALID_SENTIMENTS}"
        )
    
    return normalized


def validate_date_range(
    start_date: Optional[datetime],
    end_date: Optional[datetime],
    max_days: int = 365
) -> Tuple[Optional[datetime], Optional[datetime]]:
    """
    Validate a date range.
    
    Args:
        start_date: Start date
        end_date: End date
        max_days: Maximum allowed range in days
    
    Returns:
        Tuple of (start_date, end_date)
    
    Raises:
        HTTPException: If date range is invalid
    """
    if start_date and end_date:
        if start_date > end_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Start date must be before end date"
            )
        
        delta = (end_date - start_date).days
        if delta > max_days:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Date range cannot exceed {max_days} days"
            )
    
    if start_date and start_date > datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Start date cannot be in the future"
        )
    
    return start_date, end_date


def validate_pagination(
    limit: int,
    offset: int,
    max_limit: int = 10000
) -> Tuple[int, int]:
    """
    Validate pagination parameters.
    
    Args:
        limit: Number of records to return
        offset: Number of records to skip
        max_limit: Maximum allowed limit
    
    Returns:
        Tuple of (limit, offset)
    
    Raises:
        HTTPException: If pagination params are invalid
    """
    if limit < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Limit must be at least 1"
        )
    
    if limit > max_limit:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Limit cannot exceed {max_limit}"
        )
    
    if offset < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Offset cannot be negative"
        )
    
    return limit, offset


def validate_admin_key(api_key: str, expected_key: str) -> bool:
    """
    Validate admin API key.
    
    Args:
        api_key: Provided API key
        expected_key: Expected API key
    
    Returns:
        True if valid
    
    Raises:
        HTTPException: If key is invalid
    """
    if not api_key or api_key != expected_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or missing admin API key"
        )
    return True

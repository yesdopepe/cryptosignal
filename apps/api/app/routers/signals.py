"""Signals API router with caching."""
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query, Header, Request, Response
from fastapi_cache.decorator import cache
from sqlalchemy import select, func, desc, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models import Signal, Channel
from app.schemas.signal import (
    SignalCreate,
    SignalUpdate,
    SignalResponse,
    SignalListResponse,
)
from app.config import settings
from app.cache import custom_key_builder

router = APIRouter(prefix="/signals", tags=["Signals"])


@router.get("", response_model=SignalListResponse)
@cache(expire=15, key_builder=custom_key_builder)  # 15 second cache
async def list_signals(
    request: Request,
    response: Response,
    limit: int = Query(default=50, ge=1, le=1000, description="Number of signals to return"),
    offset: int = Query(default=0, ge=0, description="Number of signals to skip"),
    channel_id: Optional[int] = Query(default=None, description="Filter by channel ID"),
    token_symbol: Optional[str] = Query(default=None, description="Filter by token symbol"),
    sentiment: Optional[str] = Query(default=None, description="Filter by sentiment"),
    success: Optional[bool] = Query(default=None, description="Filter by success status"),
    start_date: Optional[datetime] = Query(default=None, description="Filter by start date"),
    end_date: Optional[datetime] = Query(default=None, description="Filter by end date"),
    session: AsyncSession = Depends(get_session),
):
    """
    List signals with pagination and optional filters.
    
    - **limit**: Maximum number of signals to return (1-1000)
    - **offset**: Number of signals to skip for pagination
    - **channel_id**: Filter signals by channel
    - **token_symbol**: Filter signals by token (e.g., BTC, ETH)
    - **sentiment**: Filter by sentiment (BULLISH, BEARISH, NEUTRAL)
    - **success**: Filter by success status
    - **start_date**: Filter signals after this date
    - **end_date**: Filter signals before this date
    """
    # Build query with filters
    query = select(Signal)
    count_query = select(func.count(Signal.id))
    
    filters = []
    
    if channel_id:
        filters.append(Signal.channel_id == channel_id)
    
    if token_symbol:
        filters.append(Signal.token_symbol == token_symbol.upper())
    
    if sentiment:
        filters.append(Signal.sentiment == sentiment.upper())
    
    if success is not None:
        filters.append(Signal.success == success)
    
    if start_date:
        filters.append(Signal.timestamp >= start_date)
    
    if end_date:
        filters.append(Signal.timestamp <= end_date)
    
    if filters:
        query = query.where(and_(*filters))
        count_query = count_query.where(and_(*filters))
    
    # Get total count
    total_result = await session.execute(count_query)
    total = total_result.scalar()
    
    # Get signals with pagination
    query = query.order_by(desc(Signal.timestamp)).offset(offset).limit(limit)
    result = await session.execute(query)
    signals = result.scalars().all()
    
    return SignalListResponse(
        items=[SignalResponse.model_validate(s) for s in signals],
        total=total,
        limit=limit,
        offset=offset,
        has_more=(offset + limit) < total,
    )


@router.get("/{signal_id}", response_model=SignalResponse)
@cache(expire=30, key_builder=custom_key_builder)  # 30 second cache
async def get_signal(
    signal_id: int,
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_session),
):
    """
    Get a specific signal by ID.
    
    - **signal_id**: The unique identifier of the signal
    """
    result = await session.execute(
        select(Signal).where(Signal.id == signal_id)
    )
    signal = result.scalar_one_or_none()
    
    if not signal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Signal with ID {signal_id} not found"
        )
    
    return SignalResponse.model_validate(signal)


@router.get("/token/{symbol}", response_model=SignalListResponse)
@cache(expire=15, key_builder=custom_key_builder)  # 15 second cache
async def get_signals_by_token(
    symbol: str,
    request: Request,
    response: Response,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    """
    Get all signals for a specific token symbol.
    
    - **symbol**: Token symbol (e.g., BTC, ETH, SOL)
    - **limit**: Maximum number of signals to return
    - **offset**: Number of signals to skip
    """
    symbol_upper = symbol.upper()
    
    # Get total count
    count_result = await session.execute(
        select(func.count(Signal.id)).where(Signal.token_symbol == symbol_upper)
    )
    total = count_result.scalar()
    
    # Get signals
    result = await session.execute(
        select(Signal)
        .where(Signal.token_symbol == symbol_upper)
        .order_by(desc(Signal.timestamp))
        .offset(offset)
        .limit(limit)
    )
    signals = result.scalars().all()
    
    return SignalListResponse(
        items=[SignalResponse.model_validate(s) for s in signals],
        total=total,
        limit=limit,
        offset=offset,
        has_more=(offset + limit) < total,
    )


@router.post("", response_model=SignalResponse, status_code=status.HTTP_201_CREATED)
async def create_signal(
    signal_data: SignalCreate,
    x_admin_key: Optional[str] = Header(default=None, description="Admin API key"),
    session: AsyncSession = Depends(get_session),
):
    """
    Create a new signal. **Admin only**.
    
    Requires `X-Admin-Key` header with valid admin API key.
    """
    # Simple admin auth check
    if x_admin_key != settings.secret_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or missing admin API key"
        )
    
    # Verify channel exists
    channel_result = await session.execute(
        select(Channel).where(Channel.id == signal_data.channel_id)
    )
    channel = channel_result.scalar_one_or_none()
    
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Channel with ID {signal_data.channel_id} not found"
        )
    
    # Create signal
    signal = Signal(
        channel_id=signal_data.channel_id,
        channel_name=signal_data.channel_name,
        token_symbol=signal_data.token_symbol.upper(),
        token_name=signal_data.token_name,
        price_at_signal=signal_data.price_at_signal,
        current_price=signal_data.current_price,
        sentiment=signal_data.sentiment.upper(),
        message_text=signal_data.message_text,
        confidence_score=signal_data.confidence_score,
        timestamp=datetime.utcnow(),
        success=signal_data.success,
        roi_percent=signal_data.roi_percent,
        tags=signal_data.tags or [],
    )
    
    session.add(signal)
    await session.flush()
    await session.refresh(signal)
    
    return SignalResponse.model_validate(signal)


@router.delete("/{signal_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_signal(
    signal_id: int,
    x_admin_key: Optional[str] = Header(default=None, description="Admin API key"),
    session: AsyncSession = Depends(get_session),
):
    """
    Delete a signal by ID. **Admin only**.
    
    Requires `X-Admin-Key` header with valid admin API key.
    """
    # Simple admin auth check
    if x_admin_key != settings.secret_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or missing admin API key"
        )
    
    result = await session.execute(
        select(Signal).where(Signal.id == signal_id)
    )
    signal = result.scalar_one_or_none()
    
    if not signal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Signal with ID {signal_id} not found"
        )
    
    await session.delete(signal)
    return None

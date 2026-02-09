"""Channels API router."""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Header, Response, Request
from fastapi_cache.decorator import cache
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models import Channel, Signal
from app.schemas.channel import (
    ChannelCreate,
    ChannelUpdate,
    ChannelResponse,
    ChannelListResponse,
    ChannelStats,
)
from app.config import settings
from app.cache import custom_key_builder

router = APIRouter(prefix="/channels", tags=["Channels"])


@router.get("", response_model=ChannelListResponse)
@cache(expire=60, key_builder=custom_key_builder)  # 1 minute cache
async def list_channels(
    request: Request,
    response: Response,
    limit: int = Query(default=50, ge=1, le=100, description="Number of channels to return"),
    offset: int = Query(default=0, ge=0, description="Number of channels to skip"),
    active_only: bool = Query(default=True, description="Only return active channels"),
    session: AsyncSession = Depends(get_session),
):
    """
    List all monitored channels.
    
    - **limit**: Maximum number of channels to return (1-100)
    - **offset**: Number of channels to skip for pagination
    - **active_only**: Filter to only active channels (default: true)
    """
    # Build query
    query = select(Channel)
    count_query = select(func.count(Channel.id))
    
    if active_only:
        query = query.where(Channel.is_active == True)
        count_query = count_query.where(Channel.is_active == True)
    
    # Get total count
    total_result = await session.execute(count_query)
    total = total_result.scalar()
    
    # Get channels
    query = query.order_by(desc(Channel.total_signals)).offset(offset).limit(limit)
    result = await session.execute(query)
    channels = result.scalars().all()
    
    return ChannelListResponse(
        items=[ChannelResponse.model_validate(c) for c in channels],
        total=total,
        limit=limit,
        offset=offset,
        has_more=(offset + limit) < total,
    )


@router.get("/{channel_id}", response_model=ChannelResponse)
@cache(expire=60, key_builder=custom_key_builder)  # 1 minute cache
async def get_channel(
    channel_id: int,
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_session),
):
    """
    Get a specific channel by ID.
    
    - **channel_id**: The unique identifier of the channel
    """
    result = await session.execute(
        select(Channel).where(Channel.id == channel_id)
    )
    channel = result.scalar_one_or_none()
    
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Channel with ID {channel_id} not found"
        )
    
    return ChannelResponse.model_validate(channel)


@router.get("/{channel_id}/stats")
@cache(expire=300, key_builder=custom_key_builder)  # 5 minutes cache
async def get_channel_stats(
    channel_id: int,
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_session),
):
    """
    Get detailed statistics for a channel.
    
    **CACHED ENDPOINT** - Aggregates all channel signals.
    
    - Cache TTL: 5 minutes (300 seconds)
    
    Returns comprehensive channel performance metrics including:
    - Signal counts and success rates
    - ROI statistics
    - Sentiment breakdown
    - Time-based signal counts
    """
    # Get channel
    channel_result = await session.execute(
        select(Channel).where(Channel.id == channel_id)
    )
    channel = channel_result.scalar_one_or_none()
    
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Channel with ID {channel_id} not found"
        )
    
    # Get all signals for this channel
    signals_result = await session.execute(
        select(Signal).where(Signal.channel_id == channel_id)
    )
    signals = signals_result.scalars().all()
    
    if not signals:
        return {
            "id": channel.id,
            "name": channel.name,
            "total_signals": 0,
            "message": "No signals found for this channel",
        }
    
    # Calculate statistics
    total = len(signals)
    successful = sum(1 for s in signals if s.success)
    failed = sum(1 for s in signals if s.success is False)
    
    roi_values = [s.roi_percent for s in signals if s.roi_percent is not None]
    avg_roi = sum(roi_values) / len(roi_values) if roi_values else 0
    best_roi = max(roi_values) if roi_values else 0
    worst_roi = min(roi_values) if roi_values else 0
    
    bullish = sum(1 for s in signals if s.sentiment == "BULLISH")
    bearish = sum(1 for s in signals if s.sentiment == "BEARISH")
    neutral = sum(1 for s in signals if s.sentiment == "NEUTRAL")
    
    confidence_values = [s.confidence_score for s in signals]
    avg_confidence = sum(confidence_values) / len(confidence_values) if confidence_values else 0
    
    # Token frequency
    token_counts = {}
    for s in signals:
        token_counts[s.token_symbol] = token_counts.get(s.token_symbol, 0) + 1
    most_signaled = max(token_counts.items(), key=lambda x: x[1])[0] if token_counts else "N/A"
    
    # Time-based counts
    from datetime import datetime, timedelta
    now = datetime.utcnow()
    signals_24h = sum(1 for s in signals if s.timestamp >= now - timedelta(hours=24))
    signals_7d = sum(1 for s in signals if s.timestamp >= now - timedelta(days=7))
    signals_30d = sum(1 for s in signals if s.timestamp >= now - timedelta(days=30))
    
    response.headers["X-Cache-Status"] = "MISS"
    response.headers["Cache-Control"] = "max-age=300"
    
    return {
        "id": channel.id,
        "name": channel.name,
        "total_signals": total,
        "successful_signals": successful,
        "failed_signals": failed,
        "success_rate": round((successful / total * 100) if total > 0 else 0, 2),
        "avg_roi": round(avg_roi, 2),
        "best_roi": round(best_roi, 2),
        "worst_roi": round(worst_roi, 2),
        "total_bullish": bullish,
        "total_bearish": bearish,
        "total_neutral": neutral,
        "most_signaled_token": most_signaled,
        "avg_confidence": round(avg_confidence, 3),
        "signals_last_24h": signals_24h,
        "signals_last_7d": signals_7d,
        "signals_last_30d": signals_30d,
    }


@router.post("", response_model=ChannelResponse, status_code=status.HTTP_201_CREATED)
async def create_channel(
    channel_data: ChannelCreate,
    x_admin_key: Optional[str] = Header(default=None, description="Admin API key"),
    session: AsyncSession = Depends(get_session),
):
    """
    Add a new channel to monitor. **Admin only**.
    
    Requires `X-Admin-Key` header with valid admin API key.
    """
    # Simple admin auth check
    if x_admin_key != settings.secret_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or missing admin API key"
        )
    
    # Check if telegram_id already exists
    existing = await session.execute(
        select(Channel).where(Channel.telegram_id == channel_data.telegram_id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Channel with telegram_id '{channel_data.telegram_id}' already exists"
        )
    
    # Create channel
    channel = Channel(
        name=channel_data.name,
        telegram_id=channel_data.telegram_id,
        description=channel_data.description,
        subscriber_count=channel_data.subscriber_count,
        is_active=channel_data.is_active,
    )
    
    session.add(channel)
    await session.flush()
    await session.refresh(channel)
    
    return ChannelResponse.model_validate(channel)


@router.patch("/{channel_id}", response_model=ChannelResponse)
async def update_channel(
    channel_id: int,
    channel_data: ChannelUpdate,
    x_admin_key: Optional[str] = Header(default=None, description="Admin API key"),
    session: AsyncSession = Depends(get_session),
):
    """
    Update a channel. **Admin only**.
    
    Requires `X-Admin-Key` header with valid admin API key.
    """
    if x_admin_key != settings.secret_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or missing admin API key"
        )
    
    result = await session.execute(
        select(Channel).where(Channel.id == channel_id)
    )
    channel = result.scalar_one_or_none()
    
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Channel with ID {channel_id} not found"
        )
    
    # Update fields
    update_data = channel_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(channel, field, value)
    
    await session.flush()
    await session.refresh(channel)
    
    return ChannelResponse.model_validate(channel)


@router.delete("/{channel_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_channel(
    channel_id: int,
    x_admin_key: Optional[str] = Header(default=None, description="Admin API key"),
    session: AsyncSession = Depends(get_session),
):
    """
    Remove a channel from monitoring. **Admin only**.
    
    This will also delete all signals associated with the channel.
    Requires `X-Admin-Key` header with valid admin API key.
    """
    if x_admin_key != settings.secret_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or missing admin API key"
        )
    
    result = await session.execute(
        select(Channel).where(Channel.id == channel_id)
    )
    channel = result.scalar_one_or_none()
    
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Channel with ID {channel_id} not found"
        )
    
    await session.delete(channel)
    return None

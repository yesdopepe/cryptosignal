"""
Channel subscription router for per-user channel tracking.
Users can subscribe to channels from their Telegram to receive notifications.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy import select, and_
from datetime import datetime

from app.auth import get_current_user
from app.database import async_session_maker
from app.models import ChannelSubscription, User
from app.models.channel import Channel

router = APIRouter(prefix="/subscriptions", tags=["Channel Subscriptions"])


# ============== Request/Response Models ==============

class SubscribeRequest(BaseModel):
    """Request to subscribe to a channel."""
    channel_id: int
    channel_title: Optional[str] = None  # For display purposes
    notify_email: bool = False
    notify_telegram: bool = True  # Forward to saved messages


class UpdateSubscriptionRequest(BaseModel):
    """Request to update subscription settings."""
    notify_email: Optional[bool] = None
    notify_telegram: Optional[bool] = None
    is_active: Optional[bool] = None


class SubscriptionInfo(BaseModel):
    """Subscription information."""
    id: int
    channel_id: int
    channel_name: Optional[str] = None
    is_active: bool
    notify_email: bool
    notify_telegram: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


class SubscriptionListResponse(BaseModel):
    """Response with list of subscriptions."""
    success: bool
    subscriptions: List[SubscriptionInfo]
    count: int
    error: Optional[str] = None


class SubscriptionResponse(BaseModel):
    """Single subscription operation response."""
    success: bool
    subscription: Optional[SubscriptionInfo] = None
    message: Optional[str] = None
    error: Optional[str] = None


# ============== Endpoints ==============

@router.get("/", response_model=SubscriptionListResponse)
async def list_subscriptions(user = Depends(get_current_user)):
    """
    List all channel subscriptions for the current user.
    
    Returns all channels the user has subscribed to for tracking.
    """
    async with async_session_maker() as db:
        result = await db.execute(
            select(ChannelSubscription, Channel)
            .outerjoin(Channel, ChannelSubscription.channel_id == Channel.id)
            .where(ChannelSubscription.user_id == user.id)
            .order_by(ChannelSubscription.created_at.desc())
        )
        rows = result.all()
        
        subscriptions = []
        for sub, channel in rows:
            subscriptions.append(SubscriptionInfo(
                id=sub.id,
                channel_id=sub.channel_id,
                channel_name=channel.name if channel else None,
                is_active=sub.is_active,
                notify_email=sub.notify_email,
                notify_telegram=sub.notify_telegram,
                created_at=sub.created_at,
            ))
        
        return SubscriptionListResponse(
            success=True,
            subscriptions=subscriptions,
            count=len(subscriptions),
        )


@router.post("/", response_model=SubscriptionResponse)
async def subscribe_to_channel(
    request: SubscribeRequest,
    user = Depends(get_current_user)
):
    """
    Subscribe to a channel for tracking.
    
    The channel must be one that the user has joined on Telegram.
    After subscribing, the system will track signals from this channel
    and send notifications according to the settings.
    
    Args:
        channel_id: Telegram channel/group ID
        channel_title: Optional display name for the channel
        notify_email: Send email notifications for signals (requires Phase 2)
        notify_telegram: Forward signals to Telegram Saved Messages (requires Phase 2)
    """
    async with async_session_maker() as db:
        # Check if already subscribed
        result = await db.execute(
            select(ChannelSubscription).where(
                and_(
                    ChannelSubscription.user_id == user.id,
                    ChannelSubscription.channel_id == request.channel_id
                )
            )
        )
        existing = result.scalar_one_or_none()
        
        if existing:
            # Reactivate if was deactivated
            if not existing.is_active:
                existing.is_active = True
                existing.notify_email = request.notify_email
                existing.notify_telegram = request.notify_telegram
                await db.commit()
                await db.refresh(existing)
                
                return SubscriptionResponse(
                    success=True,
                    subscription=SubscriptionInfo(
                        id=existing.id,
                        channel_id=existing.channel_id,
                        channel_name=request.channel_title,
                        is_active=existing.is_active,
                        notify_email=existing.notify_email,
                        notify_telegram=existing.notify_telegram,
                        created_at=existing.created_at,
                    ),
                    message="Subscription reactivated",
                )
            
            return SubscriptionResponse(
                success=False,
                error="Already subscribed to this channel",
            )
        
        # Ensure channel exists in our database (create if needed)
        channel_result = await db.execute(
            select(Channel).where(Channel.id == request.channel_id)
        )
        channel = channel_result.scalar_one_or_none()
        
        if not channel and request.channel_title:
            # Create channel record
            channel = Channel(
                id=request.channel_id,
                name=request.channel_title,
                telegram_id=str(request.channel_id),
            )
            db.add(channel)
        
        # Create subscription
        subscription = ChannelSubscription(
            user_id=user.id,
            channel_id=request.channel_id,
            is_active=True,
            notify_email=request.notify_email,
            notify_telegram=request.notify_telegram,
        )
        db.add(subscription)
        await db.commit()
        await db.refresh(subscription)
        
        return SubscriptionResponse(
            success=True,
            subscription=SubscriptionInfo(
                id=subscription.id,
                channel_id=subscription.channel_id,
                channel_name=request.channel_title or (channel.name if channel else None),
                is_active=subscription.is_active,
                notify_email=subscription.notify_email,
                notify_telegram=subscription.notify_telegram,
                created_at=subscription.created_at,
            ),
            message="Successfully subscribed to channel",
        )


@router.patch("/{subscription_id}", response_model=SubscriptionResponse)
async def update_subscription(
    subscription_id: int,
    request: UpdateSubscriptionRequest,
    user = Depends(get_current_user)
):
    """
    Update subscription settings.
    
    Args:
        subscription_id: The subscription ID to update
        notify_email: Enable/disable email notifications
        notify_telegram: Enable/disable Telegram forwarding
        is_active: Enable/disable the subscription
    """
    async with async_session_maker() as db:
        result = await db.execute(
            select(ChannelSubscription).where(
                and_(
                    ChannelSubscription.id == subscription_id,
                    ChannelSubscription.user_id == user.id
                )
            )
        )
        subscription = result.scalar_one_or_none()
        
        if not subscription:
            raise HTTPException(status_code=404, detail="Subscription not found")
        
        # Update fields
        if request.notify_email is not None:
            subscription.notify_email = request.notify_email
        if request.notify_telegram is not None:
            subscription.notify_telegram = request.notify_telegram
        if request.is_active is not None:
            subscription.is_active = request.is_active
        
        await db.commit()
        await db.refresh(subscription)
        
        # Get channel name
        channel_result = await db.execute(
            select(Channel).where(Channel.id == subscription.channel_id)
        )
        channel = channel_result.scalar_one_or_none()
        
        return SubscriptionResponse(
            success=True,
            subscription=SubscriptionInfo(
                id=subscription.id,
                channel_id=subscription.channel_id,
                channel_name=channel.name if channel else None,
                is_active=subscription.is_active,
                notify_email=subscription.notify_email,
                notify_telegram=subscription.notify_telegram,
                created_at=subscription.created_at,
            ),
            message="Subscription updated",
        )


@router.delete("/{subscription_id}", response_model=SubscriptionResponse)
async def unsubscribe(
    subscription_id: int,
    user = Depends(get_current_user)
):
    """
    Unsubscribe from a channel.
    
    This deactivates the subscription. Use PATCH with is_active=false
    to temporarily pause without removing the subscription.
    """
    async with async_session_maker() as db:
        result = await db.execute(
            select(ChannelSubscription).where(
                and_(
                    ChannelSubscription.id == subscription_id,
                    ChannelSubscription.user_id == user.id
                )
            )
        )
        subscription = result.scalar_one_or_none()
        
        if not subscription:
            raise HTTPException(status_code=404, detail="Subscription not found")
        
        await db.delete(subscription)
        await db.commit()
        
        return SubscriptionResponse(
            success=True,
            message="Unsubscribed from channel",
        )


@router.delete("/channel/{channel_id}", response_model=SubscriptionResponse)
async def unsubscribe_by_channel(
    channel_id: int,
    user = Depends(get_current_user)
):
    """
    Unsubscribe from a channel by its Telegram ID.
    
    Alternative to unsubscribing by subscription_id.
    """
    async with async_session_maker() as db:
        result = await db.execute(
            select(ChannelSubscription).where(
                and_(
                    ChannelSubscription.channel_id == channel_id,
                    ChannelSubscription.user_id == user.id
                )
            )
        )
        subscription = result.scalar_one_or_none()
        
        if not subscription:
            raise HTTPException(status_code=404, detail="Subscription not found")
        
        await db.delete(subscription)
        await db.commit()
        
        return SubscriptionResponse(
            success=True,
            message="Unsubscribed from channel",
        )

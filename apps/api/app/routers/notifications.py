"""
Notifications router — in-app notification management.

Provides CRUD for user notifications with read/unread state,
badge counts, and bulk operations.
"""
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func, delete, desc
from pydantic import BaseModel

from app.database import get_session
from app.auth import get_current_user
from app.models.user import User
from app.models.notification import Notification

router = APIRouter(prefix="/notifications", tags=["notifications"])


# ---- Schemas ----

class NotificationResponse(BaseModel):
    id: int
    type: str
    title: str
    message: str
    data: Optional[dict] = None
    is_read: bool
    signal_id: Optional[int] = None
    token_symbol: Optional[str] = None
    contract_address: Optional[str] = None
    channel_name: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class NotificationListResponse(BaseModel):
    notifications: List[NotificationResponse]
    total: int
    unread_count: int


class NotificationBadge(BaseModel):
    unread_count: int


class MarkReadRequest(BaseModel):
    notification_ids: List[int]


class NotificationPreferencesRequest(BaseModel):
    email_signals: bool = True
    email_price_alerts: bool = True
    email_transfers: bool = False
    in_app_signals: bool = True
    in_app_price_alerts: bool = True
    in_app_transfers: bool = True


# ---- Routes ----

@router.get("/", response_model=NotificationListResponse)
async def get_notifications(
    limit: int = Query(50, le=100),
    offset: int = Query(0),
    unread_only: bool = Query(False),
    type: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Get paginated notifications for the current user."""
    base_query = select(Notification).where(Notification.user_id == current_user.id)

    if unread_only:
        base_query = base_query.where(Notification.is_read == False)
    if type:
        base_query = base_query.where(Notification.type == type)

    # Count total
    count_q = select(func.count()).select_from(
        base_query.subquery()
    )
    total = (await db.execute(count_q)).scalar() or 0

    # Count unread
    unread_q = select(func.count()).where(
        Notification.user_id == current_user.id,
        Notification.is_read == False,
    )
    unread_count = (await db.execute(unread_q)).scalar() or 0

    # Fetch page
    items_q = (
        base_query
        .order_by(desc(Notification.created_at))
        .offset(offset)
        .limit(limit)
    )
    result = await db.execute(items_q)
    notifications = result.scalars().all()

    return NotificationListResponse(
        notifications=notifications,
        total=total,
        unread_count=unread_count,
    )


@router.get("/badge", response_model=NotificationBadge)
async def get_notification_badge(
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Get unread notification count for badge display."""
    q = select(func.count()).where(
        Notification.user_id == current_user.id,
        Notification.is_read == False,
    )
    count = (await db.execute(q)).scalar() or 0
    return NotificationBadge(unread_count=count)


@router.post("/read", status_code=status.HTTP_200_OK)
async def mark_notifications_read(
    body: MarkReadRequest,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Mark specific notifications as read."""
    stmt = (
        update(Notification)
        .where(
            Notification.user_id == current_user.id,
            Notification.id.in_(body.notification_ids),
        )
        .values(is_read=True)
    )
    await db.execute(stmt)
    await db.commit()
    return {"success": True, "marked": len(body.notification_ids)}


@router.post("/read-all", status_code=status.HTTP_200_OK)
async def mark_all_notifications_read(
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Mark all notifications as read."""
    stmt = (
        update(Notification)
        .where(
            Notification.user_id == current_user.id,
            Notification.is_read == False,
        )
        .values(is_read=True)
    )
    result = await db.execute(stmt)
    await db.commit()
    return {"success": True, "marked": result.rowcount}


@router.delete("/{notification_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_notification(
    notification_id: int,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Delete a single notification."""
    stmt = select(Notification).where(
        Notification.id == notification_id,
        Notification.user_id == current_user.id,
    )
    result = await db.execute(stmt)
    notif = result.scalar_one_or_none()
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found")
    await db.delete(notif)
    await db.commit()


@router.delete("/", status_code=status.HTTP_200_OK)
async def clear_all_notifications(
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Clear all notifications for the current user."""
    stmt = delete(Notification).where(Notification.user_id == current_user.id)
    result = await db.execute(stmt)
    await db.commit()
    return {"success": True, "deleted": result.rowcount}

"""
Central notification service for dispatching signal alerts to subscribers.

Handles rate limiting, filtering by subscription preferences, and
parallel dispatch to email and Telegram Saved Messages.
"""
import asyncio
import logging
from typing import Dict, Any, List, Optional, Set
from datetime import datetime, timedelta
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.config import settings
from app.database import async_session_maker
from app.models.channel_subscription import ChannelSubscription
from app.models.notification import Notification
from app.models.user import User
from app.services.email_service import email_service

logger = logging.getLogger(__name__)


class NotificationService:
    """
    Central notification orchestrator.
    
    Queries subscribers for a channel, applies filters, enforces rate limits,
    and dispatches notifications via email and Telegram Saved Messages.
    """
    
    def __init__(self):
        # Rate limiting: {(user_id, channel_id): last_notification_time}
        self._rate_limit_cache: Dict[tuple, datetime] = {}
        # Track failed notifications for retry
        self._failed_queue: List[Dict[str, Any]] = []
    
    def _is_rate_limited(self, user_id: int, channel_id: int) -> bool:
        """Check if user is rate limited for this channel."""
        key = (user_id, channel_id)
        if key not in self._rate_limit_cache:
            return False
        
        last_notification = self._rate_limit_cache[key]
        cooldown = timedelta(seconds=settings.notification_rate_limit_seconds)
        
        if datetime.utcnow() - last_notification < cooldown:
            return True
        
        return False
    
    def _update_rate_limit(self, user_id: int, channel_id: int):
        """Update rate limit timestamp for user/channel pair."""
        self._rate_limit_cache[(user_id, channel_id)] = datetime.utcnow()
    
    def _passes_filters(
        self, 
        subscription: ChannelSubscription, 
        signal_data: Dict[str, Any]
    ) -> bool:
        """Check if signal passes subscription filters."""
        # Check confidence filter
        if subscription.min_confidence is not None:
            signal_confidence = signal_data.get("confidence_score", 0.5)
            # min_confidence stored as 0-100, signal_confidence as 0-1
            if signal_confidence * 100 < subscription.min_confidence:
                return False
        
        # Check sentiment filter
        if subscription.sentiment_filter:
            signal_sentiment = signal_data.get("sentiment", "NEUTRAL").upper()
            if subscription.sentiment_filter.upper() != signal_sentiment:
                return False
        
        return True
    
    def _format_telegram_message(self, signal_data: Dict[str, Any]) -> str:
        """Format signal data for Telegram Saved Messages."""
        token = signal_data.get("token_symbol", "UNKNOWN")
        token_name = signal_data.get("token_name", token)
        channel = signal_data.get("channel_name", "Unknown")
        sentiment = signal_data.get("sentiment", "NEUTRAL")
        confidence = signal_data.get("confidence_score", 0.5)
        price = signal_data.get("price_at_signal")
        target = signal_data.get("target_price")
        stop_loss = signal_data.get("stop_loss")
        message = signal_data.get("message_text", "")[:500]
        signal_type = signal_data.get("signal_type", "token_mention")
        contract_addresses = signal_data.get("contract_addresses", [])
        chain = signal_data.get("chain", "")
        
        # Labels and Emojis
        type_label = {
            "full_signal": "Signal",
            "contract_detection": "Contract Detected",
            "token_mention": "Token Mentioned",
        }.get(signal_type, "Detection")

        sentiment_emoji = {"BULLISH": "🚀", "BEARISH": "📉", "NEUTRAL": "👀"}.get(sentiment.upper(), "👀")
        
        # Build message
        lines = [
            f"<b>{sentiment_emoji} {type_label}</b>",
            "",
            f"<b>Token:</b> ${token} ({token_name})",
        ]

        if chain:
             lines.append(f"<b>Chain:</b> {chain.upper()}")

        if contract_addresses:
            for i, ca in enumerate(contract_addresses):
                lines.append(f"<b>CA:</b> <code>{ca}</code>")

        lines.extend([
            f"<b>Confidence:</b> {int(confidence * 100)}%",
            f"<b>Channel:</b> {channel}",
        ])
        
        # Only show prices if they exist (mostly for full_signals)
        if price is not None:
            lines.append(f"<b>Entry:</b> ${price:,.8f}".rstrip('0').rstrip('.'))
        if target is not None:
            lines.append(f"<b>Target:</b> ${target:,.8f}".rstrip('0').rstrip('.'))
        if stop_loss is not None:
            lines.append(f"<b>Stop Loss:</b> ${stop_loss:,.8f}".rstrip('0').rstrip('.'))
        
        if message:
            lines.extend([
                "",
                "<b>Original Message:</b>",
                f"<i>{message}</i>",
            ])
        
        # Footer
        lines.extend([
            "",
            f"<i>⚠️ DYOR. Not financial advice.</i>",
        ])
        
        return "\n".join(lines)
    
    async def notify_subscribers(
        self, 
        channel_id: int, 
        signal_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Notify all subscribers of a channel about a new signal.
        
        Args:
            channel_id: The database ID of the channel
            signal_data: Signal data dictionary
            
        Returns:
            Summary of notification results
        """
        print(f"DEBUG: notify_subscribers called for channel_id={channel_id}") # FORCE PRINT
        if not settings.notification_enabled:
            return {"skipped": True, "reason": "Notifications disabled"}
        
        results = {
            "total_subscribers": 0,
            "notified": 0,
            "rate_limited": 0,
            "filtered": 0,
            "email_sent": 0,
            "telegram_sent": 0,
            "errors": [],
        }
        
        try:
            async with async_session_maker() as session:
                # Query active subscriptions for this channel with user data
                stmt = (
                    select(ChannelSubscription)
                    .options(selectinload(ChannelSubscription.user))
                    .where(
                        ChannelSubscription.channel_id == channel_id,
                        ChannelSubscription.is_active == True,
                    )
                )
                result = await session.execute(stmt)
                subscriptions = result.scalars().all()
                
                results["total_subscribers"] = len(subscriptions)
                print(f"DEBUG: Found {len(subscriptions)} subscribers for channel {channel_id}") # FORCE PRINT
                
                if not subscriptions:
                    logger.debug(f"No subscribers for channel {channel_id}")
                    return results
                
                # Process each subscription
                tasks = []
                for sub in subscriptions:
                    user = sub.user
                    if not user or not user.is_active:
                        continue
                    
                    # Check rate limit
                    if self._is_rate_limited(user.id, channel_id):
                        results["rate_limited"] += 1
                        continue
                    
                    # Check filters
                    if not self._passes_filters(sub, signal_data):
                        results["filtered"] += 1
                        continue
                    
                    # Queue notification tasks
                    tasks.append(
                        self._notify_user(user, sub, signal_data, results)
                    )
                
                # Execute all notifications in parallel
                if tasks:
                    await asyncio.gather(*tasks, return_exceptions=True)
                
                results["notified"] = results["email_sent"] + results["telegram_sent"]
                
                logger.info(
                    f"📢 Notified {results['notified']} subscribers for channel {channel_id} "
                    f"(rate_limited={results['rate_limited']}, filtered={results['filtered']})"
                )
                
        except Exception as e:
            logger.error(f"Notification dispatch error: {e}")
            results["errors"].append(str(e))
        
        return results
    
    async def _notify_user(
        self,
        user: User,
        subscription: ChannelSubscription,
        signal_data: Dict[str, Any],
        results: Dict[str, Any],
    ):
        """Send notifications to a single user based on their preferences."""
        # Update rate limit
        self._update_rate_limit(user.id, subscription.channel_id)
        
        # Always create in-app notification
        try:
            await self._create_in_app_notification(user.id, signal_data)
            results.setdefault("in_app_sent", 0)
            results["in_app_sent"] += 1
        except Exception as e:
            results["errors"].append(f"In-app to {user.id}: {e}")
        
        # Email notification
        if subscription.notify_email and user.email:
            try:
                print(f"DEBUG: Attempting to send email to {user.email}...")
                email_result = await email_service.send_signal_notification(
                    user.email, signal_data
                )
                if email_result.get("success"):
                    print(f"DEBUG: Email success to {user.email}")
                    results["email_sent"] += 1
                else:
                    err = email_result.get('error')
                    print(f"DEBUG: Email FAILED to {user.email}: {err}")
                    logger.error(f"Email failed to {user.email}: {err}")
                    results["errors"].append(f"Email to {user.id}: {err}")
            except Exception as e:
                print(f"DEBUG: Email EXCEPTION to {user.email}: {e}")
                logger.error(f"Email exception to {user.email}: {e}")
                results["errors"].append(f"Email to {user.id}: {e}")
        else:
             print(f"DEBUG: Skipping email for user {user.id} (notify_email={subscription.notify_email}, email={user.email})")
        
        # Telegram Saved Messages notification
        if subscription.notify_telegram:
            try:
                # Import here to avoid circular imports
                from app.services.user_telegram import user_telegram_manager
                
                message = self._format_telegram_message(signal_data)
                tg_result = await user_telegram_manager.send_to_saved_messages(
                    user.id, message
                )
                if tg_result.get("success"):
                    results["telegram_sent"] += 1
                else:
                    results["errors"].append(f"Telegram to {user.id}: {tg_result.get('error')}")
            except Exception as e:
                results["errors"].append(f"Telegram to {user.id}: {e}")
    
    async def _create_in_app_notification(
        self, user_id: int, signal_data: Dict[str, Any]
    ):
        """Create a persistent in-app notification and push via WebSocket."""
        token = signal_data.get("token_symbol", "UNKNOWN")
        sentiment = signal_data.get("sentiment", "NEUTRAL")
        channel = signal_data.get("channel_name", "Unknown")
        confidence = signal_data.get("confidence_score", 0.5)
        price = signal_data.get("price_at_signal")
        contract_addresses = signal_data.get("contract_addresses", [])
        chain = signal_data.get("chain")
        signal_type = signal_data.get("signal_type", "token_mention")
        
        type_label = {
            "full_signal": "Signal",
            "contract_detection": "Contract Detected",
            "token_mention": "Mention",
        }.get(signal_type, "Detection")
        
        sentiment_emoji = {"BULLISH": "🚀", "BEARISH": "📉", "NEUTRAL": "👀"}.get(
            sentiment.upper(), "👀"
        )
        
        # Title: "👀 Contract Detected: PEPE (ETH)"
        chain_label = f" ({chain.upper()})" if chain else ""
        title = f"{sentiment_emoji} {type_label}: {token}{chain_label}"
        
        # Message body: "From Channel X — CA: 0x123...abc"
        parts = [f"From {channel}"]
        
        if contract_addresses:
            ca = contract_addresses[0]
            short_ca = f"{ca[:6]}...{ca[-4:]}"
            parts.append(f"CA: {short_ca}")
            
        if price is not None:
             parts.append(f"Price: ${price:,.8f}".rstrip("0").rstrip("."))

        if confidence > 0.8:
            parts.append(f"{int(confidence * 100)}% Conf")
        
        message = " · ".join(parts)
        
        notif_data = {
            "token_symbol": token,
            "token_name": signal_data.get("token_name", token),
            "sentiment": sentiment,
            "price": price,
            "confidence": confidence,
            "channel": channel,
            "contract_addresses": contract_addresses,
            "chain": chain,
            "signal_type": signal_type,
            "target_price": signal_data.get("target_price"),
            "stop_loss": signal_data.get("stop_loss"),
        }
        
        try:
            async with async_session_maker() as session:
                notif = Notification(
                    user_id=user_id,
                    type="signal",
                    title=title,
                    message=message,
                    data=notif_data,
                    token_symbol=token,
                    contract_address=contract_addresses[0] if contract_addresses else None,
                    channel_name=channel,
                )
                session.add(notif)
                await session.commit()
                await session.refresh(notif)
                
                # Fetch user to get email
                u_stmt = select(User).where(User.id == user_id)
                u_res = await session.execute(u_stmt)
                user = u_res.scalar_one_or_none()
                
                # Push via WebSocket
                from app.services.websocket_manager import manager
                await manager.send_to_user(user_id, {
                    "type": "notification",
                    "data": notif.to_dict(),
                    "timestamp": notif.created_at.isoformat(),
                })
                
                # FORCE EMAIL if user has email (User requested: "let it trigger an email there")
                if user and user.email:
                    print(f"DEBUG: Forcing email from _create_in_app_notification to {user.email}")
                    asyncio.create_task(
                        email_service.send_signal_notification(user.email, signal_data)
                    )
                else:
                    print(f"DEBUG: No email found for user {user_id} in _create_in_app_notification")
                    
        except Exception as e:
            logger.error(f"Failed to create in-app notification for user {user_id}: {e}")
    
    async def create_tracking_notification(
        self,
        user_id: int,
        notif_type: str,
        title: str,
        message: str,
        data: Optional[Dict[str, Any]] = None,
        token_symbol: Optional[str] = None,
        contract_address: Optional[str] = None,
    ):
        """Create a custom in-app notification (for price alerts, transfers, etc.) AND email."""
        try:
            # 1. Create In-App Notification
            async with async_session_maker() as session:
                notif = Notification(
                    user_id=user_id,
                    type=notif_type,
                    title=title,
                    message=message,
                    data=data,
                    token_symbol=token_symbol,
                    contract_address=contract_address,
                )
                session.add(notif)
                await session.commit()
                await session.refresh(notif)
                
                # Fetch user email for step 2
                u_stmt = select(User).where(User.id == user_id)
                u_res = await session.execute(u_stmt)
                user = u_res.scalar_one_or_none()
                
                # Push via WebSocket
                from app.services.websocket_manager import manager
                await manager.send_to_user(user_id, {
                    "type": "notification",
                    "data": notif.to_dict(),
                    "timestamp": notif.created_at.isoformat(),
                })
                
                # 2. Send Email (if user exists and has email)
                if user and user.email:
                    # Async dispatch to avoid blocking
                    print(f"DEBUG: Triggering email for tracking notification to {user.email}")
                    asyncio.create_task(
                        email_service.send_general_notification(
                            to_email=user.email,
                            title=title,
                            message_body=message,
                            data=data
                        )
                    )
                else:
                    print(f"DEBUG: Skipping tracking email for user {user_id} (email={getattr(user, 'email', 'None')})")
                
                return notif
        except Exception as e:
            logger.error(f"Failed to create tracking notification for user {user_id}: {e}")
            return None
    
    def clear_rate_limits(self):
        """Clear all rate limits (for testing)."""
        self._rate_limit_cache.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get notification service statistics."""
        return {
            "rate_limit_entries": len(self._rate_limit_cache),
            "failed_queue_size": len(self._failed_queue),
            "email_available": email_service.is_available,
            "notifications_enabled": settings.notification_enabled,
            "rate_limit_seconds": settings.notification_rate_limit_seconds,
        }


# Global service instance
notification_service = NotificationService()

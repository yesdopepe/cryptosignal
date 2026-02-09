"""ChannelSubscription model for user-channel relationships."""
from datetime import datetime
from typing import Optional, TYPE_CHECKING
from sqlalchemy import Integer, Boolean, DateTime, ForeignKey, UniqueConstraint, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.channel import Channel


class ChannelSubscription(Base):
    """Model representing a user's subscription to a channel."""
    
    __tablename__ = "channel_subscriptions"
    
    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # Foreign keys
    user_id: Mapped[int] = mapped_column(
        Integer, 
        ForeignKey("users.id", ondelete="CASCADE"), 
        nullable=False,
        index=True,
    )
    channel_id: Mapped[int] = mapped_column(
        Integer, 
        ForeignKey("channels.id", ondelete="CASCADE"), 
        nullable=False,
        index=True,
    )
    
    # Subscription settings
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Notification preferences
    notify_email: Mapped[bool] = mapped_column(Boolean, default=False)
    notify_telegram: Mapped[bool] = mapped_column(Boolean, default=True)  # Send to Saved Messages
    
    # Optional filters
    min_confidence: Mapped[Optional[float]] = mapped_column(Integer, nullable=True)  # 0-100
    sentiment_filter: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # BULLISH, BEARISH, NEUTRAL, or null for all
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, 
        nullable=False, 
        default=datetime.utcnow,
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, 
        nullable=True,
        onupdate=datetime.utcnow,
    )
    
    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="channel_subscriptions")
    channel: Mapped["Channel"] = relationship("Channel")
    
    # Constraints
    __table_args__ = (
        UniqueConstraint("user_id", "channel_id", name="uq_user_channel_subscription"),
    )
    
    def __repr__(self) -> str:
        return f"<ChannelSubscription(id={self.id}, user_id={self.user_id}, channel_id={self.channel_id})>"
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "channel_id": self.channel_id,
            "is_active": self.is_active,
            "notify_email": self.notify_email,
            "notify_telegram": self.notify_telegram,
            "min_confidence": self.min_confidence,
            "sentiment_filter": self.sentiment_filter,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "channel": self.channel.to_dict() if self.channel else None,
        }

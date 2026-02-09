"""In-app notification model for persistent user notifications."""
from datetime import datetime
from typing import Optional, TYPE_CHECKING
from sqlalchemy import (
    Integer,
    String,
    Float,
    Text,
    Boolean,
    DateTime,
    ForeignKey,
    JSON,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User


class Notification(Base):
    """Persistent in-app notification for a user."""

    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Notification metadata
    type: Mapped[str] = mapped_column(
        String(50), nullable=False, default="signal", index=True
    )  # signal, price_alert, transfer, system, tracking

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Optional structured data for rich rendering
    data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Read state
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    # Link to related entities
    signal_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    token_symbol: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    contract_address: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    channel_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, index=True
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="notifications")

    __table_args__ = (
        Index("idx_notif_user_read", "user_id", "is_read"),
        Index("idx_notif_user_created", "user_id", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<Notification(id={self.id}, user_id={self.user_id}, type={self.type})>"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "type": self.type,
            "title": self.title,
            "message": self.message,
            "data": self.data,
            "is_read": self.is_read,
            "signal_id": self.signal_id,
            "token_symbol": self.token_symbol,
            "contract_address": self.contract_address,
            "channel_name": self.channel_name,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

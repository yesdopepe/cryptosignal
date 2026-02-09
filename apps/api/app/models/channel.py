"""Channel model for storing Telegram channel information."""
from datetime import datetime
from typing import Optional, List, TYPE_CHECKING
from sqlalchemy import Integer, String, Text, Float, Boolean, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.signal import Signal


class Channel(Base):
    """Model representing a monitored Telegram channel."""
    
    __tablename__ = "channels"
    
    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # Channel identification
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    telegram_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Statistics
    subscriber_count: Mapped[int] = mapped_column(Integer, default=0)
    success_rate: Mapped[float] = mapped_column(Float, default=0.0)
    total_signals: Mapped[int] = mapped_column(Integer, default=0)
    avg_roi: Mapped[float] = mapped_column(Float, default=0.0)
    
    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    
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
    signals: Mapped[List["Signal"]] = relationship(
        "Signal", 
        back_populates="channel",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )
    
    # Indexes
    __table_args__ = (
        Index("idx_channel_success_rate", "success_rate"),
        Index("idx_channel_total_signals", "total_signals"),
    )
    
    def __repr__(self) -> str:
        return f"<Channel(id={self.id}, name={self.name}, signals={self.total_signals})>"
    
    def to_dict(self) -> dict:
        """Convert channel to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "telegram_id": self.telegram_id,
            "description": self.description,
            "subscriber_count": self.subscriber_count,
            "success_rate": self.success_rate,
            "total_signals": self.total_signals,
            "avg_roi": self.avg_roi,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

"""TelegramSession model for storing per-user Telegram session data."""
from datetime import datetime
from typing import Optional, TYPE_CHECKING
from sqlalchemy import Integer, String, Boolean, DateTime, ForeignKey, LargeBinary, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User


class TelegramSession(Base):
    """Model representing a user's Telegram session."""
    
    __tablename__ = "telegram_sessions"
    
    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # Foreign key to user
    user_id: Mapped[int] = mapped_column(
        Integer, 
        ForeignKey("users.id", ondelete="CASCADE"), 
        unique=True, 
        nullable=False,
        index=True,
    )
    
    # Telegram identification
    phone_number: Mapped[str] = mapped_column(String(20), nullable=False)
    telegram_user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    telegram_username: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    # Session data (encrypted Telethon session)
    session_data: Mapped[Optional[bytes]] = mapped_column(LargeBinary, nullable=True)
    
    # Auth state
    is_authenticated: Mapped[bool] = mapped_column(Boolean, default=False)
    auth_state: Mapped[str] = mapped_column(
        String(50), 
        default="disconnected",  # disconnected, awaiting_code, awaiting_2fa, authenticated
    )
    phone_code_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
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
    last_connected: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Relationship
    user: Mapped["User"] = relationship("User", back_populates="telegram_session")
    
    def __repr__(self) -> str:
        return f"<TelegramSession(id={self.id}, user_id={self.user_id}, phone={self.phone_number}, auth={self.is_authenticated})>"
    
    def to_dict(self) -> dict:
        """Convert to dictionary (excluding sensitive session data)."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "phone_number": self.phone_number[:4] + "****" + self.phone_number[-2:] if self.phone_number else None,
            "telegram_username": self.telegram_username,
            "is_authenticated": self.is_authenticated,
            "auth_state": self.auth_state,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_connected": self.last_connected.isoformat() if self.last_connected else None,
        }

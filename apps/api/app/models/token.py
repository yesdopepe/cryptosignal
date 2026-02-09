"""Token model for storing cryptocurrency token statistics."""
from datetime import datetime
from typing import Optional
from sqlalchemy import Integer, String, Float, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Token(Base):
    """Model representing aggregated statistics for a cryptocurrency token."""
    
    __tablename__ = "tokens"
    
    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # Token identification
    symbol: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    
    # Statistics
    total_signals: Mapped[int] = mapped_column(Integer, default=0)
    success_rate: Mapped[float] = mapped_column(Float, default=0.0)
    avg_roi: Mapped[float] = mapped_column(Float, default=0.0)
    
    # Price tracking
    current_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    price_change_24h: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    # Timestamps
    last_signal_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
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
    
    # Indexes
    __table_args__ = (
        Index("idx_token_total_signals", "total_signals"),
        Index("idx_token_success_rate", "success_rate"),
        Index("idx_token_last_signal", "last_signal_at"),
    )
    
    def __repr__(self) -> str:
        return f"<Token(symbol={self.symbol}, signals={self.total_signals})>"
    
    def to_dict(self) -> dict:
        """Convert token to dictionary."""
        return {
            "id": self.id,
            "symbol": self.symbol,
            "name": self.name,
            "total_signals": self.total_signals,
            "success_rate": self.success_rate,
            "avg_roi": self.avg_roi,
            "current_price": self.current_price,
            "price_change_24h": self.price_change_24h,
            "last_signal_at": self.last_signal_at.isoformat() if self.last_signal_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

"""Signal model for storing crypto trading signals."""
from datetime import datetime
from typing import Optional, List
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


class Signal(Base):
    """Model representing a crypto trading signal from a Telegram channel."""
    
    __tablename__ = "signals"
    
    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # Channel reference
    channel_id: Mapped[int] = mapped_column(
        Integer, 
        ForeignKey("channels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    channel_name: Mapped[str] = mapped_column(String(255), nullable=False)
    
    # Token information
    token_symbol: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    token_name: Mapped[str] = mapped_column(String(255), nullable=False)
    
    # Price data (optional — contract detections may not have a price)
    price_at_signal: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    current_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    # Signal classification
    signal_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="token_mention",
        index=True,
    )  # full_signal | contract_detection | token_mention
    
    # On-chain data
    contract_addresses: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True, default=list)
    chain: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    
    # Signal analysis
    sentiment: Mapped[str] = mapped_column(
        String(20), 
        nullable=False, 
        default="NEUTRAL",
        index=True,
    )  # BULLISH, BEARISH, NEUTRAL
    
    message_text: Mapped[str] = mapped_column(Text, nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    
    # Timestamps
    timestamp: Mapped[datetime] = mapped_column(
        DateTime, 
        nullable=False, 
        default=datetime.utcnow,
        index=True,
    )
    
    # Performance tracking
    success: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    roi_percent: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    # Tags for categorization
    tags: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True, default=list)
    
    # Relationships
    channel: Mapped["Channel"] = relationship("Channel", back_populates="signals")
    
    # Indexes for performance
    __table_args__ = (
        Index("idx_signal_timestamp_channel", "timestamp", "channel_id"),
        Index("idx_signal_token_timestamp", "token_symbol", "timestamp"),
        Index("idx_signal_sentiment_timestamp", "sentiment", "timestamp"),
    )
    
    def __repr__(self) -> str:
        return f"<Signal(id={self.id}, token={self.token_symbol}, sentiment={self.sentiment})>"
    
    def to_dict(self) -> dict:
        """Convert signal to dictionary."""
        return {
            "id": self.id,
            "channel_id": self.channel_id,
            "channel_name": self.channel_name,
            "token_symbol": self.token_symbol,
            "token_name": self.token_name,
            "price_at_signal": self.price_at_signal,
            "current_price": self.current_price,
            "signal_type": self.signal_type,
            "contract_addresses": self.contract_addresses or [],
            "chain": self.chain,
            "sentiment": self.sentiment,
            "message_text": self.message_text,
            "confidence_score": self.confidence_score,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "success": self.success,
            "roi_percent": self.roi_percent,
            "tags": self.tags or [],
        }

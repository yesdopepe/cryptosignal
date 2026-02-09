"""Channel schemas for request/response validation."""
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class ChannelBase(BaseModel):
    """Base channel schema with common fields."""
    
    name: str = Field(..., min_length=1, max_length=255, description="Channel name")
    telegram_id: str = Field(..., min_length=1, max_length=100, description="Telegram channel ID")
    description: Optional[str] = Field(default=None, description="Channel description")


class ChannelCreate(ChannelBase):
    """Schema for creating a new channel."""
    
    subscriber_count: int = Field(default=0, ge=0, description="Number of subscribers")
    is_active: bool = Field(default=True, description="Whether channel is active")


class ChannelUpdate(BaseModel):
    """Schema for updating an existing channel."""
    
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = None
    subscriber_count: Optional[int] = Field(default=None, ge=0)
    is_active: Optional[bool] = None


class ChannelResponse(BaseModel):
    """Schema for channel response."""
    
    id: int
    name: str
    telegram_id: str
    description: Optional[str]
    subscriber_count: int
    success_rate: float
    total_signals: int
    avg_roi: float
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime]
    
    class Config:
        from_attributes = True


class ChannelListResponse(BaseModel):
    """Schema for paginated channel list response."""
    
    items: List[ChannelResponse]
    total: int
    limit: int
    offset: int
    has_more: bool
    
    class Config:
        from_attributes = True


class ChannelStats(BaseModel):
    """Schema for detailed channel statistics."""
    
    id: int
    name: str
    total_signals: int
    successful_signals: int
    failed_signals: int
    success_rate: float
    avg_roi: float
    best_roi: float
    worst_roi: float
    total_bullish: int
    total_bearish: int
    total_neutral: int
    most_signaled_token: str
    avg_confidence: float
    signals_last_24h: int
    signals_last_7d: int
    signals_last_30d: int
    
    class Config:
        from_attributes = True

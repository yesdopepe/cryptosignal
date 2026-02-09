"""Token schemas for request/response validation."""
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


class TokenBase(BaseModel):
    """Base token schema with common fields."""
    
    symbol: str = Field(..., min_length=1, max_length=20, description="Token symbol")
    name: str = Field(..., min_length=1, max_length=255, description="Token name")
    
    @field_validator("symbol")
    @classmethod
    def validate_symbol(cls, v: str) -> str:
        return v.upper()


class TokenCreate(TokenBase):
    """Schema for creating a new token."""
    
    current_price: Optional[float] = Field(default=None, ge=0)


class TokenUpdate(BaseModel):
    """Schema for updating an existing token."""
    
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    current_price: Optional[float] = Field(default=None, ge=0)
    price_change_24h: Optional[float] = None


class TokenResponse(BaseModel):
    """Schema for token response."""
    
    id: int
    symbol: str
    name: str
    total_signals: int
    success_rate: float
    avg_roi: float
    current_price: Optional[float]
    price_change_24h: Optional[float]
    last_signal_at: Optional[datetime]
    created_at: datetime
    updated_at: Optional[datetime]
    
    class Config:
        from_attributes = True


class TokenListResponse(BaseModel):
    """Schema for paginated token list response."""
    
    items: List[TokenResponse]
    total: int
    limit: int
    offset: int
    has_more: bool
    
    class Config:
        from_attributes = True


class TokenStats(BaseModel):
    """Schema for detailed token statistics."""
    
    symbol: str
    name: str
    total_signals: int
    successful_signals: int
    failed_signals: int
    success_rate: float
    avg_roi: float
    median_roi: float
    best_roi: float
    worst_roi: float
    total_bullish: int
    total_bearish: int
    total_neutral: int
    avg_confidence: float
    signals_last_24h: int
    signals_last_7d: int
    signals_last_30d: int
    top_channel: str
    sentiment_score: float  # -1 to 1 scale
    
    class Config:
        from_attributes = True

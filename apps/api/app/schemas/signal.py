"""Signal schemas for request/response validation."""
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


class SignalBase(BaseModel):
    """Base signal schema with common fields."""
    
    token_symbol: str = Field(..., min_length=1, max_length=50, description="Token symbol (e.g., BTC)")
    token_name: str = Field(..., min_length=1, max_length=255, description="Token name")
    price_at_signal: Optional[float] = Field(default=None, ge=0, description="Price at time of signal (optional for detections)")
    signal_type: str = Field(default="token_mention", description="full_signal | contract_detection | token_mention")
    contract_addresses: Optional[List[str]] = Field(default=[], description="Detected contract addresses")
    chain: Optional[str] = Field(default=None, max_length=30, description="Blockchain network")
    sentiment: str = Field(default="NEUTRAL", description="Signal sentiment")
    message_text: str = Field(..., min_length=1, description="Original message text")
    confidence_score: float = Field(default=0.5, ge=0, le=1, description="Confidence score 0-1")
    tags: Optional[List[str]] = Field(default=[], description="Tags for categorization")
    
    @field_validator("sentiment")
    @classmethod
    def validate_sentiment(cls, v: str) -> str:
        valid_sentiments = ["BULLISH", "BEARISH", "NEUTRAL"]
        v_upper = v.upper()
        if v_upper not in valid_sentiments:
            raise ValueError(f"Sentiment must be one of: {valid_sentiments}")
        return v_upper
    
    @field_validator("token_symbol")
    @classmethod
    def validate_symbol(cls, v: str) -> str:
        return v.upper()


class SignalCreate(SignalBase):
    """Schema for creating a new signal."""
    
    channel_id: int = Field(..., gt=0, description="Channel ID")
    channel_name: str = Field(..., min_length=1, description="Channel name")
    current_price: Optional[float] = Field(default=None, ge=0, description="Current token price")
    success: Optional[bool] = Field(default=None, description="Whether signal was successful")
    roi_percent: Optional[float] = Field(default=None, description="ROI percentage")


class SignalUpdate(BaseModel):
    """Schema for updating an existing signal."""
    
    current_price: Optional[float] = Field(default=None, ge=0)
    sentiment: Optional[str] = None
    confidence_score: Optional[float] = Field(default=None, ge=0, le=1)
    success: Optional[bool] = None
    roi_percent: Optional[float] = None
    tags: Optional[List[str]] = None
    
    @field_validator("sentiment")
    @classmethod
    def validate_sentiment(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        valid_sentiments = ["BULLISH", "BEARISH", "NEUTRAL"]
        v_upper = v.upper()
        if v_upper not in valid_sentiments:
            raise ValueError(f"Sentiment must be one of: {valid_sentiments}")
        return v_upper


class SignalResponse(BaseModel):
    """Schema for signal response."""
    
    id: int
    channel_id: int
    channel_name: str
    token_symbol: str
    token_name: str
    price_at_signal: Optional[float] = None
    current_price: Optional[float] = None
    signal_type: str = "token_mention"
    contract_addresses: Optional[List[str]] = []
    chain: Optional[str] = None
    sentiment: str
    message_text: str
    confidence_score: float
    timestamp: datetime
    success: Optional[bool] = None
    roi_percent: Optional[float] = None
    tags: List[str]
    
    class Config:
        from_attributes = True


class SignalListResponse(BaseModel):
    """Schema for paginated signal list response."""
    
    items: List[SignalResponse]
    total: int
    limit: int
    offset: int
    has_more: bool
    
    class Config:
        from_attributes = True


class SignalFilter(BaseModel):
    """Schema for filtering signals."""
    
    channel_id: Optional[int] = None
    token_symbol: Optional[str] = None
    sentiment: Optional[str] = None
    success: Optional[bool] = None
    min_confidence: Optional[float] = Field(default=None, ge=0, le=1)
    max_confidence: Optional[float] = Field(default=None, ge=0, le=1)
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None

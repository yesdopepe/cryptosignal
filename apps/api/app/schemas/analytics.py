"""Analytics schemas for response validation."""
from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class HistoricalSignal(BaseModel):
    """Simplified signal for historical data response."""
    
    id: int
    channel_name: str
    token_symbol: str
    sentiment: str
    price_at_signal: float
    roi_percent: Optional[float]
    success: Optional[bool]
    timestamp: datetime
    confidence_score: float


class HistoricalDataResponse(BaseModel):
    """Schema for historical data analytics response."""
    
    signals: List[HistoricalSignal]
    total_count: int
    date_range: Dict[str, str]
    summary: Dict[str, Any]
    query_time_ms: float
    cached: bool
    
    class Config:
        from_attributes = True


class TokenStatsResponse(BaseModel):
    """Schema for token statistics response."""
    
    symbol: str
    name: str
    total_signals: int
    success_rate: float
    avg_roi: float
    median_roi: float
    volatility: float
    sentiment_distribution: Dict[str, int]
    roi_distribution: Dict[str, int]  # Bucketed ROI ranges
    signals_by_channel: Dict[str, int]
    performance_trend: List[Dict[str, Any]]  # Daily/weekly performance
    query_time_ms: float
    cached: bool
    
    class Config:
        from_attributes = True


class ChannelLeaderboardEntry(BaseModel):
    """Single entry in channel leaderboard."""
    
    rank: int
    channel_id: int
    channel_name: str
    total_signals: int
    success_rate: float
    avg_roi: float
    score: float  # Composite score
    win_streak: int
    top_token: str


class ChannelLeaderboardResponse(BaseModel):
    """Schema for channel leaderboard response."""
    
    leaderboard: List[ChannelLeaderboardEntry]
    total_channels: int
    total_signals_analyzed: int
    time_period: str
    query_time_ms: float
    cached: bool
    
    class Config:
        from_attributes = True


class PatternInfo(BaseModel):
    """Information about a detected pattern."""
    
    pattern_type: str  # e.g., "bullish_momentum", "accumulation", "distribution"
    description: str
    confidence: float
    tokens_affected: List[str]
    start_date: datetime
    detected_at: datetime
    supporting_signals: int


class PatternAnalysisResponse(BaseModel):
    """Schema for pattern analysis response."""
    
    patterns: List[PatternInfo]
    market_phase: str  # bull, bear, sideways
    dominant_sentiment: str
    sentiment_strength: float
    volume_trend: str
    signals_analyzed: int
    time_period_days: int
    query_time_ms: float
    cached: bool
    
    class Config:
        from_attributes = True


class TrendingToken(BaseModel):
    """Schema for trending token information."""
    
    rank: int
    symbol: str
    name: str
    signal_count_24h: int
    signal_change_percent: float  # vs previous 24h
    dominant_sentiment: str
    avg_roi_24h: float
    momentum_score: float


class TrendingResponse(BaseModel):
    """Schema for trending tokens response."""
    
    trending: List[TrendingToken]
    total_signals_24h: int
    most_active_channels: List[str]
    timestamp: datetime
    
    class Config:
        from_attributes = True


class MarketSentiment(BaseModel):
    """Schema for overall market sentiment."""
    
    overall_sentiment: str  # BULLISH, BEARISH, NEUTRAL
    sentiment_score: float  # -1 to 1
    bullish_percent: float
    bearish_percent: float
    neutral_percent: float
    fear_greed_index: int  # 0-100
    signals_analyzed: int
    time_period_hours: int
    top_bullish_tokens: List[str]
    top_bearish_tokens: List[str]
    timestamp: datetime
    
    class Config:
        from_attributes = True

"""Pydantic schemas package."""
from app.schemas.signal import (
    SignalCreate,
    SignalUpdate,
    SignalResponse,
    SignalListResponse,
)
from app.schemas.channel import (
    ChannelCreate,
    ChannelUpdate,
    ChannelResponse,
    ChannelListResponse,
    ChannelStats,
)
from app.schemas.token import (
    TokenCreate,
    TokenResponse,
    TokenListResponse,
    TokenStats,
)
from app.schemas.analytics import (
    HistoricalDataResponse,
    TokenStatsResponse,
    ChannelLeaderboardResponse,
    PatternAnalysisResponse,
    TrendingToken,
    MarketSentiment,
)
from app.schemas.common import (
    PaginationParams,
    PaginatedResponse,
    SuccessResponse,
    ErrorResponse,
)

__all__ = [
    # Signal
    "SignalCreate",
    "SignalUpdate",
    "SignalResponse",
    "SignalListResponse",
    # Channel
    "ChannelCreate",
    "ChannelUpdate",
    "ChannelResponse",
    "ChannelListResponse",
    "ChannelStats",
    # Token
    "TokenCreate",
    "TokenResponse",
    "TokenListResponse",
    "TokenStats",
    # Analytics
    "HistoricalDataResponse",
    "TokenStatsResponse",
    "ChannelLeaderboardResponse",
    "PatternAnalysisResponse",
    "TrendingToken",
    "MarketSentiment",
    # Common
    "PaginationParams",
    "PaginatedResponse",
    "SuccessResponse",
    "ErrorResponse",
]

"""Common schemas used across the application."""
from typing import Any, Generic, List, Optional, TypeVar
from pydantic import BaseModel, Field


T = TypeVar("T")


class PaginationParams(BaseModel):
    """Pagination parameters for list endpoints."""
    
    limit: int = Field(default=50, ge=1, le=10000, description="Maximum number of records to return")
    offset: int = Field(default=0, ge=0, description="Number of records to skip")


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response wrapper."""
    
    items: List[T]
    total: int
    limit: int
    offset: int
    has_more: bool
    
    class Config:
        from_attributes = True


class SuccessResponse(BaseModel):
    """Generic success response."""
    
    success: bool = True
    message: str = "Operation completed successfully"
    data: Optional[Any] = None


class ErrorResponse(BaseModel):
    """Generic error response."""
    
    success: bool = False
    error: str
    detail: Optional[str] = None
    code: Optional[str] = None


class CacheInfo(BaseModel):
    """Cache information for response headers."""
    
    status: str = Field(description="Cache status: HIT or MISS")
    key: str = Field(description="Cache key used")
    ttl: Optional[int] = Field(default=None, description="Time to live in seconds")

"""Redis cache configuration and utilities."""
import hashlib
import json
from typing import Optional, Callable
from fastapi import Request, Response
from fastapi_cache import FastAPICache
from fastapi_cache.backends.redis import RedisBackend
from fastapi_cache.decorator import cache
from redis import asyncio as aioredis

from app.config import settings


# Global redis client reference
redis_client: Optional[aioredis.Redis] = None


def custom_key_builder(
    func: Callable,
    namespace: str = "",
    request: Request = None,
    response: Response = None,
    args: tuple = None,
    kwargs: dict = None,
) -> str:
    """Build custom cache key including query parameters."""
    prefix = f"{FastAPICache.get_prefix()}:{namespace}:{func.__module__}:{func.__name__}"
    
    # Include path parameters
    if kwargs:
        sorted_kwargs = sorted(kwargs.items())
        kwargs_str = json.dumps(sorted_kwargs, sort_keys=True, default=str)
        kwargs_hash = hashlib.md5(kwargs_str.encode()).hexdigest()[:8]
        prefix = f"{prefix}:{kwargs_hash}"
    
    # Include query parameters
    if request and request.query_params:
        query_str = str(sorted(request.query_params.items()))
        query_hash = hashlib.md5(query_str.encode()).hexdigest()[:8]
        prefix = f"{prefix}:q:{query_hash}"
    
    return prefix


async def init_cache():
    """Initialize Redis cache."""
    global redis_client
    
    if not settings.cache_enabled:
        # Use in-memory backend if cache is disabled
        from fastapi_cache.backends.inmemory import InMemoryBackend
        FastAPICache.init(InMemoryBackend(), prefix="crypto-signals")
        return
    
    try:
        redis_client = aioredis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=False,
        )
        
        # Test connection
        await redis_client.ping()
        
        FastAPICache.init(
            RedisBackend(redis_client),
            prefix="crypto-signals",
            key_builder=custom_key_builder,
        )
        print(f"✅ Redis cache initialized: {settings.redis_url}")
    except Exception as e:
        print(f"⚠️ Redis connection failed: {e}. Using in-memory cache.")
        from fastapi_cache.backends.inmemory import InMemoryBackend
        FastAPICache.init(InMemoryBackend(), prefix="crypto-signals")


async def close_cache():
    """Close Redis connection."""
    global redis_client
    if redis_client:
        await redis_client.close()
        redis_client = None


async def clear_cache(pattern: str = "*"):
    """Clear cache entries matching pattern."""
    global redis_client
    if redis_client:
        prefix = FastAPICache.get_prefix()
        full_pattern = f"{prefix}:{pattern}"
        async for key in redis_client.scan_iter(match=full_pattern):
            await redis_client.delete(key)


class CacheStatus:
    """Utility class to track cache status for headers."""
    
    @staticmethod
    async def check_cached(key: str) -> bool:
        """Check if a key exists in cache."""
        global redis_client
        if redis_client:
            return await redis_client.exists(key)
        return False


# Re-export cache decorator for convenience
__all__ = ["cache", "init_cache", "close_cache", "clear_cache", "custom_key_builder"]

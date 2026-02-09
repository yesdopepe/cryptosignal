"""Live data API router with WebSocket support and caching."""
import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, Request, Response, Query, HTTPException
from fastapi_cache.decorator import cache
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session, async_session_maker
from app.services.analytics_service import AnalyticsService
from app.auth import verify_websocket_token
from app.services.websocket_manager import manager
from app.cache import custom_key_builder

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/live", tags=["Live"])


# Allowed origins for WebSocket connections
ALLOWED_WS_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:8000",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:8000",
    None,  # Allow connections without origin (e.g., from scripts)
]


@router.get("/market")
@cache(expire=60, key_builder=custom_key_builder)
async def get_market_data(
    request: Request,
    response: Response,
    limit: int = Query(default=50, ge=1, le=100),
):
    """
    Get real-time market data for top cryptocurrencies.

    Returns top coins by market cap with prices, 24h change,
    volume, market cap, logos, and 7-day sparkline data.

    No authentication required. Data from CoinGecko free API.
    """
    from app.services.market_service import market_service

    coins = await market_service.get_top_coins(per_page=limit)
    global_stats = await market_service.get_global_stats()

    return {
        "coins": coins,
        "global": global_stats,
        "count": len(coins),
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/trending")
@cache(expire=60, key_builder=custom_key_builder)  # 1 minute cache
async def get_trending_tokens(
    request: Request,
    response: Response,
    hours: int = 24,
    session: AsyncSession = Depends(get_session),
):
    """
    Get trending tokens — combines CoinGecko market trending
    with signal-based trending from Telegram channels.
    """
    from app.services.market_service import market_service

    # 1) CoinGecko trending (real market data with prices)
    market_trending = await market_service.get_trending_coins()

    # 2) Signal-based trending (from DB)
    analytics = AnalyticsService(session)
    signal_result = await analytics.get_trending_tokens(hours=hours)
    signal_trending = signal_result.get("trending", [])

    return {
        "trending": market_trending,
        "signal_trending": signal_trending,
        "total_signals_24h": signal_result.get("total_signals_24h", 0),
        "most_active_channels": signal_result.get("most_active_channels", []),
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/ohlc/{symbol}")
@cache(expire=300, key_builder=custom_key_builder)  # 5 minute cache
async def get_ohlc_data(
    request: Request,
    response: Response,
    symbol: str,
    days: str = Query(default="7"),
):
    """
    Get OHLC candlestick data for any token symbol.

    Uses CoinGecko free API — resolves symbol → CoinGecko ID automatically.
    Supports any coin listed on CoinGecko, not just top 50.

    - days=1  → 30-min candles (~48 candles)
    - days=7-30 → 4-hour candles
    - days=31+ → 4-day candles (CoinGecko behavior)

    No authentication required.

    NOTE: Only successful (non-empty) responses are cached.
    Errors raise HTTPException which bypasses the @cache decorator,
    allowing immediate retries.
    """
    from app.services.coingecko_service import coingecko_service
    
    # Handle 'max' or numeric days
    # Note: CoinGecko Free Tier now limits OHLC to 365 days max.
    if days == "max":
        days_param = 365
    else:
        try:
            # allow any number of days up to 365
            d = int(days)
            if d < 1: d = 1
            if d > 365: d = 365 # Cap at 365 for free tier
            days_param = d
        except ValueError:
            days_param = 7

    try:
        candles = await coingecko_service.get_ohlc(symbol, days=days_param)
    except Exception as e:
        logger.warning(f"OHLC fetch failed for {symbol}: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"Chart data temporarily unavailable for {symbol.upper()}. Try again shortly.",
        )

    if not candles:
        raise HTTPException(
            status_code=404,
            detail=f"No chart data found for {symbol.upper()}. Token may not be listed on CoinGecko.",
        )

    return {
        "symbol": symbol.upper(),
        "candles": candles,
        "days": days_param,
        "count": len(candles),
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/sentiment")
@cache(expire=30, key_builder=custom_key_builder)  # 30 second cache
async def get_market_sentiment(
    request: Request,
    response: Response,
    hours: int = 24,
    session: AsyncSession = Depends(get_session),
):
    """
    Get overall market sentiment analysis.
    
    - **hours**: Time window in hours (default: 24)
    
    Returns:
    - Overall sentiment (BULLISH, BEARISH, NEUTRAL)
    - Sentiment score (-1 to 1 scale)
    - Sentiment percentages
    - Fear & Greed Index (0-100)
    - Top bullish and bearish tokens
    """
    analytics = AnalyticsService(session)
    result = await analytics.get_market_sentiment(hours=hours)
    return result


@router.get("/stats")
@cache(expire=15, key_builder=custom_key_builder)  # 15 second cache
async def get_live_stats(
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_session),
):
    """
    Get real-time platform statistics.

    Returns fields matching frontend StatsCards expectations.
    """
    from sqlalchemy import select, func
    from app.models import Signal, Channel, Token
    from app.models.tracked_token import TrackedToken

    now = datetime.utcnow()

    # Get counts
    signal_count = await session.execute(select(func.count(Signal.id)))
    channel_count = await session.execute(
        select(func.count(Channel.id)).where(Channel.is_active == True)
    )
    token_count = await session.execute(select(func.count(Token.id)))
    tracked_count = await session.execute(
        select(func.count(func.distinct(TrackedToken.symbol))).where(
            TrackedToken.is_active == True
        )
    )

    # Recent activity
    hour_ago = now - timedelta(hours=1)
    day_ago = now - timedelta(hours=24)

    recent_signals_1h = await session.execute(
        select(func.count(Signal.id)).where(Signal.timestamp >= hour_ago)
    )
    recent_signals_24h = await session.execute(
        select(func.count(Signal.id)).where(Signal.timestamp >= day_ago)
    )

    # Success rate and avg ROI from recent signals
    recent_result = await session.execute(
        select(Signal).where(Signal.timestamp >= day_ago)
    )
    recent_signals = recent_result.scalars().all()

    success_count = sum(1 for s in recent_signals if s.success)
    roi_values = [s.roi_percent for s in recent_signals if s.roi_percent is not None]
    success_rate = (success_count / len(recent_signals)) if recent_signals else 0
    avg_roi = (sum(roi_values) / len(roi_values) / 100) if roi_values else 0  # as decimal

    total_sigs = signal_count.scalar() or 0
    active_chans = channel_count.scalar() or 0
    total_toks = token_count.scalar() or 0
    tracked = tracked_count.scalar() or 0

    return {
        # Fields matching StatsCards component
        "total_signals": total_sigs,
        "active_channels": active_chans,
        "tokens_tracked": tracked or total_toks,
        "success_rate": round(success_rate, 3),
        "signals_24h": recent_signals_24h.scalar() or 0,
        "avg_roi_24h": round(avg_roi, 4),
        # Extra fields
        "total_channels": active_chans,
        "total_tokens": total_toks,
        "signals_last_hour": recent_signals_1h.scalar() or 0,
        "websocket_connections": manager.connection_count,
        "timestamp": now.isoformat(),
        "status": "healthy",
    }


@router.websocket("/stream")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time signal updates.
    
    Connect to receive:
    - New signals as they are detected
    - Market sentiment updates (every 30 seconds)
    - Trending token updates (every minute)
    
    Optional authentication via query param: ?token=<your_api_token>
    
    Send messages to subscribe to specific tokens or channels:
    ```json
    {"action": "subscribe", "type": "token", "value": "BTC"}
    {"action": "subscribe", "type": "channel", "value": "CryptoWhales"}
    {"action": "unsubscribe", "type": "token", "value": "BTC"}
    ```
    """
    logger.info(f"🔌 WebSocket connection attempt from {websocket.client}")
    
    # Extract token from query string if provided
    token = websocket.query_params.get("token")
    user = None
    if token:
        # Get a database session for token verification
        async with async_session_maker() as session:
            user = await verify_websocket_token(token, session)
        logger.info(f"WebSocket auth: user={user.username if user else 'none'}")
    
    # Accept the connection (with user association if authenticated)
    await manager.connect(websocket, user_id=user.id if user else None)
    logger.info(f"WebSocket connected (user={user.username if user else 'anon'}). Total connections: {manager.connection_count}")
    
    # Client subscriptions
    subscriptions = {
        "tokens": set(),
        "channels": set(),
    }
    
    # Send welcome message
    try:
        await websocket.send_json({
            "type": "connected",
            "message": "Welcome to Crypto Signal Aggregator live stream",
            "timestamp": datetime.utcnow().isoformat(),
        })
    except Exception as e:
        logger.error(f"Failed to send welcome message: {e}")
        manager.disconnect(websocket)
        return
    
    update_task = None
    price_task = None
    try:
        # Start background task for periodic updates
        update_task = asyncio.create_task(
            send_periodic_updates(websocket, subscriptions)
        )
        
        # Start tracked token price updates for authenticated users
        if user:
            price_task = asyncio.create_task(
                send_tracked_price_updates(websocket, user.id)
            )
        
        # Listen for client messages
        while True:
            data = await websocket.receive_text()
            
            try:
                message = json.loads(data)
                action = message.get("action")
                sub_type = message.get("type")
                value = message.get("value", "").upper()
                
                if action == "subscribe":
                    if sub_type == "token" and value:
                        subscriptions["tokens"].add(value)
                        await websocket.send_json({
                            "type": "subscribed",
                            "sub_type": "token",
                            "value": value,
                        })
                    elif sub_type == "channel" and value:
                        subscriptions["channels"].add(value)
                        await websocket.send_json({
                            "type": "subscribed",
                            "sub_type": "channel",
                            "value": value,
                        })
                
                elif action == "unsubscribe":
                    if sub_type == "token" and value in subscriptions["tokens"]:
                        subscriptions["tokens"].discard(value)
                        await websocket.send_json({
                            "type": "unsubscribed",
                            "sub_type": "token",
                            "value": value,
                        })
                    elif sub_type == "channel" and value in subscriptions["channels"]:
                        subscriptions["channels"].discard(value)
                        await websocket.send_json({
                            "type": "unsubscribed",
                            "sub_type": "channel",
                            "value": value,
                        })
                
                elif action == "ping":
                    await websocket.send_json({"type": "pong", "timestamp": datetime.utcnow().isoformat()})
                    
            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": "error",
                    "message": "Invalid JSON message",
                })
    
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected. Remaining connections: {manager.connection_count - 1}")
        manager.disconnect(websocket)
        if update_task:
            update_task.cancel()
        if price_task:
            price_task.cancel()
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)
        if update_task:
            update_task.cancel()
        if price_task:
            price_task.cancel()


async def send_periodic_updates(websocket: WebSocket, subscriptions: dict):
    """Send periodic updates to a WebSocket client using real DB data."""
    sentiment_counter = 0
    trending_counter = 0
    
    while True:
        try:
            await asyncio.sleep(10)  # Check every 10 seconds
            
            sentiment_counter += 10
            trending_counter += 10
            
            # Send sentiment update every 30 seconds (from real data)
            if sentiment_counter >= 30:
                sentiment_counter = 0
                try:
                    async with async_session_maker() as session:
                        analytics = AnalyticsService(session)
                        sentiment_data = await analytics.get_market_sentiment(hours=24)
                        await websocket.send_json({
                            "type": "sentiment_update",
                            "timestamp": datetime.utcnow().isoformat(),
                            "data": {
                                "overall": sentiment_data.get("overall_sentiment", "NEUTRAL"),
                                "score": sentiment_data.get("sentiment_score", 0),
                            }
                        })
                except Exception as e:
                    logger.debug(f"Failed to send sentiment update: {e}")
            
            # Send trending update every 60 seconds (from real data)
            if trending_counter >= 60:
                trending_counter = 0
                try:
                    async with async_session_maker() as session:
                        analytics = AnalyticsService(session)
                        trending_data = await analytics.get_trending_tokens(hours=24)
                        top_tokens = []
                        # Handle response format (it returns a dict with "trending" key)
                        trending_list = trending_data.get("trending", []) if isinstance(trending_data, dict) else []

                        # Enrich with real prices
                        if trending_list:
                            try:
                                from app.services.market_service import market_service
                                symbols = [t.get("symbol", "") for t in trending_list[:5]]
                                price_data = await market_service.get_prices_for_symbols(symbols)
                            except Exception:
                                price_data = {}
                        else:
                            price_data = {}

                        for token in trending_list[:5]:
                            sym = token.get("symbol", "")
                            pd = price_data.get(sym, {})
                            top_tokens.append({
                                "symbol": sym,
                                "count": token.get("signal_count_24h", 0),
                                "change": pd.get("price_change_24h") or token.get("price_change_24h", 0),
                                "price": pd.get("price"),
                            })
                        await websocket.send_json({
                            "type": "trending_update",
                            "timestamp": datetime.utcnow().isoformat(),
                            "data": {"top_tokens": top_tokens},
                        })
                except Exception as e:
                    logger.debug(f"Failed to send trending update: {e}")
                
        except Exception:
            break


async def broadcast_new_signal(signal_data: dict):
    """Broadcast a new signal to all connected WebSocket clients."""
    await manager.broadcast({
        "type": "new_signal",
        "data": signal_data,
        "timestamp": datetime.utcnow().isoformat(),
    })


async def send_tracked_price_updates(websocket: WebSocket, user_id: int):
    """
    Send realtime price updates for a user's tracked tokens.
    Reads from the centralized TokenPriceTracker cache.
    """
    from app.services.token_tracker import token_tracker
    
    while True:
        try:
            await asyncio.sleep(15)  # Send price updates every 15 seconds
            
            prices = token_tracker.get_prices_for_user(user_id)
            if prices:
                await websocket.send_json({
                    "type": "tracked_price_update",
                    "timestamp": datetime.utcnow().isoformat(),
                    "data": {
                        "tokens": prices,
                    }
                })
        except Exception:
            break

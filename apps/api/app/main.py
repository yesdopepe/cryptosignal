"""
Crypto Signal Aggregator & Analysis API

A FastAPI-based cryptocurrency signal aggregation system that monitors
Telegram channels for token announcements, performs analytics on
historical data, and provides both REST API and responsive web interface.
"""
import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from fastapi import FastAPI, Request, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
import os

from app.config import settings
from app.database import create_tables, async_session_maker, engine
from app.cache import init_cache, close_cache
from app.routers import (
    signals_router, 
    analytics_router, 
    channels_router, 
    live_router, 
    auth_router,
    tracking_router,
    # webhooks_router
)
from app.routers.telegram import router as telegram_router
from app.routers.subscriptions import router as subscriptions_router
from app.routers.search import router as search_router
from app.routers.notifications import router as notifications_router
from app.services.telegram_monitor import telegram_monitor, start_monitoring, stop_monitoring
from app.services.token_tracker import token_tracker
# from app.services.streams_service import streams_service
from app.services.user_telegram import user_telegram_manager
from app.auth import get_current_user, require_admin

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def save_signal_to_db(signal_data: dict):
    """Save a detected signal to the database and broadcast via WebSocket."""
    from app.models.signal import Signal
    from app.models.channel import Channel
    from app.services.websocket_manager import manager
    from app.services.notification_service import notification_service
    from app.services.email_service import email_service
    from app.models.user import User
    from sqlalchemy import select
    
    try:
        async with async_session_maker() as session:
            # Check if channel exists, create if not
            channel_name = signal_data.get('channel_name', 'Unknown')
            channel_result = await session.execute(
                select(Channel).where(Channel.name == channel_name)
            )
            channel = channel_result.scalar_one_or_none()
            
            if not channel:
                # For non-Telegram sources (like DEXScreener), use channel name hash as telegram_id
                raw_channel_id = signal_data.get('channel_id', '')
                if raw_channel_id == 0 or raw_channel_id == '0' or not raw_channel_id:
                    # Generate unique ID from channel name for non-Telegram sources
                    import hashlib
                    telegram_id = hashlib.md5(channel_name.encode()).hexdigest()[:16]
                else:
                    telegram_id = str(raw_channel_id)
                
                channel = Channel(
                    name=channel_name,
                    telegram_id=telegram_id,
                    is_active=True,
                )
                session.add(channel)
                await session.flush()
                
                await session.flush()
                logger.info(f"🆕 Created new channel '{channel.name}'")
            
            # Create signal record
            signal = Signal(
                channel_id=channel.id,
                channel_name=channel_name,
                token_symbol=signal_data['token_symbol'],
                token_name=signal_data.get('token_name', signal_data['token_symbol']),
                price_at_signal=signal_data.get('price_at_signal'),
                signal_type=signal_data.get('signal_type', 'token_mention'),
                contract_addresses=signal_data.get('contract_addresses', []),
                chain=signal_data.get('chain'),
                sentiment=signal_data.get('sentiment', 'NEUTRAL'),
                message_text=signal_data.get('message_text', ''),
                confidence_score=signal_data.get('confidence_score', 0.5),
                tags=signal_data.get('tags', []),
            )
            
            session.add(signal)
            await session.commit()
            await session.refresh(signal)
            
            logger.info(f"💾 Saved signal #{signal.id}: {signal.token_symbol} from {channel_name}")
            
            # Broadcast to WebSocket clients
            broadcast_data = {
                "id": signal.id,
                "token_symbol": signal.token_symbol,
                "token_name": signal.token_name,
                "channel_name": signal.channel_name,
                "sentiment": signal.sentiment,
                "price_at_signal": signal.price_at_signal,
                "confidence_score": signal.confidence_score,
                "signal_type": signal_data.get("signal_type", "token_mention"),
                "contract_addresses": signal_data.get("contract_addresses", []),
                "chain": signal_data.get("chain"),
                "timestamp": signal.timestamp.isoformat() if signal.timestamp else datetime.utcnow().isoformat(),
            }
            
            await manager.broadcast({
                "type": "new_signal",
                "data": broadcast_data,
                "timestamp": datetime.utcnow().isoformat(),
            })
            
            # Notify subscribers (Phase 2)
            # Run in background to not block signal processing
            enriched_signal_data = {
                **signal_data,
                "signal_id": signal.id,
                "timestamp": signal.timestamp.isoformat() if signal.timestamp else datetime.utcnow().isoformat(),
            }
            asyncio.create_task(
                notification_service.notify_subscribers(channel.id, enriched_signal_data)
            )
            
    except Exception as e:
        logger.error(f"Failed to save signal: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    logger.info("🚀 Starting Crypto Signal Aggregator...")
    
    # Create database tables
    await create_tables()
    logger.info("✅ Database tables created")
    
    # Add new columns if they don't exist (lightweight migration for SQLite)
    try:
        async with engine.begin() as conn:
            from sqlalchemy import text, inspect as sa_inspect
            # Check if 'address' column exists in tracked_tokens
            result = await conn.execute(text("PRAGMA table_info(tracked_tokens)"))
            columns = [row[1] for row in result.fetchall()]
            if 'address' not in columns:
                await conn.execute(text("ALTER TABLE tracked_tokens ADD COLUMN address VARCHAR"))
                logger.info("✅ Added 'address' column to tracked_tokens")

            if 'name' not in columns:
                await conn.execute(text("ALTER TABLE tracked_tokens ADD COLUMN name VARCHAR"))
                logger.info("✅ Added 'name' column to tracked_tokens")
            
            # Migrate signals table — add new columns
            result = await conn.execute(text("PRAGMA table_info(signals)"))
            sig_cols = [row[1] for row in result.fetchall()]
            
            if 'signal_type' not in sig_cols:
                await conn.execute(text(
                    "ALTER TABLE signals ADD COLUMN signal_type VARCHAR(30) DEFAULT 'token_mention'"
                ))
                logger.info("✅ Added 'signal_type' column to signals")
            
            if 'contract_addresses' not in sig_cols:
                await conn.execute(text(
                    "ALTER TABLE signals ADD COLUMN contract_addresses JSON DEFAULT '[]'"
                ))
                logger.info("✅ Added 'contract_addresses' column to signals")
            
            if 'chain' not in sig_cols:
                await conn.execute(text(
                    "ALTER TABLE signals ADD COLUMN chain VARCHAR(30)"
                ))
                logger.info("✅ Added 'chain' column to signals")
            
            # Migrate notifications table — add 'data' column if missing
            result = await conn.execute(text("PRAGMA table_info(notifications)"))
            notif_cols = [row[1] for row in result.fetchall()]
            
            if 'data' not in notif_cols:
                await conn.execute(text(
                    "ALTER TABLE notifications ADD COLUMN data JSON"
                ))
                logger.info("✅ Added 'data' column to notifications")

            if 'signal_id' not in notif_cols:
                await conn.execute(text(
                    "ALTER TABLE notifications ADD COLUMN signal_id INTEGER"
                ))
                logger.info("✅ Added 'signal_id' column to notifications")
            
            if 'token_symbol' not in notif_cols:
                await conn.execute(text(
                    "ALTER TABLE notifications ADD COLUMN token_symbol VARCHAR(20)"
                ))
                logger.info("✅ Added 'token_symbol' column to notifications")
            
            if 'contract_address' not in notif_cols:
                await conn.execute(text(
                    "ALTER TABLE notifications ADD COLUMN contract_address VARCHAR(255)"
                ))
                logger.info("✅ Added 'contract_address' column to notifications")
            
            if 'channel_name' not in notif_cols:
                await conn.execute(text(
                    "ALTER TABLE notifications ADD COLUMN channel_name VARCHAR(255)"
                ))
                logger.info("✅ Added 'channel_name' column to notifications")

            # Make price_at_signal nullable (SQLite doesn't support ALTER COLUMN,
            # but newly inserted rows will be fine since the ORM maps it as nullable)
            
            # Check notifications table exists (create_tables above should handle it,
            # but ensure model was imported)
            from app.models.notification import Notification  # noqa: F401
    except Exception as e:
        logger.debug(f"Migration check (non-critical): {e}")
    
    # Initialize cache
    await init_cache()
    
    # ===== EMAIL DIAGNOSTICS — print at startup so we know if email works =====
    from app.services.email_service import email_service as _startup_es
    print(f"===== EMAIL DIAGNOSTICS =====")
    print(f"  SMTP Host: {settings.smtp_host}")
    print(f"  SMTP Port: {settings.smtp_port}")
    print(f"  SMTP User: {settings.smtp_user}")
    print(f"  SMTP Password set: {bool(settings.smtp_password)}")
    print(f"  From Email: {settings.notification_from_email}")
    print(f"  has_email_credentials: {settings.has_email_credentials}")
    print(f"  notification_enabled: {settings.notification_enabled}")
    print(f"  email_service.is_available: {_startup_es.is_available}")
    print(f"=============================")
    
    # Quick DB check: list all active users
    try:
        from app.models.user import User as _U
        from sqlalchemy import select as _sel
        async with async_session_maker() as _sess:
            _users = (await _sess.execute(_sel(_U).where(_U.is_active == True))).scalars().all()
            print(f"===== ACTIVE USERS ({len(_users)}) =====")
            for _u in _users:
                print(f"  #{_u.id} {_u.username} — email={_u.email} admin={_u.is_admin}")
            print(f"==============================")
    except Exception as _e:
        print(f"  [DIAG] Could not query users: {_e}")
    
    # Background service startup task to prevent blocking API availability
    async def start_background_services():
        """Start heavy background services in parallel without blocking API startup."""
        
        # 1. Ensure ALL active users are subscribed to ALL existing channels (Backfill)
        try:
            from app.models.user import User
            from app.models.channel import Channel
            from app.models.channel_subscription import ChannelSubscription
            from sqlalchemy import select
            
            async with async_session_maker() as session:
                all_users = (await session.execute(select(User).where(User.is_active == True))).scalars().all()
                channels = (await session.execute(select(Channel))).scalars().all()
                
                count = 0
                for user in all_users:
                    for channel in channels:
                        # Check if sub exists
                        stmt = select(ChannelSubscription).where(
                            ChannelSubscription.user_id == user.id,
                            ChannelSubscription.channel_id == channel.id
                        )
                        exists = (await session.execute(stmt)).scalar_one_or_none()
                        
                        if not exists:
                            new_sub = ChannelSubscription(
                                user_id=user.id,
                                channel_id=channel.id,
                                is_active=True,
                                notify_email=True,
                                notify_telegram=True
                            )
                            session.add(new_sub)
                            count += 1
                
                if count > 0:
                    await session.commit()
                    logger.info(f"✅ Auto-subscribed users to {count} channel slots")
        except Exception as e:
            logger.error(f"Failed to backfill user subscriptions: {e}")

        async def start_telegram():
            try:
                logger.info("📡 Starting Telegram monitor...")
                await start_monitoring(on_signal=save_signal_to_db)
            except Exception as e:
                logger.error(f"❌ Failed to start Telegram monitor: {e}")

        async def start_tracker_and_streams():
            try:
                # Start real-time token price tracker
                logger.info("📈 Starting token price tracker...")
                await token_tracker.start()

                # Initialize Moralis Streams + sync tracked addresses
                # logger.info("🌊 Initializing Moralis Streams...")
                # await streams_service.initialize()
                # all_addresses = token_tracker.get_all_tracked_addresses()
                # if all_addresses:
                #    await streams_service.sync_addresses(all_addresses)
                #    logger.info(f"🌊 Synced {len(all_addresses)} addresses to Moralis Stream")
            except Exception as e:
                logger.error(f"❌ Failed to start tracker/streams: {e}")

        # Run independently so one failure doesn't block the other
        await asyncio.gather(
            start_telegram(),
            start_tracker_and_streams()
        )

    # Launch services in background
    asyncio.create_task(start_background_services())
    
    logger.info("✅ Application started successfully (Background services initializing...)")
    logger.info(f"📊 API docs available at: http://localhost:8000/docs")
    logger.info(f"📱 Telegram: Waiting for real messages (authenticate via /api/v1/telegram/setup)")
    
    # Restore per-user background monitoring for users with saved sessions
    logger.info("📡 Restoring per-user background monitoring...")
    asyncio.create_task(user_telegram_manager.restore_all_monitoring())
    
    yield
    
    # Shutdown
    logger.info("🛑 Shutting down...")
    await user_telegram_manager.shutdown()
    await token_tracker.stop()
    # await streams_service.cleanup()
    await stop_monitoring()
    await close_cache()
    logger.info("✅ Cleanup complete")


# Create FastAPI application
app = FastAPI(
    title="Crypto Signal Aggregator API",
    description="""
## Cryptocurrency Signal Aggregation & Analysis System

This API aggregates crypto trading signals from Telegram channels, 
performs analytics on historical data, and provides real-time insights.

### Features:
- 📊 **100,000+ Signal Records** - Comprehensive historical data
- ⚡ **Redis Caching** - Sub-20ms response times for cached endpoints
- 📈 **Analytics** - Token statistics, channel leaderboards, pattern detection
- 🔴 **Real-time** - WebSocket support for live signal streaming
- 📱 **Responsive UI** - Mobile-friendly web dashboard

### Cache Performance:
| Endpoint | Without Cache | With Cache | Improvement |
|----------|---------------|------------|-------------|
| /analytics/historical | 1500-3000ms | 10-20ms | 100-200x |
| /analytics/channels/leaderboard | 2000-4000ms | 5-15ms | 200-400x |
| /analytics/patterns | 1500-3000ms | 5-15ms | 100-300x |

### Authentication:
Admin endpoints require `X-Admin-Key` header with valid API key.
    """,
    version="1.0.0",
    contact={
        "name": "Crypto Signal Aggregator",
    },
    license_info={
        "name": "MIT",
    },
    lifespan=lifespan,
)

# Add CORS middleware - allow all origins for development
logger.info(f"🔒 CORS Allowed Origins: {settings.cors_origins}")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,  # Load from settings (env vars)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
static_path = os.path.join(os.path.dirname(__file__), "..", "static")
if os.path.exists(static_path):
    app.mount("/static", StaticFiles(directory=static_path), name="static")

# Setup templates
templates_path = os.path.join(os.path.dirname(__file__), "..", "templates")
templates = Jinja2Templates(directory=templates_path)

# Include API routers
app.include_router(signals_router, prefix=settings.api_v1_prefix)
app.include_router(analytics_router, prefix=settings.api_v1_prefix)
app.include_router(channels_router, prefix=settings.api_v1_prefix)
app.include_router(live_router, prefix=settings.api_v1_prefix)
app.include_router(auth_router, prefix=settings.api_v1_prefix)
app.include_router(telegram_router, prefix=settings.api_v1_prefix)
app.include_router(subscriptions_router, prefix=settings.api_v1_prefix)
app.include_router(search_router, prefix=settings.api_v1_prefix)
app.include_router(tracking_router, prefix=settings.api_v1_prefix)
# app.include_router(webhooks_router, prefix=settings.api_v1_prefix)
app.include_router(notifications_router, prefix=settings.api_v1_prefix)


# ============== Web Interface Routes ==============

@app.get("/", response_class=HTMLResponse, tags=["Web Interface"])
async def dashboard(request: Request):
    """
    Main dashboard page with real-time signal feed and market overview.
    """
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "title": "Dashboard"}
    )


@app.get("/signals", response_class=HTMLResponse, tags=["Web Interface"])
async def signals_page(request: Request):
    """
    Signals page with searchable and filterable signal list.
    """
    return templates.TemplateResponse(
        "signals.html",
        {"request": request, "title": "Signals"}
    )


@app.get("/analytics", response_class=HTMLResponse, tags=["Web Interface"])
async def analytics_page(request: Request):
    """
    Analytics page with historical data visualization and performance charts.
    """
    return templates.TemplateResponse(
        "analytics.html",
        {"request": request, "title": "Analytics"}
    )


# ============== Health Check ==============

@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint for monitoring."""
    return {
        "status": "healthy",
        "service": "crypto-signal-aggregator",
        "version": "1.0.0",
    }


@app.get("/api/v1", tags=["API Info"])
async def api_info():
    """API version and information."""
    return {
        "name": "Crypto Signal Aggregator API",
        "version": "1.0.0",
        "endpoints": {
            "signals": f"{settings.api_v1_prefix}/signals",
            "analytics": f"{settings.api_v1_prefix}/analytics",
            "channels": f"{settings.api_v1_prefix}/channels",
            "live": f"{settings.api_v1_prefix}/live",
        },
        "documentation": "/docs",
        "websocket": f"{settings.api_v1_prefix}/live/stream",
    }


# ============== Telegram Authentication Endpoints (Legacy - Global) ==============

@app.get("/api/v1/telegram/status", tags=["Telegram"])
async def telegram_status():
    """
    Get current Telegram authentication and monitoring status.
    This endpoint is public to show status.
    """
    return telegram_monitor.status


@app.post("/api/v1/telegram/setup", tags=["Telegram"])
async def telegram_setup(phone_number: str, user = Depends(require_admin)):
    """
    Start Telegram authentication with phone number (Admin only).
    
    This will send a verification code to the provided phone number.
    After receiving the code, use /api/v1/telegram/verify to complete auth.
    
    Requires admin authentication via Bearer token in Authorization header.
    
    Args:
        phone_number: Phone number in international format (e.g., +1234567890)
    """
    result = await telegram_monitor.setup_phone(phone_number)
    return result


@app.post("/api/v1/telegram/verify", tags=["Telegram"])
async def telegram_verify(code: str, user = Depends(require_admin)):
    """
    Verify the authentication code sent to phone (Admin only).
    
    Args:
        code: The verification code received via SMS/Telegram
    """
    result = await telegram_monitor.verify_code(code)
    return result


@app.post("/api/v1/telegram/verify-2fa", tags=["Telegram"])
async def telegram_verify_2fa(password: str, user = Depends(require_admin)):
    """
    Verify 2FA password if required (Admin only).
    
    Args:
        password: Your Telegram 2FA password
    """
    result = await telegram_monitor.verify_2fa(password)
    return result


@app.post("/api/v1/telegram/logout", tags=["Telegram"])
async def telegram_logout(user = Depends(require_admin)):
    """
    Logout from Telegram and clear saved session (Admin only).
    """
    result = await telegram_monitor.logout()
    return result

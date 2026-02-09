"""Routers package."""
from app.routers.signals import router as signals_router
from app.routers.analytics import router as analytics_router
from app.routers.channels import router as channels_router
from app.routers.live import router as live_router
from app.routers.auth import router as auth_router
from app.routers.tracking import router as tracking_router
# from app.routers.webhooks import router as webhooks_router
from app.routers.notifications import router as notifications_router

__all__ = [
    "signals_router",
    "analytics_router",
    "channels_router",
    "live_router",
    "auth_router",
    "tracking_router",
    # "webhooks_router",
    "notifications_router",
]

"""
Telegram router for per-user Telegram connections and background monitoring.
Allows authenticated users to connect their own Telegram account
and start background monitoring of subscribed channels.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, List

from app.auth import get_current_user
from app.services.user_telegram import user_telegram_manager

router = APIRouter(prefix="/telegram", tags=["User Telegram"])


# ============== Request/Response Models ==============

class ConnectRequest(BaseModel):
    """Request to start Telegram connection."""
    phone_number: str


class VerifyCodeRequest(BaseModel):
    """Request to verify phone code."""
    code: str


class Verify2FARequest(BaseModel):
    """Request to verify 2FA password."""
    password: str


class TelegramStatusResponse(BaseModel):
    """Telegram connection status response."""
    connected: bool
    auth_state: str
    phone_number: Optional[str] = None
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    has_saved_session: Optional[bool] = None
    is_monitoring: Optional[bool] = None
    error: Optional[str] = None


class ChannelInfo(BaseModel):
    """Channel/group information."""
    id: int
    title: str
    username: Optional[str] = None
    is_channel: bool
    is_group: bool
    participants_count: Optional[int] = None
    unread_count: Optional[int] = None


class ChannelsResponse(BaseModel):
    """Response with list of user's channels."""
    success: bool
    channels: List[ChannelInfo] = []
    count: int = 0
    error: Optional[str] = None


class AuthResponse(BaseModel):
    """Generic auth operation response."""
    success: bool
    message: Optional[str] = None
    auth_state: str
    requires_2fa: Optional[bool] = None
    error: Optional[str] = None


class MonitoringStatusResponse(BaseModel):
    """Background monitoring status."""
    is_monitoring: bool
    started_at: Optional[str] = None
    channels_count: int = 0
    messages_processed: int = 0
    signals_detected: int = 0
    last_message_at: Optional[str] = None
    errors: List[str] = []
    queue_size: int = 0


class MonitoringResponse(BaseModel):
    """Response for monitoring start/stop."""
    success: bool
    message: Optional[str] = None
    is_monitoring: bool = False
    channels_count: int = 0
    error: Optional[str] = None


# ============== Auth Endpoints ==============

@router.get("/status", response_model=TelegramStatusResponse)
async def get_status(user = Depends(get_current_user)):
    """
    Get current user's Telegram connection status.
    
    Returns whether the user is connected to Telegram and account details.
    """
    status = await user_telegram_manager.get_user_status(user.id)
    return TelegramStatusResponse(**status)


@router.post("/connect", response_model=AuthResponse)
async def connect_telegram(
    request: ConnectRequest,
    user = Depends(get_current_user)
):
    """
    Start Telegram connection with phone number.
    
    This will send a verification code to the provided phone number.
    After receiving the code, use /verify to complete authentication.
    Background monitoring starts automatically after authentication.
    """
    result = await user_telegram_manager.start_auth(user.id, request.phone_number)
    return AuthResponse(**result)


@router.post("/verify", response_model=AuthResponse)
async def verify_code(
    request: VerifyCodeRequest,
    user = Depends(get_current_user)
):
    """
    Verify the authentication code sent to phone.
    
    If 2FA is enabled on the Telegram account, this will return
    requires_2fa=true and you'll need to call /verify-2fa next.
    Background monitoring starts automatically after verification.
    """
    result = await user_telegram_manager.verify_code(user.id, request.code)
    return AuthResponse(**result)


@router.post("/verify-2fa", response_model=AuthResponse)
async def verify_2fa(
    request: Verify2FARequest,
    user = Depends(get_current_user)
):
    """
    Verify 2FA password if required.
    Background monitoring starts automatically after verification.
    """
    result = await user_telegram_manager.verify_2fa(user.id, request.password)
    return AuthResponse(**result)


@router.get("/channels", response_model=ChannelsResponse)
async def list_channels(user = Depends(get_current_user)):
    """
    List all channels and groups the user has joined on Telegram.
    The user must be connected to Telegram first.
    """
    result = await user_telegram_manager.get_user_channels(user.id)
    
    if not result["success"]:
        return ChannelsResponse(
            success=False,
            error=result.get("error", "Failed to get channels"),
            channels=[],
            count=0
        )
    
    channels = [ChannelInfo(**ch) for ch in result.get("channels", [])]
    return ChannelsResponse(
        success=True,
        channels=channels,
        count=len(channels)
    )


@router.post("/disconnect", response_model=AuthResponse)
async def disconnect_telegram(user = Depends(get_current_user)):
    """
    Disconnect from Telegram and clear saved session.
    This also stops any active background monitoring.
    """
    result = await user_telegram_manager.disconnect(user.id)
    return AuthResponse(
        success=result["success"],
        message=result.get("message"),
        auth_state="not_connected" if result["success"] else "error",
        error=result.get("error")
    )


# ============== Background Monitoring Endpoints ==============

@router.get("/monitoring/status", response_model=MonitoringStatusResponse)
async def get_monitoring_status(user = Depends(get_current_user)):
    """
    Get the current background monitoring status.
    
    Returns whether monitoring is active, how many channels are being watched,
    how many messages have been processed, and how many signals detected.
    """
    status = user_telegram_manager.get_monitoring_status(user.id)
    return MonitoringStatusResponse(**status)


@router.post("/monitoring/start", response_model=MonitoringResponse)
async def start_monitoring(user = Depends(get_current_user)):
    """
    Start background monitoring of subscribed channels.
    
    The system will listen for new messages on all channels you've subscribed to,
    parse them for trading signals, and create notifications automatically.
    
    Pre-requisites:
    - Must be connected to Telegram (use /connect first)
    - Must have at least one channel subscription (use /subscriptions to subscribe)
    """
    result = await user_telegram_manager.start_monitoring(user.id)
    return MonitoringResponse(**result)


@router.post("/monitoring/stop", response_model=MonitoringResponse)
async def stop_monitoring(user = Depends(get_current_user)):
    """
    Stop background monitoring.
    
    The system will stop listening for new messages. Existing signals
    and notifications are preserved.
    """
    result = await user_telegram_manager.stop_monitoring(user.id)
    return MonitoringResponse(**result)


@router.post("/monitoring/refresh", response_model=MonitoringResponse)
async def refresh_monitoring(user = Depends(get_current_user)):
    """
    Refresh background monitoring.
    
    Use after subscribing to new channels to start monitoring them.
    This restarts the listener with the updated channel list.
    """
    result = await user_telegram_manager.refresh_monitoring(user.id)
    return MonitoringResponse(**result)

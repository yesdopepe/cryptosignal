"""Authentication router for login, registration, and user management."""
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.auth import (
    UserCreate, UserLogin, UserResponse, TokenResponse,
    authenticate_user, create_user_in_db, create_access_token,
    get_current_user, require_admin, user_to_response,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])


class RegisterRequest(BaseModel):
    """Registration request body."""
    email: EmailStr
    username: str
    password: str


class LoginRequest(BaseModel):
    """Login request body."""
    username: str
    password: str


class MessageResponse(BaseModel):
    """Generic message response."""
    success: bool
    message: str


@router.post("/register", response_model=TokenResponse)
async def register(
    request: RegisterRequest,
    session: AsyncSession = Depends(get_session),
):
    """
    Register a new user account.
    
    Returns an access token upon successful registration.
    """
    # Validate password length
    if len(request.password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters long",
        )
    
    # Validate username
    if len(request.username) < 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username must be at least 3 characters long",
        )
    
    # Create user
    user = await create_user_in_db(
        session=session,
        email=request.email,
        username=request.username,
        password=request.password,
    )
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email or username already registered",
        )
    
    # Auto-subscribe new user to ALL existing channels
    try:
        from app.models.channel import Channel
        from app.models.channel_subscription import ChannelSubscription
        
        channels = (await session.execute(select(Channel))).scalars().all()
        for channel in channels:
            sub = ChannelSubscription(
                user_id=user.id,
                channel_id=channel.id,
                is_active=True,
                notify_email=True,
                notify_telegram=True,
            )
            session.add(sub)
        if channels:
            await session.commit()
            logger.info(f"✅ Auto-subscribed new user '{user.username}' to {len(channels)} channels")
    except Exception as e:
        logger.error(f"Failed to auto-subscribe new user: {e}")
    
    # Generate token
    token, expires_at = create_access_token(
        user_id=user.id,
        email=user.email,
        is_admin=user.is_admin,
    )
    
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_at=expires_at,
        user=user_to_response(user),
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    request: LoginRequest,
    session: AsyncSession = Depends(get_session),
):
    """
    Authenticate and get an access token.
    
    The token can be used:
    - As Bearer token in Authorization header
    - In X-API-Key header
    - As query parameter for WebSocket: ?token=<token>
    """
    user = await authenticate_user(session, request.username, request.password)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )
    
    # Generate token
    token, expires_at = create_access_token(
        user_id=user.id,
        email=user.email,
        is_admin=user.is_admin,
    )
    
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_at=expires_at,
        user=user_to_response(user),
    )


@router.post("/logout", response_model=MessageResponse)
async def logout(user = Depends(get_current_user)):
    """
    Logout the current user.
    
    Note: With JWT tokens, logout is handled client-side by discarding the token.
    This endpoint serves as a confirmation and could be extended to implement
    token blacklisting if needed.
    """
    return MessageResponse(
        success=True,
        message=f"Logged out user: {user.username}",
    )


@router.get("/me", response_model=UserResponse)
async def get_me(user = Depends(get_current_user)):
    """Get current authenticated user info."""
    return user_to_response(user)


@router.post("/users", response_model=MessageResponse)
async def create_new_user(
    request: RegisterRequest,
    admin = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    """
    Create a new user (admin only).
    """
    user = await create_user_in_db(
        session=session,
        email=request.email,
        username=request.username,
        password=request.password,
        is_admin=False,
    )
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email or username already exists",
        )
    
    return MessageResponse(
        success=True,
        message=f"User '{request.username}' created successfully",
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(user = Depends(get_current_user)):
    """
    Refresh the access token for the current user.
    
    Returns a new token with extended expiration.
    """
    token, expires_at = create_access_token(
        user_id=user.id,
        email=user.email,
        is_admin=user.is_admin,
    )
    
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_at=expires_at,
        user=user_to_response(user),
    )

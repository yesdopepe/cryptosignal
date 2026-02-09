"""Authentication and authorization module with JWT and bcrypt."""
import logging
from datetime import datetime, timedelta
from typing import Optional

import bcrypt
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.database import get_session

logger = logging.getLogger(__name__)

# Security schemes
security_bearer = HTTPBearer(auto_error=False)

# JWT Configuration
JWT_SECRET_KEY = settings.secret_key
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24 * 7  # 1 week


# ============== Pydantic Models ==============

class UserCreate(BaseModel):
    """Schema for user registration."""
    email: EmailStr
    username: str
    password: str


class UserLogin(BaseModel):
    """Schema for user login."""
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    """Schema for user response (without sensitive data)."""
    id: int
    email: str
    username: str
    is_active: bool
    is_admin: bool
    is_verified: bool
    has_telegram: bool
    created_at: Optional[datetime] = None
    last_login: Optional[datetime] = None


class TokenResponse(BaseModel):
    """Schema for authentication token response."""
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime
    user: UserResponse


# ============== Password Utilities ==============

def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against its bcrypt hash."""
    try:
        return bcrypt.checkpw(
            password.encode('utf-8'), 
            password_hash.encode('utf-8')
        )
    except Exception:
        return False


# ============== JWT Utilities ==============

def create_access_token(user_id: int, email: str, is_admin: bool = False) -> tuple[str, datetime]:
    """Create a JWT access token."""
    expires_at = datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS)
    
    payload = {
        "sub": str(user_id),
        "email": email,
        "is_admin": is_admin,
        "exp": expires_at,
        "iat": datetime.utcnow(),
    }
    
    token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return token, expires_at


def decode_access_token(token: str) -> Optional[dict]:
    """Decode and validate a JWT access token."""
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload
    except JWTError as e:
        logger.debug(f"JWT decode error: {e}")
        return None


# ============== User Management ==============

async def get_user_by_email(session: AsyncSession, email: str):
    """Get a user by email."""
    from app.models.user import User
    result = await session.execute(
        select(User).options(selectinload(User.telegram_session)).where(User.email == email)
    )
    return result.scalar_one_or_none()


async def get_user_by_id(session: AsyncSession, user_id: int):
    """Get a user by ID."""
    from app.models.user import User
    result = await session.execute(
        select(User).options(selectinload(User.telegram_session)).where(User.id == user_id)
    )
    return result.scalar_one_or_none()


async def get_user_by_username(session: AsyncSession, username: str):
    """Get a user by username."""
    from app.models.user import User
    result = await session.execute(
        select(User).options(selectinload(User.telegram_session)).where(User.username == username)
    )
    return result.scalar_one_or_none()


async def create_user_in_db(
    session: AsyncSession, 
    email: str, 
    username: str, 
    password: str,
    is_admin: bool = False,
):
    """Create a new user in the database."""
    from app.models.user import User
    
    # Check if user already exists
    existing = await get_user_by_email(session, email)
    if existing:
        return None
    
    existing_username = await get_user_by_username(session, username)
    if existing_username:
        return None
    
    # Create new user
    user = User(
        email=email,
        username=username,
        password_hash=hash_password(password),
        is_admin=is_admin,
        is_active=True,
    )
    
    session.add(user)
    await session.flush()
    
    # Refresh with eager loading to prevent lazy load issues
    result = await session.execute(
        select(User).options(selectinload(User.telegram_session)).where(User.id == user.id)
    )
    user = result.scalar_one()
    
    logger.info(f"Created new user: {email}")
    return user


async def authenticate_user(session: AsyncSession, username_or_email: str, password: str):
    """Authenticate a user by username/email and password."""
    # Try email first
    user = await get_user_by_email(session, username_or_email)
    if not user:
        # Try username
        user = await get_user_by_username(session, username_or_email)
    
    if not user:
        return None
    
    if not verify_password(password, user.password_hash):
        return None
    
    if not user.is_active:
        return None
    
    # Update last login
    user.last_login = datetime.utcnow()
    await session.flush()
    
    return user


# ============== FastAPI Dependencies ==============

async def get_current_user(
    request: Request,
    bearer: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
    session: AsyncSession = Depends(get_session),
):
    """
    Get the current authenticated user from JWT token.
    
    Supports:
    - Bearer token in Authorization header
    - X-API-Key header (for backwards compatibility)
    """
    token = None
    
    # Check Bearer token
    if bearer and bearer.credentials:
        token = bearer.credentials
    
    # Check X-API-Key header (fallback)
    if not token:
        token = request.headers.get("X-API-Key")
    
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Decode JWT
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Get user from database
    user_id = int(payload.get("sub", 0))
    user = await get_user_by_id(session, user_id)
    
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return user


async def get_current_user_optional(
    request: Request,
    bearer: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
    session: AsyncSession = Depends(get_session),
):
    """
    Get the current user if authenticated, None otherwise.
    Does not raise exception for unauthenticated requests.
    """
    try:
        return await get_current_user(request, bearer, session)
    except HTTPException:
        return None


async def require_admin(
    user = Depends(get_current_user),
):
    """Require admin privileges."""
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
    return user


# ============== WebSocket Authentication ==============

async def verify_websocket_token(token: Optional[str], session: AsyncSession):
    """Verify a token for WebSocket connections."""
    if not token:
        return None
    
    payload = decode_access_token(token)
    if not payload:
        return None
    
    user_id = int(payload.get("sub", 0))
    return await get_user_by_id(session, user_id)


def get_websocket_token_from_query(query_string: str) -> Optional[str]:
    """Extract token from WebSocket query string."""
    from urllib.parse import parse_qs
    params = parse_qs(query_string)
    tokens = params.get('token', [])
    return tokens[0] if tokens else None


# ============== User Response Helper ==============

def user_to_response(user) -> UserResponse:
    """Convert a User model to UserResponse schema."""
    has_telegram = False
    if hasattr(user, 'telegram_session') and user.telegram_session:
        has_telegram = user.telegram_session.is_authenticated
    
    return UserResponse(
        id=user.id,
        email=user.email,
        username=user.username,
        is_active=user.is_active,
        is_admin=user.is_admin,
        is_verified=user.is_verified,
        has_telegram=has_telegram,
        created_at=user.created_at,
        last_login=user.last_login,
    )

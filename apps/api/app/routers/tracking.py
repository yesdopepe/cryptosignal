from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from app.database import get_session
from app.auth import get_current_user
from app.models.user import User
from app.models.tracked_token import TrackedToken
from pydantic import BaseModel

router = APIRouter(prefix="/tracking", tags=["tracking"])

class TrackedTokenCreate(BaseModel):
    symbol: str
    name: Optional[str] = None
    chain: str = "solana"
    address: Optional[str] = None
    notes: Optional[str] = None

class TrackedTokenResponse(BaseModel):
    id: int
    symbol: str
    name: Optional[str] = None
    chain: str
    address: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True

class TrackedTokenPriceResponse(BaseModel):
    symbol: str
    chain: Optional[str] = None
    address: Optional[str] = None
    price_usd: Optional[float] = None
    price_change_24h: Optional[float] = None
    token_name: Optional[str] = None
    token_logo: Optional[str] = None
    market_cap: Optional[float] = None
    volume_24h: Optional[float] = None
    cmc_rank: Optional[int] = None
    updated_at: Optional[str] = None

@router.get("/", response_model=List[TrackedTokenResponse])
async def get_tracked_tokens(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Get all tokens tracked by the current user."""
    query = select(TrackedToken).where(TrackedToken.user_id == current_user.id)
    result = await db.execute(query)
    return result.scalars().all()

@router.post("/", response_model=TrackedTokenResponse)
async def track_token(
    token_data: TrackedTokenCreate,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Track a new token."""
    # Check if already tracked
    query = select(TrackedToken).where(
        TrackedToken.user_id == current_user.id,
        TrackedToken.symbol == token_data.symbol
    )
    result = await db.execute(query)
    existing = result.scalar_one_or_none()
    
    if existing:
        return existing
        
    new_token = TrackedToken(
        user_id=current_user.id,
        symbol=token_data.symbol,
        name=token_data.name,
        chain=token_data.chain,
        address=token_data.address,
        notes=token_data.notes
    )
    
    db.add(new_token)
    await db.commit()
    await db.refresh(new_token)

    # Register subscription immediately in memory for instant price fetching
    try:
        from app.services.token_tracker import token_tracker
        await token_tracker.add_subscription(
            user_id=new_token.user_id,
            symbol=new_token.symbol,
            address=new_token.address
        )
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Immediate tracker update failed: {e}")

    # Register address with Moralis Streams (fire-and-forget)
    # Removing Moralis Integration
    # if token_data.address:
    #     try:
    #         from app.services.streams_service import streams_service
    #         await streams_service.add_address(token_data.address)
    #     except Exception as e:
    #         import logging
    #         logging.getLogger(__name__).warning(f"Stream add_address failed: {e}")

    return new_token

@router.get("/prices", response_model=List[TrackedTokenPriceResponse])
async def get_tracked_token_prices(
    request: Request,
    response: Response,
    current_user: User = Depends(get_current_user)
):
    """Get real-time prices for all tracked tokens."""
    from app.services.token_tracker import token_tracker
    prices = token_tracker.get_prices_for_user(current_user.id)
    return prices


@router.get("/{symbol}/history")
async def get_token_price_history(
    symbol: str,
    current_user: User = Depends(get_current_user),
):
    """Get price/OHLC history for a tracked token (for candlestick charts)."""
    from app.services.token_tracker import token_tracker
    ohlc = await token_tracker.get_ohlc_history(symbol)
    return {"symbol": symbol.upper(), "history": ohlc}


@router.delete("/{symbol}", status_code=status.HTTP_204_NO_CONTENT)
async def untrack_token(
    symbol: str,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Stop tracking a token."""
    query = select(TrackedToken).where(
        TrackedToken.user_id == current_user.id,
        TrackedToken.symbol == symbol
    )
    result = await db.execute(query)
    token = result.scalar_one_or_none()
    
    if not token:
        raise HTTPException(status_code=404, detail="Token not found")

    # Remove address from Moralis Streams if no other user tracks it
    # Removing Moralis Integration
    # if token.address:
    #     try:
    #         # Check if any other user still tracks this address
    #         other = await db.execute(
    #             select(TrackedToken).where(
    #                 TrackedToken.address == token.address,
    #                 TrackedToken.id != token.id,
    #                 TrackedToken.is_active == True,
    #             )
    #         )
    #         if not other.scalar_one_or_none():
    #             from app.services.streams_service import streams_service
    #             await streams_service.remove_address(token.address)
    #     except Exception as e:
    #         import logging
    #         logging.getLogger(__name__).warning(f"Stream remove_address failed: {e}")

    await db.delete(token)
    await db.commit()

    # Remove subscription immediately from memory
    try:
        from app.services.token_tracker import token_tracker
        await token_tracker.remove_subscription(
            user_id=current_user.id,
            symbol=symbol
        )
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Immediate tracker removal failed: {e}")

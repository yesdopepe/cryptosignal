"""Search API router - CoinGecko-powered token search with Moralis address fallback."""
import logging
import re
from typing import Any, Optional, List, Tuple
from fastapi import APIRouter, Query, HTTPException, Request, Response
from fastapi_cache.decorator import cache
from pydantic import BaseModel

from app.services.coingecko_service import coingecko_service
# from app.services.moralis_service import moralis_service
from app.cache import custom_key_builder

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/search", tags=["Search"])

# -------------------------------------------------------------------
# Address detection helpers
# -------------------------------------------------------------------

# Regex patterns for known address formats
_EVM_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")          # Ethereum, BSC, Polygon, etc.
_TRON_RE = re.compile(r"^T[1-9A-HJ-NP-Za-km-z]{33}$")  # TRON base58check, 34 chars
_SOL_RE = re.compile(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$")  # Solana base58, 32-44 chars

# Map detected address type → list of CoinGecko platform ids to try
_PLATFORM_MAP: dict[str, list[str]] = {
    "evm": ["ethereum", "binance-smart-chain", "polygon-pos", "arbitrum-one", "base", "avalanche"],
    "tron": ["tron"],
    "solana": ["solana"],
}


def _detect_address_type(query: str) -> Optional[str]:
    """Return the address family if *query* looks like a contract address, else None."""
    if _EVM_RE.match(query):
        return "evm"
    if _TRON_RE.match(query):
        return "tron"
    # Solana addresses are base58, typically 43-44 chars, no 0x prefix
    if _SOL_RE.match(query) and len(query) >= 32:
        # Heuristic: if it's all alphanumeric and >= 32 chars, likely an address
        # But short queries like "bitcoin" are also alphanumeric — require >= 32 chars
        return "solana"
    return None


class TokenSearchResult(BaseModel):
    """Token search result."""
    symbol: str
    name: str
    address: str
    chain: str
    price_usd: Optional[float] = None
    price_change_24h: Optional[float] = None
    logo: Optional[str] = None
    decimals: Optional[int] = None
    market_cap_rank: Optional[int] = None


class SearchResponse(BaseModel):
    """Search response containing results."""
    query: str
    results: List[TokenSearchResult]
    count: int


def _safe_float(val: Any) -> Optional[float]:
    """Convert a value to float or return None."""
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _moralis_to_results(
    raw: List[dict], limit: int
) -> List[TokenSearchResult]:
    """Convert Moralis raw dicts into TokenSearchResult list."""
    results: List[TokenSearchResult] = []
    seen: set = set()
    for token in raw:
        key = f"{token.get('symbol', '')}_{token.get('chain', '')}_{token.get('address', '')}"
        if key in seen:
            continue
        seen.add(key)
        results.append(TokenSearchResult(
            symbol=token.get("symbol", ""),
            name=token.get("name", token.get("symbol", "")),
            address=token.get("address", ""),
            chain=token.get("chain", "unknown"),
            price_usd=_safe_float(token.get("price_usd")),
            price_change_24h=_safe_float(token.get("price_change_24h")),
            logo=token.get("logo"),
            decimals=token.get("decimals"),
        ))
        if len(results) >= limit:
            break
    return results


@router.get("/tokens", response_model=SearchResponse)
@cache(expire=30, key_builder=custom_key_builder)  # 30 second cache
async def search_tokens(
    request: Request,
    response: Response,
    q: str = Query(..., min_length=1, max_length=100, description="Search query (token name, symbol, or address)"),
    limit: int = Query(default=20, ge=1, le=50, description="Maximum number of results"),
):
    """
    Search for tokens by name, symbol, or contract address.

    - **Name / symbol** queries use CoinGecko (14 000+ coins, free tier).
    - **Contract address** queries use CoinGecko contract lookup (multi-chain)
      with Moralis fallback for EVM addresses.
    """
    query = q.strip()
    addr_type = _detect_address_type(query)

    # ---- Contract address lookup ------------------------------------
    if addr_type:
        platforms = _PLATFORM_MAP.get(addr_type, [])

        # 1. Try CoinGecko contract lookup (works for any chain)
        for platform in platforms:
            token = await coingecko_service.lookup_by_contract(query, platform)
            if token:
                result = TokenSearchResult(
                    symbol=token.get("symbol", ""),
                    name=token.get("name", ""),
                    address=query,
                    chain=token.get("chain", platform),
                    price_usd=_safe_float(token.get("price_usd")),
                    price_change_24h=_safe_float(token.get("price_change_24h")),
                    logo=token.get("logo"),
                    decimals=token.get("decimals"),
                    market_cap_rank=token.get("market_cap_rank"),
                )
                return SearchResponse(query=q, results=[result], count=1)

        # 2. Fallback to Moralis for EVM addresses
        # if addr_type == "evm" and moralis_service.is_available:
        #    try:
        #        raw_results = moralis_service.search_tokens(query)
        #        results = _moralis_to_results(raw_results, limit)
        #        if results:
        #            return SearchResponse(query=q, results=results, count=len(results))
        #    except Exception as e:
        #        logger.debug(f"Moralis address fallback failed: {e}")

        # Nothing found for this address
        return SearchResponse(query=q, results=[], count=0)

    # ---- Name / symbol → CoinGecko ----------------------------------
    try:
        raw = await coingecko_service.search_tokens(query, limit=limit)

        results: List[TokenSearchResult] = []
        seen: set = set()

        for token in raw:
            sym = token.get("symbol", "")
            name = token.get("name", sym)
            key = f"{sym}_{name}"
            if key in seen:
                continue
            seen.add(key)

            results.append(TokenSearchResult(
                symbol=sym,
                name=name,
                address=token.get("address", ""),
                chain=token.get("chain", "multi"),
                price_usd=_safe_float(token.get("price_usd")),
                price_change_24h=_safe_float(token.get("price_change_24h")),
                logo=token.get("logo"),
                decimals=token.get("decimals"),
                market_cap_rank=token.get("market_cap_rank"),
            ))

            if len(results) >= limit:
                break

        # If CoinGecko returned nothing, try Moralis as fallback
        # if not results and moralis_service.is_available:
        #    logger.debug(f"CoinGecko returned 0 results for '{query}', trying Moralis")
        #    try:
        #        moralis_raw = moralis_service.search_tokens(query)
        #        results = _moralis_to_results(moralis_raw, limit)
        #    except Exception:
        #        pass

        return SearchResponse(query=q, results=results, count=len(results))

    except Exception as e:
        # Last resort: try Moralis if CoinGecko errors out
        # if moralis_service.is_available:
        #    try:
        #        moralis_raw = moralis_service.search_tokens(query)
        #        results = _moralis_to_results(moralis_raw, limit)
        #        return SearchResponse(query=q, results=results, count=len(results))
        #    except Exception:
        #        pass
        raise HTTPException(status_code=500, detail=f"Search failed: {e}")


@router.get("/tokens/{address}", response_model=SearchResponse)
@cache(expire=30, key_builder=custom_key_builder)  # 30 second cache
async def get_token_by_address(
    address: str,
    request: Request,
    response: Response,
    chain: str = Query(default="eth", description="Chain to look up (eth, bsc, polygon, etc.)"),
):
    """
    Get token information by contract address.

    Returns token data including price and metadata for the specified address.
    """
    # if not moralis_service.is_available:
    #     raise HTTPException(
    #         status_code=503,
    #         detail="Moralis API is not configured. Set MORALIS_API_KEY in environment."
    #     )

    if True:
        # Fallback for now - we don't have a good single address lookup without Moralis or paid CG
        # Trying to use generic search logic which supports contract addresses via CG
        
        # Check if it's an EVM address
        if _EVM_RE.match(address):
             # Try generic lookup (which uses coingecko_service.lookup_by_contract)
             platforms = _PLATFORM_MAP.get("evm", [])
             for platform in platforms:
                token = await coingecko_service.lookup_by_contract(address, platform)
                if token:
                     result = TokenSearchResult(
                        symbol=token.get("symbol", ""),
                        name=token.get("name", ""),
                        address=address,
                        chain=token.get("chain", platform),
                        price_usd=_safe_float(token.get("price_usd")),
                        price_change_24h=_safe_float(token.get("price_change_24h")),
                        logo=token.get("logo"),
                        decimals=token.get("decimals"),
                        market_cap_rank=token.get("market_cap_rank"),
                    )
                     return SearchResponse(query=address, results=[result], count=1)
        
        # If nothing found
        return SearchResponse(query=address, results=[], count=0)
        
    """
    if not moralis_service.is_available:
        raise HTTPException(
            status_code=503,
            detail="Moralis API is not configured. Set MORALIS_API_KEY in environment."
        )

    try:
        token_stats = moralis_service.get_token_stats(address, chain)

        if not token_stats:
            return SearchResponse(query=address, results=[], count=0)

        result = TokenSearchResult(
            symbol=token_stats.get("symbol", ""),
            name=token_stats.get("name", ""),
            address=address,
            chain=chain,
            price_usd=_safe_float(token_stats.get("price_usd")),
            price_change_24h=_safe_float(token_stats.get("price_change_24h")),
            logo=token_stats.get("logo"),
            decimals=token_stats.get("decimals"),
        )

        return SearchResponse(query=address, results=[result], count=1)

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Token lookup failed: {str(e)}"
        )
    """

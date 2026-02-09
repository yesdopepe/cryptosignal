"""
Market data service — real-time cryptocurrency market overview.

Uses CoinGecko free API /coins/markets endpoint:
  - Top coins by market cap with prices, volume, logos, sparklines
  - No API key required
  - Rate limit: ~10-30 calls/min (we cache for 60s)
"""
import logging
import time
from typing import Dict, Any, List

import httpx

logger = logging.getLogger(__name__)

CG_BASE = "https://api.coingecko.com/api/v3"

# In-memory cache
_cache: Dict[str, Any] = {
    "data": None,
    "timestamp": 0,
}
_trending_cache: Dict[str, Any] = {
    "data": None,
    "timestamp": 0,
}
CACHE_TTL = 30  # seconds


class MarketService:
    """Fetches top cryptocurrency market data from CoinGecko (free tier)."""

    async def get_top_coins(
        self,
        per_page: int = 50,
        page: int = 1,
        sparkline: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Get top coins by market cap with rich market data.

        Returns list of coins with: symbol, name, image, current_price,
        market_cap, total_volume, price_change_percentage_24h,
        price_change_percentage_1h, price_change_percentage_7d,
        sparkline (7d), high_24h, low_24h, market_cap_rank, etc.
        """
        cache_key = f"top_{per_page}_{page}"
        now = time.time()

        # Return cached data if fresh
        if (
            _cache.get("key") == cache_key
            and _cache["data"] is not None
            and (now - _cache["timestamp"]) < CACHE_TTL
        ):
            return _cache["data"]

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    f"{CG_BASE}/coins/markets",
                    params={
                        "vs_currency": "usd",
                        "order": "market_cap_desc",
                        "per_page": str(per_page),
                        "page": str(page),
                        "sparkline": str(sparkline).lower(),
                        "price_change_percentage": "1h,24h,7d",
                    },
                )

                if resp.status_code == 429:
                    logger.warning("CoinGecko rate limited — returning cached data")
                    if _cache["data"] is not None:
                        return _cache["data"]
                    return []

                if resp.status_code != 200:
                    logger.error(
                        f"CoinGecko markets error {resp.status_code}: {resp.text[:200]}"
                    )
                    if _cache["data"] is not None:
                        return _cache["data"]
                    return []

                raw = resp.json()
                coins = []
                for c in raw:
                    coins.append(
                        {
                            "id": c.get("id"),
                            "symbol": (c.get("symbol") or "").upper(),
                            "name": c.get("name"),
                            "image": c.get("image"),
                            "current_price": c.get("current_price"),
                            "market_cap": c.get("market_cap"),
                            "market_cap_rank": c.get("market_cap_rank"),
                            "total_volume": c.get("total_volume"),
                            "high_24h": c.get("high_24h"),
                            "low_24h": c.get("low_24h"),
                            "price_change_24h": c.get("price_change_24h"),
                            "price_change_percentage_24h": c.get(
                                "price_change_percentage_24h"
                            ),
                            "price_change_percentage_1h": c.get(
                                "price_change_percentage_1h_in_currency"
                            ),
                            "price_change_percentage_7d": c.get(
                                "price_change_percentage_7d_in_currency"
                            ),
                            "circulating_supply": c.get("circulating_supply"),
                            "total_supply": c.get("total_supply"),
                            "ath": c.get("ath"),
                            "ath_change_percentage": c.get("ath_change_percentage"),
                            "sparkline_7d": (c.get("sparkline_in_7d") or {}).get(
                                "price"
                            ),
                        }
                    )

                # Update cache
                _cache["key"] = cache_key
                _cache["data"] = coins
                _cache["timestamp"] = now

                logger.info(f"Fetched {len(coins)} coins from CoinGecko markets")
                return coins

        except httpx.TimeoutException:
            logger.error("CoinGecko markets request timed out")
        except Exception as e:
            logger.error(f"CoinGecko markets error: {e}", exc_info=True)

        # Return stale cache on error
        if _cache["data"] is not None:
            return _cache["data"]
        return []

    async def get_prices_for_symbols(
        self, symbols: List[str]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Get current price data for a list of symbols from cached market data.
        Useful for enriching signal/trending data with real prices.
        """
        coins = await self.get_top_coins()
        result: Dict[str, Dict[str, Any]] = {}
        symbol_set = {s.upper() for s in symbols}

        for coin in coins:
            sym = coin["symbol"]
            if sym in symbol_set:
                result[sym] = {
                    "price": coin["current_price"],
                    "price_change_24h": coin["price_change_percentage_24h"],
                    "market_cap": coin["market_cap"],
                    "volume_24h": coin["total_volume"],
                    "image": coin["image"],
                    "name": coin["name"],
                }

        return result

    async def get_trending_coins(self) -> List[Dict[str, Any]]:
        """
        Get trending coins from CoinGecko /search/trending,
        enriched with real price data from our cached market data.
        """
        now = time.time()
        if (
            _trending_cache["data"] is not None
            and (now - _trending_cache["timestamp"]) < CACHE_TTL
        ):
            return _trending_cache["data"]

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{CG_BASE}/search/trending")
                if resp.status_code == 429:
                    logger.warning("CoinGecko trending rate limited")
                    return _trending_cache.get("data") or []
                if resp.status_code != 200:
                    logger.warning(f"CoinGecko trending error {resp.status_code}")
                    return _trending_cache.get("data") or []

                data = resp.json()
                coins_raw = data.get("coins", [])

                # Enrich with prices from cached market data
                cached_coins = await self.get_top_coins()
                price_map = {c["symbol"]: c for c in cached_coins}

                result = []
                for entry in coins_raw:
                    item = entry.get("item", {})
                    symbol = (item.get("symbol") or "").upper()

                    # Try enrichment from our market cache first
                    market = price_map.get(symbol, {})
                    item_data = item.get("data", {})
                    price_change_raw = item_data.get(
                        "price_change_percentage_24h", {}
                    )

                    coin = {
                        "id": item.get("id"),
                        "symbol": symbol,
                        "name": item.get("name"),
                        "image": market.get("image")
                        or item.get("large")
                        or item.get("thumb"),
                        "market_cap_rank": market.get("market_cap_rank")
                        or item.get("market_cap_rank"),
                        "current_price": market.get("current_price")
                        or item_data.get("price"),
                        "price_change_percentage_24h": market.get(
                            "price_change_percentage_24h"
                        )
                        or (
                            price_change_raw.get("usd")
                            if isinstance(price_change_raw, dict)
                            else price_change_raw
                        ),
                        "market_cap": market.get("market_cap"),
                        "total_volume": market.get("total_volume"),
                        "sparkline_7d": market.get("sparkline_7d"),
                        "score": item.get("score", 0),
                    }
                    result.append(coin)

                _trending_cache["data"] = result
                _trending_cache["timestamp"] = now
                logger.info(
                    f"Fetched {len(result)} trending coins from CoinGecko"
                )
                return result

        except httpx.TimeoutException:
            logger.warning("CoinGecko trending request timed out")
        except Exception as e:
            logger.debug(f"CoinGecko trending error: {e}")

        return _trending_cache.get("data") or []

    async def get_global_stats(self) -> Dict[str, Any]:
        """Get global crypto market statistics."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{CG_BASE}/global")
                if resp.status_code == 200:
                    data = resp.json().get("data", {})
                    return {
                        "total_market_cap_usd": data.get("total_market_cap", {}).get(
                            "usd"
                        ),
                        "total_volume_24h_usd": data.get("total_volume", {}).get(
                            "usd"
                        ),
                        "market_cap_change_24h_pct": data.get(
                            "market_cap_change_percentage_24h_usd"
                        ),
                        "active_cryptocurrencies": data.get(
                            "active_cryptocurrencies"
                        ),
                        "btc_dominance": data.get("market_cap_percentage", {}).get(
                            "btc"
                        ),
                        "eth_dominance": data.get("market_cap_percentage", {}).get(
                            "eth"
                        ),
                    }
        except Exception as e:
            logger.debug(f"CoinGecko global stats error: {e}")
        return {}


# Singleton
market_service = MarketService()

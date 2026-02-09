"""
CoinGecko API service — free tier, no API key required.

Provides:
  - Price lookup by symbol  (via /search → /simple/price)
  - 24 h OHLC candlestick data (via /coins/{id}/ohlc)

Rate limit: ~10-30 calls/min on the free tier.
We keep an in-memory symbol→id cache to minimise search calls.
"""
import logging
import asyncio
import time
from typing import Dict, Any, Optional, List, Tuple

import httpx

logger = logging.getLogger(__name__)

CG_BASE = "https://api.coingecko.com/api/v3"

# Pre-seeded map so top coins never need a /search call
_SYMBOL_TO_ID: Dict[str, str] = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "SOL": "solana",
    "BNB": "binancecoin",
    "XRP": "ripple",
    "ADA": "cardano",
    "DOGE": "dogecoin",
    "DOT": "polkadot",
    "AVAX": "avalanche-2",
    "MATIC": "matic-network",
    "LINK": "chainlink",
    "UNI": "uniswap",
    "SHIB": "shiba-inu",
    "ATOM": "cosmos",
    "LTC": "litecoin",
    "NEAR": "near",
    "ARB": "arbitrum",
    "OP": "optimism",
    "APT": "aptos",
    "SUI": "sui",
    "SEI": "sei-network",
    "TIA": "celestia",
    "INJ": "injective-protocol",
    "FET": "fetch-ai",
    "RNDR": "render-token",
    "PEPE": "pepe",
    "WIF": "dogwifcoin",
    "BONK": "bonk",
    "FLOKI": "floki",
    "TRUMP": "official-trump",
    "USDT": "tether",
    "USDC": "usd-coin",
    "DAI": "dai",
    "WBTC": "wrapped-bitcoin",
    "TRX": "tron",
    "TON": "the-open-network",
    "ETC": "ethereum-classic",
    "XLM": "stellar",
    "XMR": "monero",
    "KAS": "kaspa",
    "HBAR": "hedera-hashgraph",
    "VET": "vechain",
    "FIL": "filecoin",
    "AAVE": "aave",
    "GRT": "the-graph",
    "ALGO": "algorand",
    "STX": "stacks",
}


class CoinGeckoService:
    """Lightweight async CoinGecko client (free tier)."""

    def __init__(self) -> None:
        self._id_cache: Dict[str, Optional[str]] = dict(_SYMBOL_TO_ID)
        # Rate limiting state (lazy initialized)
        self._last_call_time = 0.0
    
    @property
    def lock(self) -> asyncio.Lock:
        if not hasattr(self, "_lock"):
            self._lock = asyncio.Lock()
        return self._lock

    async def _safe_get(self, url: str, params: Dict[str, Any] = None) -> httpx.Response:
        """Rate-limited GET request wrapper (mutex + delay)."""
        async with self.lock:
            now = time.time()
            # Enforce strict interval (e.g. 1.2s -> ~50 req/min max)
            # Free tier is ~10-30 req/min officially, but bursts allowed.
            # 1.5s = 40 req/min. 2.0s = 30 req/min.
            # Using 1.5s to be safe but responsive.
            elapsed = now - self._last_call_time
            if elapsed < 1.5:
                await asyncio.sleep(1.5 - elapsed)
            
            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    resp = await client.get(url, params=params)
                self._last_call_time = time.time()
                return resp
            except Exception:
                self._last_call_time = time.time()
                raise

    # ------------------------------------------------------------------
    # Symbol → CoinGecko ID resolution
    # ------------------------------------------------------------------

    async def _resolve_id(self, symbol: str) -> Optional[str]:
        sym = symbol.upper()
        if sym in self._id_cache:
            return self._id_cache[sym]

        # Try /search
        try:
            resp = await self._safe_get(f"{CG_BASE}/search", params={"query": sym})
            
            if resp.status_code == 200:
                coins = resp.json().get("coins", [])
                found_id = None
                # Exact match check
                for c in coins:
                    if c.get("symbol", "").upper() == sym:
                        found_id = c["id"]
                        break
                
                if found_id:
                    self._id_cache[sym] = found_id
                    return found_id
                else:
                    self._id_cache[sym] = None
                    return None
            elif resp.status_code == 429:
                logger.warning(f"CoinGecko rate limit hit for {sym}")
                return None
        except Exception as e:
            logger.debug(f"CoinGecko search failed for {sym}: {e}")

        # Do NOT cache None here for errors/rate-limits/timeouts
        return None

    # ------------------------------------------------------------------
    # Contract address lookup
    # ------------------------------------------------------------------

    async def lookup_by_contract(
        self, address: str, platform: str
    ) -> Optional[Dict[str, Any]]:
        """
        Look up a token by contract address on a specific platform.

        ``platform`` must be a CoinGecko asset-platform id, e.g.
        ``"ethereum"``, ``"tron"``, ``"solana"``, ``"binance-smart-chain"``.

        Returns a dict compatible with ``TokenSearchResult`` or ``None``.
        """
        try:
            resp = await self._safe_get(
                f"{CG_BASE}/coins/{platform}/contract/{address}",
            )
            if resp.status_code == 404:
                return None
            if resp.status_code == 429:
                logger.warning("CoinGecko rate limit during contract lookup")
                return None
            if resp.status_code != 200:
                logger.warning(
                    f"CoinGecko contract lookup {resp.status_code}"
                )
                return None

            data = resp.json()
            market = data.get("market_data") or {}
            current = market.get("current_price") or {}
            change = market.get("price_change_percentage_24h")
            mcap = market.get("market_cap") or {}
            vol = market.get("total_volume") or {}
            img = data.get("image") or {}

            return {
                "symbol": (data.get("symbol") or "").upper(),
                "name": data.get("name", ""),
                "address": address,
                "chain": platform,
                "price_usd": current.get("usd"),
                "price_change_24h": change,
                "market_cap": mcap.get("usd"),
                "volume_24h": vol.get("usd"),
                "logo": img.get("large") or img.get("small"),
                "market_cap_rank": data.get("market_cap_rank"),
                "decimals": None,
            }
        except Exception as e:
            logger.error(f"CoinGecko contract lookup error: {e}")
            return None

    # ------------------------------------------------------------------
    # Prices
    # ------------------------------------------------------------------

    async def get_prices(
        self, symbols: List[str]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Get USD price + 24 h change for a list of symbols.

        Returns ``{SYMBOL: {price_usd, price_change_24h, ...}}``
        """
        # Resolve all IDs first
        id_map: Dict[str, str] = {}  # cg_id → SYMBOL
        for sym in symbols:
            cg_id = await self._resolve_id(sym)
            if cg_id:
                id_map[cg_id] = sym.upper()

        if not id_map:
            return {}

        results: Dict[str, Dict[str, Any]] = {}
        try:
            ids_csv = ",".join(id_map.keys())
            resp = await self._safe_get(
                f"{CG_BASE}/coins/markets",
                params={
                    "vs_currency": "usd",
                    "ids": ids_csv,
                    "price_change_percentage": "24h",
                },
            )
            if resp.status_code != 200:
                logger.warning(f"CoinGecko price error {resp.status_code}")
                return results

            data = resp.json()
            for coin in data:
                cg_id = coin.get("id", "")
                sym = id_map.get(cg_id, "").upper()
                if not sym:
                    continue
                price = coin.get("current_price")
                if price is not None:
                    results[sym] = {
                        "symbol": sym,
                        "token_name": coin.get("name", sym),
                        "price_usd": price,
                        "price_change_24h": coin.get("price_change_percentage_24h"),
                        "market_cap": coin.get("market_cap"),
                        "volume_24h": coin.get("total_volume"),
                        "token_logo": coin.get("image"),
                        "cmc_rank": coin.get("market_cap_rank"),
                    }
        except Exception as e:
            logger.error(f"CoinGecko price fetch error: {e}")

        return results

    # ------------------------------------------------------------------
    # OHLC history (for candlestick charts)
    # ------------------------------------------------------------------

    async def get_ohlc(
        self, symbol: str, days: int = 1
    ) -> List[Dict[str, Any]]:
        """
        Get OHLC candlestick data from CoinGecko.

        For ``days=1`` CoinGecko returns 30-minute candles (≈48 candles).

        Returns list of ``{t: ISO-string, o, h, l, c}`` dicts.
        Raises on rate-limit or transient API errors so callers can
        decide whether to cache or retry.
        """
        cg_id = await self._resolve_id(symbol)
        if not cg_id:
            return []

        resp = await self._safe_get(
            f"{CG_BASE}/coins/{cg_id}/ohlc",
            params={"vs_currency": "usd", "days": str(days)},
        )

        if resp.status_code == 429:
            logger.warning(f"CoinGecko OHLC rate limit for {symbol}")
            raise Exception("Rate limit exceeded — try again shortly")

        if resp.status_code != 200:
            logger.warning(f"CoinGecko OHLC {resp.status_code} for {symbol}")
            raise Exception(f"CoinGecko API error {resp.status_code}")

        raw = resp.json()  # [[timestamp_ms, o, h, l, c], ...]
        candles: List[Dict[str, Any]] = []
        for row in raw:
            if len(row) >= 5:
                from datetime import datetime, timezone

                ts = datetime.fromtimestamp(
                    row[0] / 1000, tz=timezone.utc
                )
                candles.append(
                    {
                        "t": ts.isoformat(),
                        "o": row[1],
                        "h": row[2],
                        "l": row[3],
                        "c": row[4],
                    }
                )
        return candles


# Singleton
coingecko_service = CoinGeckoService()

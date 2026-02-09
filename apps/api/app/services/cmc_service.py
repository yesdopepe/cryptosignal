"""
CoinMarketCap API service for real-time cryptocurrency price data.

Uses the free Basic plan endpoints:
  - /v2/cryptocurrency/quotes/latest  (batched by symbol, up to 120 symbols)
  - /v1/cryptocurrency/map            (symbol → CMC ID mapping)

Rate limits (free tier): 30 calls/min, 10,000 calls/month.
We batch all tracked symbols into a single call to stay well within limits.
"""
import logging
from typing import Dict, Any, Optional, List

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

CMC_BASE_URL = "https://pro-api.coinmarketcap.com"


class CoinMarketCapService:
    """Async service for CoinMarketCap API."""

    def __init__(self):
        self.api_key = settings.coinmarketcap_api_key
        if not self.api_key:
            logger.warning("COINMARKETCAP_API_KEY not set. CMC features disabled.")

    @property
    def is_available(self) -> bool:
        return bool(self.api_key)

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    async def get_quotes_by_symbols(
        self, symbols: List[str]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Fetch latest quotes for a list of token symbols in one API call.

        Returns a dict keyed by uppercase symbol, each value containing:
          symbol, name, price_usd, percent_change_24h, market_cap,
          volume_24h, logo (cmc image url), cmc_rank, last_updated
        """
        if not self.api_key or not symbols:
            return {}

        # Deduplicate & uppercase
        unique = sorted(set(s.upper() for s in symbols))

        # CMC allows up to 120 symbols per call
        results: Dict[str, Dict[str, Any]] = {}
        for batch in _chunks(unique, 120):
            batch_result = await self._fetch_quotes(batch)
            results.update(batch_result)

        return results

    async def get_quote(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get a single token quote."""
        quotes = await self.get_quotes_by_symbols([symbol])
        return quotes.get(symbol.upper())

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _fetch_quotes(
        self, symbols: List[str]
    ) -> Dict[str, Dict[str, Any]]:
        """Call CMC /v2/cryptocurrency/quotes/latest for a batch of symbols."""
        results: Dict[str, Dict[str, Any]] = {}

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    f"{CMC_BASE_URL}/v2/cryptocurrency/quotes/latest",
                    headers={
                        "X-CMC_PRO_API_KEY": self.api_key,
                        "Accept": "application/json",
                    },
                    params={
                        "symbol": ",".join(symbols),
                        "convert": "USD",
                    },
                )

                if resp.status_code != 200:
                    logger.error(
                        f"CMC API error {resp.status_code}: {resp.text[:300]}"
                    )
                    return results

                body = resp.json()
                data = body.get("data", {})

                for symbol_key, entries in data.items():
                    # v2 returns a list per symbol (multiple tokens can share a symbol)
                    if not isinstance(entries, list):
                        entries = [entries]

                    # Skip if CMC returned an empty list for this symbol
                    if not entries:
                        continue

                    # Pick the highest-ranked (lowest cmc_rank) entry
                    best = min(
                        entries,
                        key=lambda e: e.get("cmc_rank") or 999999,
                    )

                    quote = (best.get("quote") or {}).get("USD", {})
                    cmc_id = best.get("id")

                    results[symbol_key.upper()] = {
                        "symbol": best.get("symbol", symbol_key),
                        "token_name": best.get("name", ""),
                        "price_usd": quote.get("price"),
                        "price_change_24h": quote.get("percent_change_24h"),
                        "market_cap": quote.get("market_cap"),
                        "volume_24h": quote.get("volume_24h"),
                        "token_logo": (
                            f"https://s2.coinmarketcap.com/static/img/coins/64x64/{cmc_id}.png"
                            if cmc_id
                            else None
                        ),
                        "cmc_rank": best.get("cmc_rank"),
                        "last_updated": quote.get("last_updated", ""),
                    }

        except httpx.TimeoutException:
            logger.error("CMC API request timed out")
        except Exception as e:
            logger.error(f"CMC API error: {e}", exc_info=True)

        return results


def _chunks(lst: List[str], n: int):
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i : i + n]


# Singleton
cmc_service = CoinMarketCapService()

"""
Real-time token price tracker service.

- Prices:     CoinMarketCap batched quote (one call per cycle, every 60 s)
- Delivery:   WebSocket push to each authenticated user

Falls back gracefully when CMC key is not set.
"""
import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List, Set
from collections import defaultdict, deque

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_maker
from app.models.tracked_token import TrackedToken

logger = logging.getLogger(__name__)

# How often we fetch fresh prices from CMC (seconds)
PRICE_REFRESH_INTERVAL = 60
# Max recent transfers kept in memory per token
MAX_TRANSFERS_PER_TOKEN = 25


class TokenPriceTracker:
    """
    Centralized service that tracks prices & on-chain activity
    for all user-tracked tokens.
    """

    def __init__(self):
        # Price cache:  "SYMBOL" -> CMC quote dict
        self._prices: Dict[str, Dict[str, Any]] = {}
        # User subscription map:  user_id -> set of SYMBOL keys
        self._subscribers: Dict[int, Set[str]] = defaultdict(set)
        # Recent transfers per address:
        #   address_lower -> deque of transfer dicts
        self._transfers: Dict[str, deque] = defaultdict(
            lambda: deque(maxlen=MAX_TRANSFERS_PER_TOKEN)
        )
        # address -> symbol mapping for quick lookup
        self._addr_to_symbol: Dict[str, str] = {}
        # Price history for candlestick charts: SYMBOL -> deque of {t, p}
        self._price_history: Dict[str, deque] = defaultdict(
            lambda: deque(maxlen=500)
        )
        self._running = False
        self._task: Optional[asyncio.Task] = None

    @property
    def is_running(self) -> bool:
        return self._running

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self):
        """Start the background price-refresh loop."""
        if self._running:
            return
        self._running = True
        # Do the first fetch synchronously so REST is ready immediately
        try:
            await self._refresh_prices()
            logger.info("✅ Initial price fetch complete (%d symbols cached)", len(self._prices))
        except Exception as e:
            logger.error(f"Initial price fetch failed: {e}")
        self._task = asyncio.create_task(self._run_loop())
        logger.info("🔄 Token price tracker started (CMC+CG, every %ds)", PRICE_REFRESH_INTERVAL)

    async def stop(self):
        """Stop the background loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("⏹️ Token price tracker stopped")

    # ------------------------------------------------------------------
    # Background loop — CMC batched price fetch
    # ------------------------------------------------------------------

    async def _run_loop(self):
        while self._running:
            try:
                await self._refresh_prices()
            except Exception as e:
                logger.error(f"Price refresh error: {e}", exc_info=True)
            await asyncio.sleep(PRICE_REFRESH_INTERVAL)

    async def _get_all_tracked_tokens(self) -> List[Dict[str, Any]]:
        """Load all active tracked tokens from DB."""
        try:
            async with async_session_maker() as session:
                q = select(
                    TrackedToken.symbol,
                    TrackedToken.chain,
                    TrackedToken.address,
                    TrackedToken.user_id,
                ).where(TrackedToken.is_active == True)
                rows = (await session.execute(q)).all()
                return [
                    {
                        "symbol": r.symbol,
                        "chain": r.chain,
                        "address": r.address,
                        "user_id": r.user_id,
                    }
                    for r in rows
                ]
        except Exception as e:
            logger.error(f"Failed to query tracked tokens: {e}")
            return []

    async def _refresh_prices(self):
        tokens = await self._get_all_tracked_tokens()
        if not tokens:
            return

        # Rebuild subscriber map
        self._subscribers.clear()
        self._addr_to_symbol.clear()
        symbols: Set[str] = set()
        for t in tokens:
            sym = t["symbol"].upper()
            symbols.add(sym)
            self._subscribers[t["user_id"]].add(sym)
            if t.get("address"):
                self._addr_to_symbol[t["address"].lower()] = sym

        # --- CMC batch call ---
        from app.services.cmc_service import cmc_service

        if cmc_service.is_available:
            # Filter for valid alphanumeric symbols only to prevent CMC 400 errors
            # (e.g. exclude "CA:0x..." placeholders)
            cmc_symbols = [s for s in symbols if s.isalnum()]
            
            quotes = await cmc_service.get_quotes_by_symbols(cmc_symbols)
            now_iso = datetime.utcnow().isoformat()
            for sym, data in quotes.items():
                if data.get("price_usd") is not None:
                    self._prices[sym] = {
                        **data,
                        "updated_at": now_iso,
                    }
                    self._price_history[sym].append(
                        {"t": now_iso, "p": data["price_usd"]}
                    )

        # --- CoinGecko fallback for any symbols still missing ---
        missing = [s for s in symbols if s not in self._prices or self._prices[s].get("price_usd") is None]
        if missing:
            await self._fallback_coingecko_prices(missing)

        # --- Moralis fallback for remaining EVM tokens with addresses ---
        # still_missing = [s for s in symbols if s not in self._prices or self._prices[s].get("price_usd") is None]
        # if still_missing:
        #    await self._fallback_moralis_prices(tokens, still_missing)

    async def _fallback_coingecko_prices(self, symbols):
        """Use CoinGecko free API as price fallback."""
        from app.services.coingecko_service import coingecko_service

        try:
            quotes = await coingecko_service.get_prices(list(symbols))
            now_iso = datetime.utcnow().isoformat()
            for sym, data in quotes.items():
                if data.get("price_usd") is not None:
                    self._prices[sym] = {
                        **data,
                        "updated_at": now_iso,
                    }
                    self._price_history[sym].append(
                        {"t": now_iso, "p": data["price_usd"]}
                    )
                    logger.debug(f"CoinGecko price for {sym}: ${data['price_usd']}")
        except Exception as e:
            logger.debug(f"CoinGecko fallback error: {e}")

    async def _fallback_moralis_prices(self, tokens, symbols):
        """Use Moralis as price source when CMC/CoinGecko didn't cover a symbol."""
        # Moralis integration removed.
        pass

    # ------------------------------------------------------------------
    # Dynamic Updates (called by API)
    # ------------------------------------------------------------------

    async def add_subscription(self, user_id: int, symbol: str, address: Optional[str] = None):
        """
        Register a new tracking subscription immediately without waiting for the loop.
        Triggers an immediate price fetch if the token is new to the system.
        """
        sym = symbol.upper()
        if user_id not in self._subscribers:
            self._subscribers[user_id] = set()
        
        self._subscribers[user_id].add(sym)
        
        if address:
            self._addr_to_symbol[address.lower()] = sym

        # If we don't have a cached price, fetch it now
        if sym not in self._prices:
            logger.info(f"⚡ Instant fetch triggered for new token: {sym}")
            # Run in background to not block the API request
            asyncio.create_task(self._fetch_single_token(sym))

    async def remove_subscription(self, user_id: int, symbol: str):
        """Remove a subscription immediately."""
        sym = symbol.upper()
        if user_id in self._subscribers and sym in self._subscribers[user_id]:
            self._subscribers[user_id].discard(sym)

    async def _fetch_single_token(self, symbol: str):
        """Fetch price for a single token (CoinGecko fallback first for speed/cost)."""
        data = None

        # Try CoinGecko first as it's often more flexible with symbols
        try:
            from app.services.coingecko_service import coingecko_service
            results = await coingecko_service.get_prices([symbol])
            data = results.get(symbol.upper())
        except Exception as e:
            logger.debug(f"CoinGecko single fetch failed for {symbol}: {e}")

        # Try CMC if CG failed
        if not data or data.get("price_usd") is None:
            try:
                from app.services.cmc_service import cmc_service
                if cmc_service.is_available and symbol.isalnum():
                    quotes = await cmc_service.get_quotes_by_symbols([symbol])
                    data = quotes.get(symbol.upper())
            except Exception as e:
                logger.debug(f"CMC single fetch failed for {symbol}: {e}")

        if data and data.get("price_usd") is not None:
            now_iso = datetime.utcnow().isoformat()
            self._prices[symbol] = {
                **data,
                "updated_at": now_iso,
            }
            self._price_history[symbol].append(
                {"t": now_iso, "p": data["price_usd"]}
            )
            logger.info(f"⚡ Instant price for {symbol}: ${data['price_usd']}")
        else:
            logger.warning(f"Could not fetch price for {symbol} from any source")

    # ------------------------------------------------------------------
    # Moralis Stream event handler (called by webhook router)
    # ------------------------------------------------------------------

    async def handle_stream_event(self, payload: Dict[str, Any]):
        """
        Process an incoming Moralis Streams webhook payload.

        Extracts ERC20 transfers, matches them against tracked addresses,
        caches the activity and broadcasts to relevant users.
        """
        # --- Moralis integration restored and updated for Notifications ---
        from app.services.websocket_manager import manager
        from app.services.notification_service import notification_service

        chain_id = payload.get("chainId", "0x1")
        confirmed = payload.get("confirmed", False)
        block = payload.get("block", {})
        transfers = payload.get("erc20Transfers", [])

        if not transfers:
            return

        now = datetime.utcnow().isoformat()

        for tx in transfers:
            contract = (tx.get("contract") or "").lower()
            if contract not in self._addr_to_symbol:
                continue

            symbol = self._addr_to_symbol[contract]

            transfer_data = {
                "symbol": symbol,
                "chain_id": chain_id,
                "address": contract,
                "from": tx.get("from", ""),
                "to": tx.get("to", ""),
                "value": tx.get("valueWithDecimals") or tx.get("value", "0"),
                "token_name": tx.get("tokenName", symbol),
                "token_symbol": tx.get("tokenSymbol", symbol),
                "tx_hash": tx.get("transactionHash", ""),
                "confirmed": confirmed,
                "block_number": block.get("number"),
                "block_timestamp": block.get("timestamp"),
                "timestamp": now,
            }

            # Cache locally
            self._transfers[contract].appendleft(transfer_data)

            # Broadcast to users tracking this symbol AND send email
            for user_id, syms in self._subscribers.items():
                if symbol in syms:
                    # Notify logic: WS + In-App + Email (handled by create_tracking_notification)
                    
                    # Format message
                    val_str = transfer_data.get("value", "0")
                    short_hash = f"{transfer_data['tx_hash'][:6]}...{transfer_data['tx_hash'][-4:]}"
                    msg = f"Transfer detected for {symbol} · Value: {val_str} · Tx: {short_hash}"
                    
                    await notification_service.create_tracking_notification(
                         user_id=user_id,
                         notif_type="tracked_transfer",
                         title=f"💸 Transfer Alert: {symbol}",
                         message=msg,
                         data=transfer_data,
                         token_symbol=symbol,
                         contract_address=contract
                    )

    # ------------------------------------------------------------------
    # Read API
    # ------------------------------------------------------------------

    def get_prices_for_user(self, user_id: int) -> List[Dict[str, Any]]:
        """Get cached prices for a user's tracked tokens."""
        keys = self._subscribers.get(user_id, set())
        return [self._prices[k] for k in keys if k in self._prices]

    def get_all_prices(self) -> Dict[str, Dict[str, Any]]:
        return dict(self._prices)

    def get_price(self, symbol: str) -> Optional[Dict[str, Any]]:
        return self._prices.get(symbol.upper())

    def get_transfers_for_address(self, address: str) -> List[Dict[str, Any]]:
        return list(self._transfers.get(address.lower(), []))

    def get_transfers_for_user(self, user_id: int) -> List[Dict[str, Any]]:
        """Return recent transfers across all of a user's tracked tokens."""
        keys = self._subscribers.get(user_id, set())
        out: List[Dict[str, Any]] = []
        for addr, sym in self._addr_to_symbol.items():
            if sym in keys and addr in self._transfers:
                out.extend(self._transfers[addr])
        # Sort by timestamp descending, cap at 50
        out.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        return out[:50]

    async def get_ohlc_history(self, symbol: str, days: int = 1) -> List[Dict[str, Any]]:
        """
        Get OHLC candlestick data for a token.

        First returns in-memory tick history.  If empty, falls back to
        CoinGecko 24 h OHLC endpoint (30-min candles).
        """
        in_mem = list(self._price_history.get(symbol.upper(), []))
        if in_mem:
            return in_mem

        # Fallback to CoinGecko OHLC
        try:
            from app.services.coingecko_service import coingecko_service
            return await coingecko_service.get_ohlc(symbol, days=days)
        except Exception as e:
            logger.debug(f"CoinGecko OHLC fallback failed for {symbol}: {e}")
            return []

    def get_price_history(self, symbol: str) -> List[Dict[str, Any]]:
        """Return recent price ticks for candlestick chart rendering."""
        return list(self._price_history.get(symbol.upper(), []))

    def get_all_tracked_addresses(self) -> List[str]:
        """Get all unique EVM addresses currently in the subscriber map."""
        return list(self._addr_to_symbol.keys())


# Singleton instance
token_tracker = TokenPriceTracker()

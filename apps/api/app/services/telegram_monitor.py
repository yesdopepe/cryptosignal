"""
Telegram monitoring service for crypto signal channels.
Based on telecopy patterns for robust Telegram integration.

Authentication flow:
1. User provides phone number via /api/v1/telegram/setup
2. Telegram sends code to phone
3. User provides code via /api/v1/telegram/verify  
4. If 2FA enabled, user provides password via /api/v1/telegram/verify-2fa
5. Session is saved and persists across restarts
"""
import asyncio
import sqlite3
import os
from typing import Optional, Callable, List, Dict, Any, Union
from datetime import datetime
import logging
from enum import Enum

from app.config import settings
from app.services.signal_parser import SignalParser

logger = logging.getLogger(__name__)


class AuthState(str, Enum):
    """Authentication state enumeration."""
    NOT_STARTED = "not_started"
    AWAITING_CODE = "awaiting_code"
    AWAITING_2FA = "awaiting_2fa"
    AUTHENTICATED = "authenticated"
    ERROR = "error"


class TelegramMonitor:
    """
    Monitor Telegram channels for crypto trading signals.
    
    Uses Telethon for direct Telegram API access with persistent sessions.
    Based on telecopy project patterns.
    
    Authentication is phone-based:
    1. Call setup_phone(phone) to initiate auth
    2. Call verify_code(code) with the code sent to phone
    3. Call verify_2fa(password) if 2FA is enabled
    """
    
    def __init__(self):
        self.client = None
        self.parser = SignalParser()
        self.callbacks: List[Callable] = []
        self.is_running = False
        self.is_connected = False
        self._mock_mode = False  # Mock mode removed - always use real Telegram
        self._monitor_task: Optional[asyncio.Task] = None
        self._channels: List[Union[str, int]] = []
        
        # Auth state tracking
        self._auth_state = AuthState.NOT_STARTED
        self._current_phone: Optional[str] = None
        self._phone_code_hash: Optional[str] = None
        self._auth_error: Optional[str] = None
        
        # Name resolution cache
        self._token_name_cache: Dict[str, str] = {}
        
        # Session database
        self._session_db_path = getattr(settings, 'telegram_session_db', 'telegram_session.db')
        self._init_session_db()
        
        # Load channels from settings
        self._load_channels()
    
    def _init_session_db(self):
        """Initialize the session database."""
        try:
            conn = sqlite3.connect(self._session_db_path)
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS credentials (
                    id INTEGER PRIMARY KEY,
                    phone_number TEXT UNIQUE NOT NULL,
                    api_id TEXT NOT NULL,
                    api_hash TEXT NOT NULL,
                    session_data BLOB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.commit()
            conn.close()
            logger.debug(f"Session database initialized: {self._session_db_path}")
        except Exception as e:
            logger.error(f"Failed to initialize session DB: {e}")
    
    def _load_channels(self):
        """Load channels from settings."""
        self._channels = []
        channel_list = getattr(settings, 'telegram_channel_list', [])
        
        for ch in channel_list:
            # Try to parse as integer (channel ID)
            try:
                self._channels.append(int(ch))
            except ValueError:
                # Keep as string (username)
                if not ch.startswith('@'):
                    ch = '@' + ch
                self._channels.append(ch)
        
        # Default channels if none configured
        if not self._channels:
            self._channels = [
                "@cryptowhales",
                "@moonshots", 
                "@gemhunters",
            ]
            logger.info(f"No channels configured, using defaults: {self._channels}")
        else:
            logger.info(f"Loaded {len(self._channels)} channels to monitor")
    
    async def start(self, on_signal: Optional[Callable] = None):
        """Start monitoring Telegram channels."""
        if on_signal:
            self.callbacks.append(on_signal)
        
        # Check for existing session
        session_data = self._load_session_from_db()
        if session_data:
            logger.info("Found existing session, attempting to connect...")
            try:
                await self._connect_with_session(session_data)
                return
            except Exception as e:
                logger.warning(f"Existing session invalid: {e}")
                self._auth_state = AuthState.NOT_STARTED
        
        # No valid session - wait for authentication
        if not settings.has_telegram_credentials:
            logger.warning("Telegram credentials not configured.")
            logger.info("📱 Set TELEGRAM_API_ID and TELEGRAM_API_HASH in .env")
        
        logger.info("📱 Telegram auth required. Use POST /api/v1/telegram/setup to authenticate")
        self._auth_state = AuthState.NOT_STARTED
        # No mock mode - wait for real authentication
    
    async def setup_phone(self, phone_number: str) -> Dict[str, Any]:
        """
        Start authentication with phone number.
        Sends verification code to the phone.
        
        Returns:
            dict with status, message, and auth_state
        """
        if not settings.has_telegram_credentials:
            return {
                "success": False,
                "error": "API credentials not configured. Set TELEGRAM_API_ID and TELEGRAM_API_HASH",
                "auth_state": AuthState.ERROR.value,
            }
        
        try:
            from telethon import TelegramClient
            
            self._current_phone = phone_number
            
            # Create temp session name based on phone
            session_name = f"session_{phone_number.replace('+', '').replace(' ', '')}"
            
            # Close existing client if any
            if self.client:
                try:
                    await self.client.disconnect()
                except:
                    pass
            
            self.client = TelegramClient(
                session_name,
                int(settings.telegram_api_id),
                settings.telegram_api_hash,
                flood_sleep_threshold=60,
            )
            
            await self.client.connect()
            
            # Check if already authorized
            if await self.client.is_user_authorized():
                self._auth_state = AuthState.AUTHENTICATED
                await self._save_session_to_db(phone_number)
                logger.info(f"✅ Already authenticated with {phone_number}")
                
                # Start monitoring
                asyncio.create_task(self._start_monitoring_after_auth())
                
                return {
                    "success": True,
                    "message": "Already authenticated! Starting channel monitoring...",
                    "auth_state": AuthState.AUTHENTICATED.value,
                }
            
            # Send code request
            result = await self.client.send_code_request(phone_number)
            self._phone_code_hash = result.phone_code_hash
            self._auth_state = AuthState.AWAITING_CODE
            
            logger.info(f"📱 Verification code sent to {phone_number}")
            
            return {
                "success": True,
                "message": f"Verification code sent to {phone_number}. Use /api/v1/telegram/verify to enter the code.",
                "auth_state": AuthState.AWAITING_CODE.value,
            }
            
        except ImportError:
            return {
                "success": False,
                "error": "Telethon not installed. Run: pip install telethon",
                "auth_state": AuthState.ERROR.value,
            }
        except Exception as e:
            self._auth_error = str(e)
            self._auth_state = AuthState.ERROR
            logger.error(f"Auth setup failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "auth_state": AuthState.ERROR.value,
            }
    
    async def verify_code(self, code: str) -> Dict[str, Any]:
        """
        Verify the authentication code sent to phone.
        
        Returns:
            dict with status, message, and auth_state
        """
        if self._auth_state != AuthState.AWAITING_CODE:
            return {
                "success": False,
                "error": f"Invalid state. Current state: {self._auth_state.value}. Call setup_phone first.",
                "auth_state": self._auth_state.value,
            }
        
        if not self.client or not self._current_phone:
            return {
                "success": False,
                "error": "No active authentication session. Call setup_phone first.",
                "auth_state": AuthState.NOT_STARTED.value,
            }
        
        try:
            from telethon.errors import SessionPasswordNeededError
            
            # Sign in with the code
            await self.client.sign_in(
                phone=self._current_phone,
                code=code,
                phone_code_hash=self._phone_code_hash
            )
            
            self._auth_state = AuthState.AUTHENTICATED
            await self._save_session_to_db(self._current_phone)
            logger.info(f"✅ Successfully authenticated as {self._current_phone}")
            
            # Start monitoring
            asyncio.create_task(self._start_monitoring_after_auth())
            
            return {
                "success": True,
                "message": "Successfully authenticated! Starting channel monitoring...",
                "auth_state": AuthState.AUTHENTICATED.value,
            }
            
        except SessionPasswordNeededError:
            self._auth_state = AuthState.AWAITING_2FA
            logger.info("🔐 2FA password required")
            return {
                "success": True,
                "message": "Two-factor authentication required. Use /api/v1/telegram/verify-2fa with your password.",
                "auth_state": AuthState.AWAITING_2FA.value,
                "requires_2fa": True,
            }
        except Exception as e:
            self._auth_error = str(e)
            logger.error(f"Code verification failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "auth_state": self._auth_state.value,
            }
    
    async def verify_2fa(self, password: str) -> Dict[str, Any]:
        """
        Verify 2FA password.
        
        Returns:
            dict with status, message, and auth_state
        """
        if self._auth_state != AuthState.AWAITING_2FA:
            return {
                "success": False,
                "error": f"Invalid state. Current state: {self._auth_state.value}",
                "auth_state": self._auth_state.value,
            }
        
        if not self.client:
            return {
                "success": False,
                "error": "No active authentication session",
                "auth_state": AuthState.NOT_STARTED.value,
            }
        
        try:
            await self.client.sign_in(password=password)
            
            self._auth_state = AuthState.AUTHENTICATED
            await self._save_session_to_db(self._current_phone)
            logger.info(f"✅ 2FA verified, authenticated as {self._current_phone}")
            
            # Start monitoring
            asyncio.create_task(self._start_monitoring_after_auth())
            
            return {
                "success": True,
                "message": "Successfully authenticated with 2FA! Starting channel monitoring...",
                "auth_state": AuthState.AUTHENTICATED.value,
            }
            
        except Exception as e:
            self._auth_error = str(e)
            logger.error(f"2FA verification failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "auth_state": self._auth_state.value,
            }
    
    async def _start_monitoring_after_auth(self):
        """Start channel monitoring after successful authentication."""
        # Stop mock mode if running
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        
        self._mock_mode = False
        self._monitor_task = asyncio.create_task(self._run_real_mode())
    
    async def _connect_with_session(self, session_data: dict):
        """Connect using saved session data."""
        from telethon import TelegramClient, events
        
        phone = session_data['phone_number']
        session_blob = session_data['session_data']
        
        # Write session to temp file
        session_name = f"session_{phone.replace('+', '').replace(' ', '')}"
        session_file = f"{session_name}.session"
        
        with open(session_file, 'wb') as f:
            f.write(session_blob)
        
        self.client = TelegramClient(
            session_name,
            int(settings.telegram_api_id),
            settings.telegram_api_hash,
            flood_sleep_threshold=60,
        )
        
        await self.client.connect()
        
        if not await self.client.is_user_authorized():
            raise Exception("Session expired or invalid")
        
        self._current_phone = phone
        self._auth_state = AuthState.AUTHENTICATED
        self._mock_mode = False
        
        logger.info(f"✅ Connected with saved session for {phone}")
        
        # Start monitoring
        self._monitor_task = asyncio.create_task(self._run_real_mode())
    
    async def _run_real_mode(self):
        """Start real Telegram monitoring with Telethon."""
        try:
            from telethon import events
            
            if not self.client or not await self.client.is_user_authorized():
                logger.error("Client not authorized. Use setup_phone() first.")
                return
            
            self.is_connected = True
            self.is_running = True
            logger.info("✅ Telegram client connected and authorized")
            
            # Resolve channel entities
            resolved_channels = []
            for channel in self._channels:
                try:
                    entity = await self.client.get_entity(channel)
                    resolved_channels.append(entity)
                    logger.info(f"  📡 Monitoring: {getattr(entity, 'title', channel)}")
                except Exception as e:
                    logger.error(f"  ❌ Failed to resolve channel {channel}: {e}")
            
            if not resolved_channels:
                logger.warning("No channels resolved. Add channels via settings or API.")
                logger.info("Listening for messages from any chat (DMs, groups you're in)...")
                # Listen to all chats instead of specific channels
                resolved_channels = None
            
            # Register message handler
            @self.client.on(events.NewMessage(chats=resolved_channels))
            async def message_handler(event):
                try:
                    await self._handle_message(event)
                except Exception as e:
                    logger.error(f"Error handling message: {e}")
            
            channel_count = len(resolved_channels) if resolved_channels else "all"
            logger.info(f"🎯 Listening for messages from {channel_count} channels...")
            
            # Keep client running
            await self.client.run_until_disconnected()
            
        except Exception as e:
            logger.error(f"Telegram connection error: {e}")
            self.is_connected = False
            self.is_running = False
    
    async def _resolve_token_name(self, symbol: str) -> str:
        """Resolve token name using cache -> tracker -> CMC."""
        if not symbol:
            return "Unknown"
            
        upper_sym = symbol.upper()
        
        # 1. Check local cache
        if upper_sym in self._token_name_cache:
            return self._token_name_cache[upper_sym]
            
        # 2. Check token_tracker cache (fast, in-memory)
        from app.services.token_tracker import token_tracker
        price_data = token_tracker.get_price(upper_sym)
        if price_data and price_data.get('token_name'):
            name = price_data['token_name']
            self._token_name_cache[upper_sym] = name
            return name
            
        # 3. Check CMC service (network call)
        from app.services.cmc_service import cmc_service
        if cmc_service.is_available:
            try:
                # We can use get_quote which fetches single token
                quote = await cmc_service.get_quote(upper_sym)
                if quote and quote.get('token_name'):
                    name = quote['token_name']
                    self._token_name_cache[upper_sym] = name
                    return name
            except Exception as e:
                logger.debug(f"Failed to resolve name for {upper_sym}: {e}")
                
        return symbol  # Fallback to symbol if name not found

    async def _handle_message(self, event):
        """Process a new message from Telegram (global monitor)."""
        message = event.message

        if not message or not message.text:
            return

        chat = await event.get_chat()
        channel_name = getattr(chat, 'title', str(event.chat_id))
        channel_id = event.chat_id
        text = message.text

        logger.debug(f"New message from {channel_name}: {text[:100]}...")

        # Parse → validate (relaxed: contract address OR token symbol is enough)
        parsed = self.parser.parse_message(text, channel_name)

        if parsed and self.parser.validate_signal(parsed):
            # Try to resolve better token name if unknown or same as symbol
            sym = parsed.get('token_symbol')
            name = parsed.get('token_name')
            
            if sym and (name == "Unknown" or name == sym):
                resolved_name = await self._resolve_token_name(sym)
                if resolved_name != "Unknown" and resolved_name != sym:
                    parsed['token_name'] = resolved_name

            parsed['channel_id'] = abs(channel_id)
            parsed['raw_message_id'] = message.id
            parsed['source'] = 'telegram'

            signal_type = parsed.get('signal_type', 'token_mention')
            logger.info(
                f"✅ [{signal_type}] {parsed['token_symbol']} from {channel_name}"
            )

            await self._notify_callbacks(parsed)
    
    async def _run_mock_mode(self):
        """Run mock mode that generates synthetic messages."""
        import random
        
        logger.info("🎭 Starting Telegram monitor in MOCK mode")
        self.is_running = True
        self._mock_mode = True
        
        mock_messages = [
            "🚀 $BTC looking extremely bullish! Entry at $67000. Target: $75000. DYOR!",
            "📈 Strong buy signal on $ETH. Entry: $3500. TP1: $4000, TP2: $4500.",
            "💎 $SOL gem alert! Current: $180. Whale activity spotted. Entry now!",
            "⚠️ $DOGE showing weakness at $0.15. Consider taking profits.",
            "🔥 $PEPE breaking out! Entry: $0.000012. Target: 100% gains!",
            "👀 Watching $LINK at $18. Buy the dip! SL: $16, TP: $25.",
            "📉 Bearish on $MATIC. Current: $0.90. Avoid for now.",
            "⚡ $AVAX alpha: Entry $40. Chart setup looks prime!",
            "🟢 $DOT accumulation zone. Entry: $7.50. Target: $12.",
            "💰 $SHIB memecoin play. Entry: $0.000025. Moon potential!",
            "🎯 $ARB looking strong. Entry $1.20, SL $1.00, TP $2.00.",
            "📊 Technical breakout on $INJ. Entry $25, target $40!",
        ]
        
        mock_channels = [
            "CryptoWhales", "MoonShots", "GemHunters",
            "DeFiSignals", "AltcoinDaily", "PumpAlerts",
        ]
        
        while self.is_running:
            await asyncio.sleep(random.uniform(10, 30))  # Every 10-30 seconds
            
            if not self.is_running:
                break
            
            message = random.choice(mock_messages)
            channel = random.choice(mock_channels)
            
            parsed = self.parser.parse_message(message, channel)
            
            if parsed and self.parser.validate_signal(parsed):
                parsed['channel_id'] = hash(channel) % 1000000
                parsed['raw_message_id'] = int(datetime.utcnow().timestamp() * 1000)
                parsed['source'] = 'telegram'
                
                signal_type = parsed.get('signal_type', 'token_mention')
                logger.info(f"📨 Mock [{signal_type}]: {parsed['token_symbol']} from {channel}")
                await self._notify_callbacks(parsed)
    
    async def _notify_callbacks(self, signal_data: Dict[str, Any]):
        """Notify all registered callbacks of a new signal."""
        for callback in self.callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(signal_data)
                else:
                    callback(signal_data)
            except Exception as e:
                logger.error(f"Callback error: {e}")
    
    def _load_session_from_db(self) -> Optional[dict]:
        """Load Telegram session data from database."""
        try:
            if not os.path.exists(self._session_db_path):
                return None
            
            conn = sqlite3.connect(self._session_db_path)
            cursor = conn.cursor()
            cursor.execute(
                'SELECT phone_number, api_id, api_hash, session_data FROM credentials ORDER BY updated_at DESC LIMIT 1'
            )
            result = cursor.fetchone()
            conn.close()
            
            if result and result[3]:
                return {
                    'phone_number': result[0],
                    'api_id': result[1],
                    'api_hash': result[2],
                    'session_data': result[3] if isinstance(result[3], bytes) else result[3].encode(),
                }
            return None
        except Exception as e:
            logger.debug(f"Could not load session from DB: {e}")
            return None
    
    async def _save_session_to_db(self, phone_number: str):
        """Save Telegram session data to database."""
        try:
            session_name = f"session_{phone_number.replace('+', '').replace(' ', '')}"
            session_file = f'{session_name}.session'
            
            if not os.path.exists(session_file):
                logger.warning(f"Session file not found: {session_file}")
                return
            
            with open(session_file, 'rb') as f:
                session_data = f.read()
            
            conn = sqlite3.connect(self._session_db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO credentials (phone_number, api_id, api_hash, session_data, updated_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (phone_number, settings.telegram_api_id, settings.telegram_api_hash, session_data))
            
            conn.commit()
            conn.close()
            logger.info(f"✅ Session saved to database for {phone_number}")
        except Exception as e:
            logger.error(f"Could not save session to DB: {e}")
    
    async def stop(self):
        """Stop monitoring."""
        self.is_running = False
        self.is_connected = False
        
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        
        if self.client:
            await self.client.disconnect()
            self.client = None
        
        logger.info("Telegram monitor stopped")
    
    def add_callback(self, callback: Callable):
        """Add a callback for when signals are detected."""
        self.callbacks.append(callback)
    
    def remove_callback(self, callback: Callable):
        """Remove a callback."""
        if callback in self.callbacks:
            self.callbacks.remove(callback)
    
    async def add_channel(self, channel: Union[str, int]) -> bool:
        """Add a channel to monitor."""
        if channel not in self._channels:
            self._channels.append(channel)
            logger.info(f"Added channel to monitor: {channel}")
            
            # If running in real mode, we need to restart to pick up new channel
            if self.is_connected and self.client:
                logger.info("Restarting monitor to add new channel...")
                await self.stop()
                await self.start()
            
            return True
        return False
    
    async def remove_channel(self, channel: Union[str, int]) -> bool:
        """Remove a channel from monitoring."""
        if channel in self._channels:
            self._channels.remove(channel)
            logger.info(f"Removed channel from monitoring: {channel}")
            return True
        return False
    
    @property
    def channels(self) -> List[Union[str, int]]:
        """Get list of monitored channels."""
        return self._channels.copy()
    
    @property
    def mock_mode(self) -> bool:
        """Check if running in mock mode."""
        return self._mock_mode
    
    @property
    def status(self) -> dict:
        """Get monitor status."""
        return {
            "is_running": self.is_running,
            "is_connected": self.is_connected,
            "mock_mode": self._mock_mode,
            "auth_state": self._auth_state.value,
            "phone_number": self._current_phone,
            "channels_monitored": len(self._channels),
            "channels": self._channels[:10],  # First 10 for display
            "callbacks_registered": len(self.callbacks),
            "auth_error": self._auth_error,
        }
    
    async def logout(self) -> Dict[str, Any]:
        """Logout and clear session."""
        try:
            if self.client:
                await self.client.log_out()
                await self.client.disconnect()
                self.client = None
            
            # Clear session from database
            if self._current_phone:
                conn = sqlite3.connect(self._session_db_path)
                cursor = conn.cursor()
                cursor.execute('DELETE FROM credentials WHERE phone_number = ?', (self._current_phone,))
                conn.commit()
                conn.close()
            
            self._auth_state = AuthState.NOT_STARTED
            self._current_phone = None
            self._phone_code_hash = None
            self.is_connected = False
            
            logger.info("Logged out successfully")
            return {"success": True, "message": "Logged out successfully"}
        except Exception as e:
            logger.error(f"Logout error: {e}")
            return {"success": False, "error": str(e)}


# Global monitor instance
telegram_monitor = TelegramMonitor()


async def start_monitoring(on_signal: Optional[Callable] = None):
    """Start the global Telegram monitor."""
    await telegram_monitor.start(on_signal)


async def stop_monitoring():
    """Stop the global Telegram monitor."""
    await telegram_monitor.stop()

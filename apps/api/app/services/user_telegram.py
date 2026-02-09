"""
Per-user Telegram service — concurrent, non-blocking architecture.

Each user authenticates with their own Telegram account.  A shared pool of
asyncio workers processes incoming channel messages from ALL users
concurrently, deduplicating identical messages that arrive via multiple
user clients.

Architecture
────────────
  User A's Telethon Client ─→ lightweight handler ─┐
  User B's Telethon Client ─→ lightweight handler ─┤
  User C's Telethon Client ─→ lightweight handler ─┤
                                                   ▼
                                ┌─────────────────────┐
                                │   asyncio.Queue      │
                                │   (back-pressure)    │
                                └────────┬────────────┘
                                         │
                ┌────────────────────────┼───────────┐
                │  Worker 1  Worker 2  Worker 3 …    │
                │  parse → dedup → save → notify     │
                └────────────────────────────────────┘

Why this matters:
  • Telethon event handlers return in microseconds (just a put_nowait).
  • Heavy IO (SQLite writes, WebSocket broadcasts, notification creation)
    happens in the worker pool — never inside the Telethon update loop.
  • Workers share a dedup cache so the same (channel_id, message_id) is
    parsed/saved exactly once, even when N users subscribe to the same channel.
"""
import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime
import logging
from enum import Enum

from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError

from app.config import settings
from app.database import async_session_maker
from app.models import User, TelegramSession, ChannelSubscription
from app.models.channel import Channel
from app.services.signal_parser import SignalParser
from sqlalchemy import select, and_

logger = logging.getLogger(__name__)


class UserAuthState(str, Enum):
    """User's Telegram authentication state."""
    NOT_CONNECTED = "not_connected"
    AWAITING_CODE = "awaiting_code"
    AWAITING_2FA = "awaiting_2fa"
    CONNECTED = "connected"
    ERROR = "error"


class UserTelegramManager:
    """
    Manages per-user Telegram connections with concurrent, non-blocking
    channel monitoring.
    """

    _NUM_WORKERS = 4          # concurrent queue consumers
    _QUEUE_MAX = 10_000       # back-pressure limit
    _DEDUP_TTL = 600          # seconds before a dedup entry expires
    _DEDUP_SWEEP_INTERVAL = 300  # seconds between cache sweeps

    def __init__(self):
        # Active client connections  (user_id → TelegramClient)
        self._active_clients: Dict[int, TelegramClient] = {}
        # Pending auth flows         (user_id → state dict)
        self._pending_auth: Dict[int, Dict[str, Any]] = {}
        # Per-user monitoring status (user_id → counters dict)
        self._monitoring_status: Dict[int, Dict[str, Any]] = {}
        # Registered Telethon event handlers (user_id → handler callable)
        self._registered_handlers: Dict[int, Any] = {}
        # Legacy task dict (kept for graceful migration from old architecture)
        self._monitoring_tasks: Dict[int, asyncio.Task] = {}

        # Shared signal parser
        self._parser = SignalParser()

        # ── Concurrent message processing ─────────────────────────
        self._msg_queue: asyncio.Queue = asyncio.Queue(maxsize=self._QUEUE_MAX)
        self._workers: List[asyncio.Task] = []
        self._workers_started: bool = False

        # Dedup cache: (channel_id, message_id) → (parsed|None, saved:bool, ts)
        self._dedup: Dict[tuple, tuple] = {}
        self._dedup_lock = asyncio.Lock()

    # ════════════════════════════════════════════════════════════
    #  AUTH METHODS  (unchanged from original)
    # ════════════════════════════════════════════════════════════

    async def get_user_status(self, user_id: int) -> Dict[str, Any]:
        """Get a user's Telegram connection status."""
        if user_id in self._pending_auth:
            return {
                "connected": False,
                "auth_state": self._pending_auth[user_id].get(
                    "state", UserAuthState.NOT_CONNECTED
                ).value,
                "phone_number": self._pending_auth[user_id].get("phone_number"),
                "error": self._pending_auth[user_id].get("error"),
            }

        if user_id in self._active_clients:
            client = self._active_clients[user_id]
            try:
                if client.is_connected() and await client.is_user_authorized():
                    me = await client.get_me()
                    return {
                        "connected": True,
                        "auth_state": UserAuthState.CONNECTED.value,
                        "phone_number": me.phone,
                        "username": me.username,
                        "first_name": me.first_name,
                        "last_name": me.last_name,
                        "is_monitoring": user_id in self._registered_handlers,
                    }
            except Exception:
                pass

        async with async_session_maker() as db:
            result = await db.execute(
                select(TelegramSession).where(TelegramSession.user_id == user_id)
            )
            session = result.scalar_one_or_none()
            if session and session.is_authenticated:
                return {
                    "connected": False,
                    "auth_state": UserAuthState.CONNECTED.value,
                    "phone_number": session.phone_number,
                    "has_saved_session": True,
                    "is_monitoring": user_id in self._registered_handlers,
                }

        return {
            "connected": False,
            "auth_state": UserAuthState.NOT_CONNECTED.value,
            "is_monitoring": False,
        }

    async def start_auth(self, user_id: int, phone_number: str) -> Dict[str, Any]:
        """Start Telegram authentication — sends verification code."""
        if not settings.has_telegram_credentials:
            return {
                "success": False,
                "error": "Telegram API credentials not configured on server",
                "auth_state": UserAuthState.ERROR.value,
            }

        try:
            client = TelegramClient(
                StringSession(),
                int(settings.telegram_api_id),
                settings.telegram_api_hash,
                flood_sleep_threshold=60,
            )
            await client.connect()

            if await client.is_user_authorized():
                session_string = client.session.save()
                await self._save_user_session(user_id, phone_number, session_string)
                self._active_clients[user_id] = client
                asyncio.create_task(self.start_monitoring(user_id))
                return {
                    "success": True,
                    "message": "Already authenticated!",
                    "auth_state": UserAuthState.CONNECTED.value,
                }

            result = await client.send_code_request(phone_number)
            self._pending_auth[user_id] = {
                "client": client,
                "phone_number": phone_number,
                "phone_code_hash": result.phone_code_hash,
                "state": UserAuthState.AWAITING_CODE,
            }
            logger.info(f"Verification code sent to {phone_number} for user {user_id}")
            return {
                "success": True,
                "message": f"Verification code sent to {phone_number}",
                "auth_state": UserAuthState.AWAITING_CODE.value,
            }

        except Exception as e:
            logger.error(f"Auth start failed for user {user_id}: {e}")
            self._pending_auth[user_id] = {
                "state": UserAuthState.ERROR,
                "error": str(e),
                "phone_number": phone_number,
            }
            return {
                "success": False,
                "error": str(e),
                "auth_state": UserAuthState.ERROR.value,
            }

    async def verify_code(self, user_id: int, code: str) -> Dict[str, Any]:
        """Verify the authentication code sent to user's phone."""
        if user_id not in self._pending_auth:
            return {
                "success": False,
                "error": "No pending authentication. Call connect first.",
                "auth_state": UserAuthState.NOT_CONNECTED.value,
            }

        pending = self._pending_auth[user_id]
        if pending.get("state") != UserAuthState.AWAITING_CODE:
            return {
                "success": False,
                "error": f"Invalid state: {pending.get('state')}",
                "auth_state": pending.get("state", UserAuthState.ERROR).value,
            }

        client = pending.get("client")
        if not client:
            return {
                "success": False,
                "error": "Client session lost. Please start over.",
                "auth_state": UserAuthState.ERROR.value,
            }

        try:
            await client.sign_in(
                phone=pending["phone_number"],
                code=code,
                phone_code_hash=pending["phone_code_hash"],
            )
            session_string = client.session.save()
            await self._save_user_session(user_id, pending["phone_number"], session_string)
            self._active_clients[user_id] = client
            del self._pending_auth[user_id]
            logger.info(f"User {user_id} successfully authenticated with Telegram")
            asyncio.create_task(self.start_monitoring(user_id))
            return {
                "success": True,
                "message": "Successfully connected to Telegram! Background monitoring started.",
                "auth_state": UserAuthState.CONNECTED.value,
            }

        except SessionPasswordNeededError:
            pending["state"] = UserAuthState.AWAITING_2FA
            logger.info(f"2FA required for user {user_id}")
            return {
                "success": True,
                "message": "Two-factor authentication required",
                "auth_state": UserAuthState.AWAITING_2FA.value,
                "requires_2fa": True,
            }
        except PhoneCodeInvalidError:
            return {
                "success": False,
                "error": "Invalid verification code",
                "auth_state": UserAuthState.AWAITING_CODE.value,
            }
        except Exception as e:
            logger.error(f"Code verification failed for user {user_id}: {e}")
            return {
                "success": False,
                "error": str(e),
                "auth_state": UserAuthState.AWAITING_CODE.value,
            }

    async def verify_2fa(self, user_id: int, password: str) -> Dict[str, Any]:
        """Verify 2FA password for user's Telegram account."""
        if user_id not in self._pending_auth:
            return {
                "success": False,
                "error": "No pending authentication",
                "auth_state": UserAuthState.NOT_CONNECTED.value,
            }

        pending = self._pending_auth[user_id]
        if pending.get("state") != UserAuthState.AWAITING_2FA:
            return {
                "success": False,
                "error": f"Invalid state: {pending.get('state')}",
                "auth_state": pending.get("state", UserAuthState.ERROR).value,
            }

        client = pending.get("client")
        if not client:
            return {
                "success": False,
                "error": "Client session lost",
                "auth_state": UserAuthState.ERROR.value,
            }

        try:
            await client.sign_in(password=password)
            session_string = client.session.save()
            await self._save_user_session(user_id, pending["phone_number"], session_string)
            self._active_clients[user_id] = client
            del self._pending_auth[user_id]
            logger.info(f"User {user_id} authenticated with 2FA")
            asyncio.create_task(self.start_monitoring(user_id))
            return {
                "success": True,
                "message": "Successfully connected with 2FA! Background monitoring started.",
                "auth_state": UserAuthState.CONNECTED.value,
            }

        except Exception as e:
            logger.error(f"2FA verification failed for user {user_id}: {e}")
            return {
                "success": False,
                "error": str(e),
                "auth_state": UserAuthState.AWAITING_2FA.value,
            }

    async def get_user_channels(self, user_id: int) -> Dict[str, Any]:
        """Get list of channels/groups the user has joined."""
        client = await self._get_or_restore_client(user_id)
        if not client:
            return {"success": False, "error": "Not connected to Telegram", "channels": []}

        try:
            channels = []
            async for dialog in client.iter_dialogs():
                if dialog.is_channel or dialog.is_group:
                    entity = dialog.entity
                    channels.append({
                        "id": dialog.id,
                        "title": dialog.title,
                        "username": getattr(entity, "username", None),
                        "is_channel": dialog.is_channel,
                        "is_group": dialog.is_group,
                        "participants_count": getattr(entity, "participants_count", None),
                        "unread_count": dialog.unread_count,
                    })
            logger.info(f"Retrieved {len(channels)} channels for user {user_id}")
            return {"success": True, "channels": channels, "count": len(channels)}

        except Exception as e:
            logger.error(f"Failed to get channels for user {user_id}: {e}")
            return {"success": False, "error": str(e), "channels": []}

    async def disconnect(self, user_id: int) -> Dict[str, Any]:
        """Disconnect user's Telegram and clear saved session."""
        try:
            await self.stop_monitoring(user_id)

            if user_id in self._active_clients:
                client = self._active_clients[user_id]
                try:
                    await client.log_out()
                except Exception:
                    pass
                try:
                    await client.disconnect()
                except Exception:
                    pass
                del self._active_clients[user_id]

            if user_id in self._pending_auth:
                pending = self._pending_auth[user_id]
                if "client" in pending:
                    try:
                        await pending["client"].disconnect()
                    except Exception:
                        pass
                del self._pending_auth[user_id]

            async with async_session_maker() as db:
                result = await db.execute(
                    select(TelegramSession).where(TelegramSession.user_id == user_id)
                )
                session = result.scalar_one_or_none()
                if session:
                    await db.delete(session)
                    await db.commit()

            logger.info(f"User {user_id} disconnected from Telegram")
            return {"success": True, "message": "Disconnected from Telegram"}

        except Exception as e:
            logger.error(f"Disconnect failed for user {user_id}: {e}")
            return {"success": False, "error": str(e)}

    # ════════════════════════════════════════════════════════════
    #  NON-BLOCKING MONITORING
    # ════════════════════════════════════════════════════════════

    async def start_monitoring(self, user_id: int) -> Dict[str, Any]:
        """
        Register a lightweight Telethon event handler for a user's
        subscribed channels.  The handler does NO heavy work — it pushes
        raw message data onto the shared ``_msg_queue`` and returns
        immediately.  Worker coroutines do the rest.
        """
        if user_id in self._registered_handlers:
            return {"success": True, "message": "Already monitoring", "is_monitoring": True}

        await self._ensure_workers()

        client = await self._get_or_restore_client(user_id)
        if not client:
            return {
                "success": False,
                "error": "Not connected to Telegram. Connect first.",
                "is_monitoring": False,
            }

        channel_ids = await self._get_subscribed_channel_ids(user_id)

        # Resolve entities (may hit Telegram API — done once per start)
        resolved: list = []
        name_map: Dict[int, str] = {}
        for cid in channel_ids:
            try:
                entity = await client.get_entity(cid)
                resolved.append(entity)
                eid = abs(getattr(entity, "id", cid))
                title = getattr(entity, "title", str(cid))
                name_map[eid] = title
                logger.info(f"  📡 User {user_id} monitoring: {title}")
            except Exception as e:
                logger.warning(
                    f"  ⚠️ User {user_id}: Could not resolve channel {cid}: {e}"
                )

        chats_filter = resolved if resolved else None

        # Closure captures for the handler (no await, no DB, no WS)
        queue = self._msg_queue
        uid = user_id

        @client.on(events.NewMessage(chats=chats_filter))
        async def _on_new_message(event):
            msg = event.message
            if not msg or not msg.text:
                return
            cid = abs(event.chat_id)
            try:
                queue.put_nowait({
                    "user_id": uid,
                    "channel_id": cid,
                    "channel_name": name_map.get(cid, str(cid)),
                    "message_id": msg.id,
                    "text": msg.text,
                    "date": (
                        msg.date.isoformat()
                        if msg.date
                        else datetime.utcnow().isoformat()
                    ),
                })
            except asyncio.QueueFull:
                pass  # back-pressure — drop silently

        self._registered_handlers[user_id] = _on_new_message
        self._monitoring_status[user_id] = {
            "started_at": datetime.utcnow().isoformat(),
            "channels_count": len(resolved),
            "messages_processed": 0,
            "signals_detected": 0,
            "last_message_at": None,
            "errors": [],
        }

        count = len(resolved) if resolved else "all"
        # Notify via WebSocket
        try:
            from app.services.websocket_manager import manager

            await manager.send_to_user(
                user_id,
                {
                    "type": "monitoring_status",
                    "data": {
                        "is_monitoring": True,
                        "channels_count": len(resolved),
                        "message": f"Monitoring active for {count} channel(s)",
                    },
                    "timestamp": datetime.utcnow().isoformat(),
                },
            )
        except Exception:
            pass

        logger.info(f"📡 User {user_id}: Monitoring {count} channels (non-blocking)")
        return {
            "success": True,
            "message": f"Monitoring started for {count} channel(s)",
            "is_monitoring": True,
            "channels_count": len(resolved),
        }

    async def stop_monitoring(self, user_id: int) -> Dict[str, Any]:
        """Remove the event handler for a user.  Workers keep running."""
        handler = self._registered_handlers.pop(user_id, None)
        if handler and user_id in self._active_clients:
            try:
                self._active_clients[user_id].remove_event_handler(handler)
            except Exception:
                pass

        # Cancel legacy monitoring task if present (hot-migration from old arch)
        task = self._monitoring_tasks.pop(user_id, None)
        if task and not task.done():
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass

        self._monitoring_status.pop(user_id, None)

        # Notify via WebSocket
        try:
            from app.services.websocket_manager import manager

            await manager.send_to_user(
                user_id,
                {
                    "type": "monitoring_status",
                    "data": {
                        "is_monitoring": False,
                        "channels_count": 0,
                        "message": "Monitoring stopped",
                    },
                    "timestamp": datetime.utcnow().isoformat(),
                },
            )
        except Exception:
            pass

        logger.info(f"🛑 Stopped monitoring for user {user_id}")
        return {"success": True, "message": "Monitoring stopped", "is_monitoring": False}

    def get_monitoring_status(self, user_id: int) -> Dict[str, Any]:
        """Return monitoring counters for a user."""
        is_monitoring = user_id in self._registered_handlers
        status = self._monitoring_status.get(user_id, {})
        return {
            "is_monitoring": is_monitoring,
            "started_at": status.get("started_at"),
            "channels_count": status.get("channels_count", 0),
            "messages_processed": status.get("messages_processed", 0),
            "signals_detected": status.get("signals_detected", 0),
            "last_message_at": status.get("last_message_at"),
            "errors": status.get("errors", [])[-5:],
            "queue_size": self._msg_queue.qsize(),
        }

    async def refresh_monitoring(self, user_id: int) -> Dict[str, Any]:
        """Stop and restart monitoring to pick up new subscriptions."""
        await self.stop_monitoring(user_id)
        return await self.start_monitoring(user_id)

    async def restore_all_monitoring(self):
        """
        Restore monitoring for all users with saved sessions and active
        subscriptions.  Called on server startup.
        """
        try:
            async with async_session_maker() as db:
                result = await db.execute(
                    select(TelegramSession).where(
                        TelegramSession.is_authenticated == True  # noqa: E712
                    )
                )
                sessions = result.scalars().all()

                if not sessions:
                    logger.info("📡 No Telegram sessions to restore monitoring for")
                    return

                restored = 0
                for tg_session in sessions:
                    uid = tg_session.user_id
                    sub_check = await db.execute(
                        select(ChannelSubscription)
                        .where(
                            and_(
                                ChannelSubscription.user_id == uid,
                                ChannelSubscription.is_active == True,  # noqa: E712
                            )
                        )
                        .limit(1)
                    )
                    if sub_check.scalar_one_or_none():
                        try:
                            res = await self.start_monitoring(uid)
                            if res.get("success"):
                                restored += 1
                        except Exception as e:
                            logger.warning(
                                f"Failed to restore monitoring for user {uid}: {e}"
                            )

                logger.info(f"📡 Restored monitoring for {restored} user(s)")
        except Exception as e:
            logger.error(f"Failed to restore monitoring: {e}")

    # ════════════════════════════════════════════════════════════
    #  WORKER POOL  (shared across all users)
    # ════════════════════════════════════════════════════════════

    async def _ensure_workers(self):
        """Start the worker pool on first use."""
        if self._workers_started:
            return
        self._workers_started = True
        for i in range(self._NUM_WORKERS):
            t = asyncio.create_task(self._queue_worker(i), name=f"tg-worker-{i}")
            self._workers.append(t)
        self._workers.append(
            asyncio.create_task(self._dedup_cleaner(), name="tg-dedup-cleaner")
        )
        logger.info(f"🔧 Started {self._NUM_WORKERS} message-processing workers")

    async def _queue_worker(self, worker_id: int):
        """Drain the shared queue and process items."""
        while True:
            try:
                item = await self._msg_queue.get()
                try:
                    await self._process_queued_message(item)
                except Exception as e:
                    logger.error(f"Worker-{worker_id} error: {e}")
                finally:
                    self._msg_queue.task_done()
            except asyncio.CancelledError:
                break

    async def _process_queued_message(self, item: dict):
        """
        Process one message from the queue.

        1. Deduplicate — same (channel_id, message_id) parsed / saved once.
        2. Parse with SignalParser.
        3. Save signal to DB (once).
        4. Per-user notification + WebSocket push.
        """
        user_id: int = item["user_id"]
        channel_id: int = item["channel_id"]
        channel_name: str = item["channel_name"]
        message_id: int = item["message_id"]
        text: str = item["text"]
        date_str: str = item["date"]

        # ── User counters ────────────────────────────────────────
        status = self._monitoring_status.get(user_id, {})
        status["messages_processed"] = status.get("messages_processed", 0) + 1
        status["last_message_at"] = datetime.utcnow().isoformat()

        # ── Deduplication ────────────────────────────────────────
        dedup_key = (channel_id, message_id)
        async with self._dedup_lock:
            cached = self._dedup.get(dedup_key)

        if cached is not None:
            parsed, already_saved = cached[0], cached[1]
        else:
            parsed = self._parser.parse_message(text, channel_name)
            already_saved = False
            async with self._dedup_lock:
                self._dedup[dedup_key] = (
                    parsed,
                    False,
                    datetime.utcnow().timestamp(),
                )

        has_detection = parsed is not None and self._parser.validate_signal(parsed)

        # ── Save signal (once per unique message) ────────────────
        if has_detection and not already_saved:
            parsed["channel_id"] = channel_id
            parsed["raw_message_id"] = message_id
            parsed["source"] = "telegram"
            parsed["user_id"] = user_id  # Associate signal with specific user

            status["signals_detected"] = status.get("signals_detected", 0) + 1

            signal_type = parsed.get("signal_type", "token_mention")
            token_label = parsed.get("token_symbol", "Unknown")
            contracts = parsed.get("contract_addresses", [])
            ca_preview = contracts[0][:12] + "…" if contracts else ""

            logger.info(
                f"✅ [{signal_type}] {token_label} {ca_preview} "
                f"from {channel_name} (user {user_id})"
            )

            try:
                from app.main import save_signal_to_db

                await save_signal_to_db(parsed)
                # Mark as saved in dedup cache
                async with self._dedup_lock:
                    if dedup_key in self._dedup:
                        old = self._dedup[dedup_key]
                        self._dedup[dedup_key] = (old[0], True, old[2])
            except Exception as e:
                logger.error(f"Failed to save signal: {e}")

        # ── Per-user notification ────────────────────────────────
        if has_detection:
            try:
                from app.services.notification_service import notification_service

                await notification_service._create_in_app_notification(
                    user_id, parsed
                )
            except Exception as e:
                logger.error(
                    f"Failed to create notification for user {user_id}: {e}"
                )

        # ── Per-user WebSocket push (always — live feed) ─────────
        try:
            from app.services.websocket_manager import manager

            await manager.send_to_user(
                user_id,
                {
                    "type": "channel_message",
                    "data": {
                        "channel_name": channel_name,
                        "channel_id": channel_id,
                        "text": text[:500],
                        "message_id": message_id,
                        "timestamp": date_str,
                        "has_signal": has_detection,
                        "signal_type": (
                            parsed.get("signal_type") if has_detection else None
                        ),
                        "token_symbol": (
                            parsed.get("token_symbol") if has_detection else None
                        ),
                        "contract_addresses": (
                            parsed.get("contract_addresses", [])
                            if has_detection
                            else []
                        ),
                        "chain": (
                            parsed.get("chain") if has_detection else None
                        ),
                        "sentiment": (
                            parsed.get("sentiment") if has_detection else None
                        ),
                    },
                    "timestamp": datetime.utcnow().isoformat(),
                },
            )
        except Exception:
            pass

    async def _dedup_cleaner(self):
        """Periodically prune expired entries from the dedup cache."""
        while True:
            try:
                await asyncio.sleep(self._DEDUP_SWEEP_INTERVAL)
                now = datetime.utcnow().timestamp()
                async with self._dedup_lock:
                    expired = [
                        k
                        for k, v in self._dedup.items()
                        if now - v[2] > self._DEDUP_TTL
                    ]
                    for k in expired:
                        del self._dedup[k]
                    if expired:
                        logger.debug(f"Pruned {len(expired)} dedup entries")
            except asyncio.CancelledError:
                break
            except Exception:
                pass

    async def _get_subscribed_channel_ids(self, user_id: int) -> List[int]:
        """Get IDs of channels the user has actively subscribed to."""
        async with async_session_maker() as db:
            result = await db.execute(
                select(ChannelSubscription.channel_id).where(
                    and_(
                        ChannelSubscription.user_id == user_id,
                        ChannelSubscription.is_active == True,  # noqa: E712
                    )
                )
            )
            return [row[0] for row in result.all()]

    # ════════════════════════════════════════════════════════════
    #  SESSION HELPERS
    # ════════════════════════════════════════════════════════════

    async def _get_or_restore_client(
        self, user_id: int
    ) -> Optional[TelegramClient]:
        """Get active client or restore from saved session."""
        if user_id in self._active_clients:
            client = self._active_clients[user_id]
            try:
                if client.is_connected() and await client.is_user_authorized():
                    return client
            except Exception:
                pass

        async with async_session_maker() as db:
            result = await db.execute(
                select(TelegramSession).where(TelegramSession.user_id == user_id)
            )
            session = result.scalar_one_or_none()

            if not session or not session.session_data:
                return None

            try:
                session_string = session.session_data.decode("utf-8")
                client = TelegramClient(
                    StringSession(session_string),
                    int(settings.telegram_api_id),
                    settings.telegram_api_hash,
                    flood_sleep_threshold=60,
                )
                await client.connect()

                if await client.is_user_authorized():
                    self._active_clients[user_id] = client
                    logger.info(f"Restored Telegram session for user {user_id}")
                    return client
                else:
                    logger.warning(f"Saved session expired for user {user_id}")
                    return None

            except Exception as e:
                logger.error(
                    f"Failed to restore session for user {user_id}: {e}"
                )
                return None

    async def _save_user_session(
        self, user_id: int, phone_number: str, session_string: str
    ):
        """Save user's Telegram session to database."""
        async with async_session_maker() as db:
            result = await db.execute(
                select(TelegramSession).where(TelegramSession.user_id == user_id)
            )
            existing = result.scalar_one_or_none()

            if existing:
                existing.phone_number = phone_number
                existing.session_data = session_string.encode("utf-8")
                existing.is_authenticated = True
                existing.auth_state = UserAuthState.CONNECTED.value
            else:
                sess = TelegramSession(
                    user_id=user_id,
                    phone_number=phone_number,
                    session_data=session_string.encode("utf-8"),
                    is_authenticated=True,
                    auth_state=UserAuthState.CONNECTED.value,
                )
                db.add(sess)

            await db.commit()
            logger.info(f"Saved Telegram session for user {user_id}")

    async def send_to_saved_messages(
        self,
        user_id: int,
        message: str,
        parse_mode: str = "html",
    ) -> Dict[str, Any]:
        """Send a message to user's Telegram Saved Messages."""
        client = await self._get_or_restore_client(user_id)
        if not client:
            return {
                "success": False,
                "error": "Not connected to Telegram. User needs to authenticate first.",
            }

        try:
            await client.send_message(
                "me",
                message,
                parse_mode=parse_mode,
                link_preview=False,
            )
            logger.info(f"📱 Sent message to Saved Messages for user {user_id}")
            return {"success": True, "message": "Sent to Saved Messages"}

        except Exception as e:
            logger.error(
                f"Failed to send to Saved Messages for user {user_id}: {e}"
            )
            return {"success": False, "error": str(e)}

    # ════════════════════════════════════════════════════════════
    #  LIFECYCLE
    # ════════════════════════════════════════════════════════════

    async def shutdown(self):
        """Stop all monitoring, cancel workers, disconnect all clients."""
        # Remove all user handlers
        for user_id in list(self._registered_handlers.keys()):
            await self.stop_monitoring(user_id)

        # Stop worker pool
        for t in self._workers:
            t.cancel()
        if self._workers:
            await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()
        self._workers_started = False

        # Disconnect all Telethon clients
        for user_id, client in list(self._active_clients.items()):
            try:
                await client.disconnect()
            except Exception:
                pass
        self._active_clients.clear()

        logger.info("UserTelegramManager shut down")


# Global manager instance
user_telegram_manager = UserTelegramManager()

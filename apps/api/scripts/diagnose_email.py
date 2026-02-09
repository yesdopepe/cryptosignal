"""
Diagnose why emails aren't being sent when signals arrive.
Tests every layer: config, email service, DB state, and the actual
_send_direct_emails_to_all_users code path.
"""
import asyncio
import sys
import os

# Ensure we're running from apps/api
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ".")


async def diagnose():
    print("=" * 60)
    print("EMAIL DIAGNOSTICS")
    print("=" * 60)
    
    # 1. Config check
    from app.config import settings
    print(f"\n[1] CONFIG")
    print(f"  smtp_host:       {settings.smtp_host}")
    print(f"  smtp_port:       {settings.smtp_port}")
    print(f"  smtp_user:       {settings.smtp_user}")
    print(f"  smtp_password:   {'*' * len(settings.smtp_password)} (len={len(settings.smtp_password)})")
    print(f"  clean_password:  {'*' * len(settings.clean_smtp_password)} (len={len(settings.clean_smtp_password)})")
    print(f"  from_email:      {settings.notification_from_email}")
    print(f"  has_email_creds: {settings.has_email_credentials}")
    print(f"  notif_enabled:   {settings.notification_enabled}")
    
    # 2. Email service check
    from app.services.email_service import email_service
    print(f"\n[2] EMAIL SERVICE")
    print(f"  is_available: {email_service.is_available}")
    
    # 3. DB state
    from app.database import async_session_maker
    from app.models.user import User
    from app.models.channel import Channel
    from app.models.channel_subscription import ChannelSubscription
    from sqlalchemy import select
    
    async with async_session_maker() as session:
        users = (await session.execute(select(User).where(User.is_active == True))).scalars().all()
        channels = (await session.execute(select(Channel))).scalars().all()
        
        print(f"\n[3] DATABASE")
        print(f"  Active users: {len(users)}")
        for u in users:
            print(f"    #{u.id} {u.username} email={u.email} admin={u.is_admin}")
        print(f"  Channels: {len(channels)}")
        for ch in channels:
            print(f"    #{ch.id} {ch.name}")
        
        # Check subscriptions for each user
        print(f"\n[4] SUBSCRIPTIONS")
        for u in users:
            subs = (await session.execute(
                select(ChannelSubscription).where(ChannelSubscription.user_id == u.id)
            )).scalars().all()
            print(f"  User #{u.id} ({u.username}): {len(subs)} subscriptions")
            for s in subs:
                print(f"    channel={s.channel_id} active={s.is_active} email={s.notify_email}")
    
    # 4. Check recent notifications (in-app) to see what was created
    from app.models.notification import Notification
    async with async_session_maker() as session:
        recent = (await session.execute(
            select(Notification).order_by(Notification.id.desc()).limit(5)
        )).scalars().all()
        print(f"\n[5] RECENT NOTIFICATIONS (last 5)")
        for n in recent:
            print(f"  #{n.id} user={n.user_id} type={n.type} title={n.title[:60]}")
            print(f"    created={n.created_at}")
    
    # 5. ACTUALLY SEND A TEST EMAIL
    print(f"\n[6] LIVE EMAIL TEST")
    if not email_service.is_available:
        print("  SKIP — email service not available!")
    else:
        for u in users:
            if not u.email:
                continue
            print(f"  Sending test to {u.email}...")
            result = await email_service.send_signal_notification(
                u.email,
                {
                    "token_symbol": "DIAG",
                    "token_name": "Diagnostic Test",
                    "channel_name": "Email Diag Script",
                    "sentiment": "BULLISH",
                    "confidence_score": 0.99,
                    "signal_type": "token_mention",
                    "message_text": "If you see this email, the email pipeline works correctly.",
                    "contract_addresses": [],
                    "chain": "eth",
                }
            )
            print(f"  Result: {result}")
    
    # 6. Check rate limiting
    from app.services.notification_service import notification_service
    print(f"\n[7] NOTIFICATION SERVICE STATE")
    stats = notification_service.get_stats()
    print(f"  {stats}")
    print(f"  Rate limit cache entries: {len(notification_service._rate_limit_cache)}")
    for key, ts in notification_service._rate_limit_cache.items():
        print(f"    {key} -> {ts}")
    
    print(f"\n{'=' * 60}")
    print("DIAGNOSIS COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    # Need to init DB engine
    from app.database import create_tables
    asyncio.run(diagnose())

"""
Simulate a signal going through the EXACT same code path as a real
Telegram message to verify email sends alongside in-app notification.
"""
import asyncio
import sys
import os
import logging

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ".")

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(name)s %(levelname)s %(message)s')


async def simulate():
    # Import from the actual running code
    from app.main import save_signal_to_db
    from app.services.email_service import email_service
    from app.services.notification_service import notification_service
    
    print(f"\n=== PRE-CHECK ===")
    print(f"email_service.is_available: {email_service.is_available}")
    print(f"notification stats: {notification_service.get_stats()}")
    
    # Clear rate limits so we don't get blocked
    notification_service.clear_rate_limits()
    print(f"Rate limits cleared.")
    
    # Simulate a signal exactly as telegram_monitor would create it
    signal_data = {
        "token_symbol": "EMAILTEST",
        "token_name": "Email Pipeline Test",
        "channel_name": "something123",  # existing channel
        "channel_id": -1002263946824,     # existing channel
        "sentiment": "BULLISH",
        "confidence_score": 0.85,
        "signal_type": "contract_detection",
        "message_text": "🔥 EMAILTEST detected! CA: 0x1234567890abcdef1234567890abcdef12345678. This is a test to verify the email pipeline works end-to-end.",
        "contract_addresses": ["0x1234567890abcdef1234567890abcdef12345678"],
        "chain": "eth",
        "price_at_signal": 0.00042,
    }
    
    print(f"\n=== CALLING save_signal_to_db ===")
    await save_signal_to_db(signal_data)
    
    # Wait for background tasks (email sending is in asyncio.create_task)
    print(f"\nWaiting 15s for background email tasks to complete...")
    await asyncio.sleep(15)
    
    print(f"\n=== DONE ===")
    print(f"Check your inbox at laiskashkash33@gmail.com for the EMAILTEST signal!")


if __name__ == "__main__":
    asyncio.run(simulate())

import asyncio
import sys
import os

# Add app directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.services.email_service import email_service
from app.config import settings

async def test_email():
    print(f"Checking configuration...")
    print(f"SMTP Host: {settings.smtp_host}")
    print(f"SMTP Port: {settings.smtp_port}")
    print(f"SMTP User: {settings.smtp_user}")
    
    # Debug password (safely)
    pwd = settings.smtp_password
    if pwd:
        masked_pwd = f"{pwd[0]}...{pwd[-1]} (Length: {len(pwd)})"
        print(f"SMTP Password: {masked_pwd}")
    else:
        print("SMTP Password: <Not Configured>")
        
    print(f"Notifications Enabled: {settings.notification_enabled}")
    
    if not settings.has_email_credentials:
        print("❌ Error: SMTP credentials incomplete in settings or .env")
        print("   Please set SMTP_USER and SMTP_PASSWORD in your .env file")
        return

    # Replace with your email for testing
    to_email = settings.smtp_user 
    if not to_email:
        print("❌ No recipient email found (using SMTP_USER)")
        return
        
    print(f"\nAttempting to send test email to {to_email}...")

    # Mock signal data
    test_signal = {
        "token_symbol": "SMTP",
        "token_name": "Test Token",
        "channel_name": "Debug Channel",
        "sentiment": "BULLISH",
        "confidence_score": 0.95,
        "price_at_signal": 123.45,
        "target_price": 150.00,
        "stop_loss": 100.00,
        "message_text": "This is a test notification via SMTP.",
        "signal_type": "full_signal"
    }

    result = await email_service.send_signal_notification(to_email, test_signal)
    
    if result.get("success"):
        try:
            print("✅ Email sent successfully!")
        except UnicodeEncodeError:
            print("Email sent successfully! (Unicode checkmark failed to print)")
    else:
        print(f"❌ Failed to send email: {result.get('error')}")

if __name__ == "__main__":
    asyncio.run(test_email())
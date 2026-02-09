import asyncio
import os
import aiosmtplib
from email.message import EmailMessage

# Credentials from your context
SMTP_HOST = "smtp.titan.email"
USER = "contact@yesdo.tech"
# Attempting to read directly or defaults
PWD = os.getenv("SMTP_PASSWORD", "yamen186!") 

async def test_connection(port, use_tls, start_tls, label):
    print(f"\n--- Testing {label} (Port {port}) ---")
    message = EmailMessage()
    message["From"] = USER
    message["To"] = USER
    message["Subject"] = f"Test {label}"
    message.set_content("Test body")

    try:
        print(f"Connecting to {SMTP_HOST}:{port}...")
        async with aiosmtplib.SMTP(
            hostname=SMTP_HOST, 
            port=port, 
            use_tls=use_tls, 
            start_tls=start_tls,
            timeout=20
        ) as smtp:
            print("Connected. Logging in...")
            # Print the password being used (masked mostly) to verify it's what we expect
            debug_pwd = f"{PWD[:2]}...{PWD[-2:]}" if len(PWD) > 4 else "***"
            print(f"Using Password: {debug_pwd} (Length: {len(PWD)})")
            
            await smtp.login(USER, PWD)
            print("Login successful! Sending mail...")
            await smtp.send_message(message)
            print("✅ SUCCESS! Email sent.")
            return True
    except Exception as e:
        print(f"❌ FAILED: {e}")
        return False

async def main():
    # Test 1: Port 465 (Implicit SSL/TLS) - Recommended for Titan
    success = await test_connection(465, True, False, "SSL/TLS")
    
    if not success:
        # Test 2: Port 587 (STARTTLS)
        await test_connection(587, False, True, "STARTTLS")

if __name__ == "__main__":
    asyncio.run(main())
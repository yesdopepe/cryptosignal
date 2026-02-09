"""
Email notification service using SMTP.

Sends formatted HTML emails for crypto signal notifications.
"""
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from email.message import EmailMessage
import aiosmtplib

from app.config import settings

logger = logging.getLogger(__name__)


class EmailService:
    """
    Service for sending email notifications via SMTP.
    
    Provides formatted HTML emails for signal notifications.
    """
    
    def __init__(self):
        self._check_config()
    
    def _check_config(self):
        """Check SMTP configuration."""
        if settings.has_email_credentials:
            logger.info("✅ SMTP email service configured")
        else:
            logger.warning("⚠️ SMTP credentials not configured, email notifications disabled")
    
    @property
    def is_available(self) -> bool:
        """Check if email service is available."""
        return settings.has_email_credentials and settings.notification_enabled
    
    def _get_sentiment_color(self, sentiment: str) -> str:
        """Get color code for sentiment."""
        colors = {
            "BULLISH": "#22c55e",  # Green
            "BEARISH": "#ef4444",  # Red
            "NEUTRAL": "#6b7280",  # Gray
        }
        return colors.get(sentiment.upper(), "#6b7280")
    
    def _get_sentiment_emoji(self, sentiment: str) -> str:
        """Get emoji for sentiment."""
        emojis = {
            "BULLISH": "🚀",
            "BEARISH": "📉",
            "NEUTRAL": "📊",
        }
        return emojis.get(sentiment.upper(), "📊")
    
    def _format_price(self, price: Optional[float]) -> str:
        """Format price for display (dynamic matching Telegram logic)."""
        if price is None:
            return "N/A"
        return f"${price:,.8f}".rstrip("0").rstrip(".")

    def _build_html_email(self, signal_data: Dict[str, Any]) -> str:
        """Build HTML email template for signal notification."""
        token = signal_data.get("token_symbol", "UNKNOWN")
        token_name = signal_data.get("token_name", token)
        channel = signal_data.get("channel_name", "Unknown Channel")
        sentiment = signal_data.get("sentiment", "NEUTRAL")
        confidence = signal_data.get("confidence_score", 0.5)
        price = signal_data.get("price_at_signal")
        target = signal_data.get("target_price")
        stop_loss = signal_data.get("stop_loss")
        message = signal_data.get("message_text", "")[:500]
        timestamp = signal_data.get("timestamp", datetime.utcnow().isoformat())
        signal_type = signal_data.get("signal_type", "token_mention")
        contract_addresses = signal_data.get("contract_addresses", [])
        chain = signal_data.get("chain", "")
        
        sentiment_color = self._get_sentiment_color(sentiment)
        sentiment_emoji = self._get_sentiment_emoji(sentiment)
        confidence_pct = int(confidence * 100)

        # Labels (Matched to Telegram Monitor)
        type_label = {
            "full_signal": "Signal",
            "contract_detection": "Contract Detected",
            "token_mention": "Token Mentioned",
        }.get(signal_type, "Detection")
        
        # Build price info section
        price_info = ""
        if price is not None:
             price_info = f"""
            <tr>
                <td style="padding: 8px 0; color: #6b7280;">Entry</td>
                <td style="padding: 8px 0; text-align: right; font-weight: 600;">{self._format_price(price)}</td>
            </tr>
            """
        if target is not None:
            price_info += f"""
            <tr>
                <td style="padding: 8px 0; color: #6b7280;">Target</td>
                <td style="padding: 8px 0; text-align: right; font-weight: 600; color: #22c55e;">{self._format_price(target)}</td>
            </tr>
            """
        if stop_loss is not None:
            price_info += f"""
            <tr>
                <td style="padding: 8px 0; color: #6b7280;">Stop Loss</td>
                <td style="padding: 8px 0; text-align: right; font-weight: 600; color: #ef4444;">{self._format_price(stop_loss)}</td>
            </tr>
            """
        
        # Contract Address Section
        ca_info = ""
        if contract_addresses:
            ca = contract_addresses[0]
            chain_label = f" ({chain.upper()})" if chain else ""
            ca_info = f"""
            <div style="background: #f3f4f6; border-radius: 6px; padding: 12px; margin-bottom: 20px; text-align: center;">
                 <p style="margin: 0 0 4px 0; font-size: 11px; color: #6b7280; font-weight: bold; text-transform: uppercase;">Contract Address{chain_label}</p>
                 <code style="font-family: monospace; font-size: 14px; color: #374151; word-break: break-all;">{ca}</code>
            </div>
            """

        
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #f3f4f6;">
    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
        <!-- Header -->
        <div style="background: linear-gradient(135deg, #1f2937 0%, #374151 100%); border-radius: 12px 12px 0 0; padding: 24px; text-align: center;">
            <h1 style="color: white; margin: 0; font-size: 24px;">🔔 {type_label}</h1>
        </div>
        
        <!-- Main Content -->
        <div style="background: white; padding: 24px; border-radius: 0 0 12px 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
            <!-- Token Header -->
            <div style="display: flex; align-items: center; margin-bottom: 20px; border-bottom: 1px solid #e5e7eb; padding-bottom: 16px;">
                <div style="background: {sentiment_color}20; border-radius: 50%; width: 56px; height: 56px; display: flex; align-items: center; justify-content: center; font-size: 28px;">
                    {sentiment_emoji}
                </div>
                <div style="margin-left: 16px;">
                    <h2 style="margin: 0; font-size: 28px; color: #1f2937;">${token}</h2>
                    <p style="margin: 4px 0 0 0; color: #6b7280; font-size: 14px;">{token_name}</p>
                </div>
                <div style="margin-left: auto; text-align: right;">
                    <span style="background: {sentiment_color}; color: white; padding: 6px 12px; border-radius: 20px; font-size: 12px; font-weight: 600;">
                        {sentiment}
                    </span>
                </div>
            </div>
            
            {ca_info}
            
            <!-- Details Table -->
            <table style="width: 100%; border-collapse: collapse; margin-bottom: 20px;">
                <tr>
                    <td style="padding: 8px 0; color: #6b7280;">Channel</td>
                    <td style="padding: 8px 0; text-align: right; font-weight: 600;">📡 {channel}</td>
                </tr>
                <tr>
                    <td style="padding: 8px 0; color: #6b7280;">Confidence</td>
                    <td style="padding: 8px 0; text-align: right;">
                        <span style="background: #e5e7eb; border-radius: 4px; padding: 2px 8px; font-weight: 600;">{confidence_pct}%</span>
                    </td>
                </tr>
                {price_info}
            </table>
            
            <!-- Original Message -->
            <div style="background: #f9fafb; border-radius: 8px; padding: 16px; margin-bottom: 20px;">
                <p style="margin: 0 0 8px 0; font-size: 12px; color: #6b7280; text-transform: uppercase; letter-spacing: 0.5px;">Original Message</p>
                <p style="margin: 0; color: #374151; font-size: 14px; line-height: 1.5; white-space: pre-wrap;">{message}</p>
            </div>
            
            <!-- Footer -->
            <div style="text-align: center; padding-top: 16px; border-top: 1px solid #e5e7eb;">
                <p style="margin: 0; color: #9ca3af; font-size: 12px;">
                    Detected at {timestamp}<br>
                    This is an automated notification from Crypto Signal Aggregator
                </p>
            </div>
        </div>
        
        <!-- Disclaimer -->
        <p style="text-align: center; color: #9ca3af; font-size: 11px; margin-top: 16px;">
            ⚠️ This is not financial advice. Always do your own research before trading.
        </p>
    </div>
</body>
</html>
        """
        return html
    
    async def send_signal_notification(
        self, 
        to_email: str, 
        signal_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Send a signal notification email.
        
        Args:
            to_email: Recipient email address
            signal_data: Signal data dictionary with token_symbol, sentiment, etc.
            
        Returns:
            dict with success status and error if any
        """
        if not self.is_available:
            return {
                "success": False,
                "error": "Email service not configured",
            }
        
        token = signal_data.get("token_symbol", "UNKNOWN")
        token_name = signal_data.get("token_name", token) # Ensure fallback to token symbol
        sentiment = signal_data.get("sentiment", "NEUTRAL")
        signal_type = signal_data.get("signal_type", "token_mention")
        chain = signal_data.get("chain", "")
        sentiment_emoji = self._get_sentiment_emoji(sentiment)
        
        type_label = {
            "full_signal": "Signal",
            "contract_detection": "Contract Detected",
            "token_mention": "Token Mentioned",
        }.get(signal_type, "Detection")
        
        chain_label = f" ({chain.upper()})" if chain else ""
        
        # Include token name in subject if known and different from symbol
        name_display = f" ({token_name})" if token_name and token_name != "Unknown" and token_name != token else ""
        subject = f"{sentiment_emoji} {type_label}: {token}{name_display}{chain_label}"
             
        html_content = self._build_html_email(signal_data)
        
        message = EmailMessage()
        # improved FROM header to reduce spam likelihood
        display_name = settings.project_name.replace('"', '').strip()
        message["From"] = f"{display_name} <{settings.notification_from_email}>"
        message["To"] = to_email
        message["Subject"] = subject
        message.set_content("Please enable HTML to view this email.")
        message.add_alternative(html_content, subtype="html")
        
        try:
            # Determine security based on port
            use_tls = settings.smtp_port == 465
            start_tls = settings.smtp_port == 587
            
            await aiosmtplib.send(
                message,
                hostname=settings.smtp_host,
                port=settings.smtp_port,
                username=settings.smtp_user,
                password=settings.clean_smtp_password,
                start_tls=start_tls,
                use_tls=use_tls,
                timeout=30.0
            )
            
            logger.info(f"📧 Email sent to {to_email} for ${token} signal")
            
            return {
                "success": True,
                "email_id": "smtp-sent",
            }
            
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    async def send_general_notification(
        self,
        to_email: str,
        title: str,
        message_body: str,
        data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Send a generic notification email (e.g. for price alerts).
        """
        if not self.is_available:
            return {"success": False, "error": "Email service not configured"}
            
        data = data or {}
        token = data.get("token_symbol", "")
        chain = data.get("chain", "")
        
        # Simple HTML Template
        html_content = f"""
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family: sans-serif; background-color: #f3f4f6; padding: 20px;">
    <div style="max-width: 600px; margin: 0 auto; background: white; border-radius: 8px; padding: 24px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
        <h2 style="color: #1f2937; margin-top: 0;">🔔 {title}</h2>
        
        <p style="color: #374151; font-size: 16px; line-height: 1.5;">{message_body}</p>
        
        <div style="margin-top: 24px; padding-top: 16px; border-top: 1px solid #e5e7eb; color: #9ca3af; font-size: 12px; text-align: center;">
            <p>Crypto Signal Aggregator Notification</p>
        </div>
    </div>
</body>
</html>
        """
        
        msg = EmailMessage()
        display_name = settings.project_name.replace('"', '').strip()
        msg["From"] = f"{display_name} <{settings.notification_from_email}>"
        msg["To"] = to_email
        msg["Subject"] = title
        msg.set_content(message_body) # Plain text fallback
        msg.add_alternative(html_content, subtype="html")
        
        try:
            use_tls = settings.smtp_port == 465
            start_tls = settings.smtp_port == 587
            
            await aiosmtplib.send(
                msg,
                hostname=settings.smtp_host,
                port=settings.smtp_port,
                username=settings.smtp_user,
                password=settings.clean_smtp_password,
                start_tls=start_tls,
                use_tls=use_tls,
                timeout=30.0
            )
            logger.info(f"📧 General email sent to {to_email}: {title}")
            return {"success": True}
        except Exception as e:
            logger.error(f"Failed to send general email to {to_email}: {e}")
            return {"success": False, "error": str(e)}

# Global service instance
email_service = EmailService()

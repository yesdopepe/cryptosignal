"""Application configuration settings."""
import os
from functools import lru_cache
from typing import List, Optional
from pydantic_settings import BaseSettings

# Find the .env file — works whether CWD is workspace root or apps/api
_here = os.path.dirname(os.path.abspath(__file__))           # .../apps/api/app
_api_env = os.path.join(_here, "..", ".env")                  # .../apps/api/.env
_root_env = os.path.join(_here, "..", "..", "..", ".env")      # .../.env
_env_file = _api_env if os.path.exists(_api_env) else (_root_env if os.path.exists(_root_env) else ".env")
print(f"[CONFIG] Loading env from: {os.path.abspath(_env_file)}")


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Database
    database_url: str = "sqlite+aiosqlite:///./crypto_signals.db"
    
    # Redis
    redis_url: str = "redis://localhost:6379/0"
    
    # Telegram Configuration (get from https://my.telegram.org)
    telegram_api_id: str = ""
    telegram_api_hash: str = ""
    telegram_phone: str = ""  # Optional: phone number can be provided via API
    telegram_session_name: str = "crypto_signal_session"
    telegram_session_db: str = "telegram_session.db"  # SQLite DB for session persistence
    
    # Telegram Channels to Monitor (comma-separated usernames or IDs)
    telegram_channels: str = ""  # e.g., "cryptowhales,moonshots,-1001234567890"
    
    # Application
    secret_key: str = "change-me-in-production"
    debug: bool = True
    cors_origins: List[str] = ["http://localhost:3000", "http://localhost:8000"]
    
    # Cache
    cache_enabled: bool = True
    
    # API Settings
    api_v1_prefix: str = "/api/v1"
    project_name: str = "Crypto Signal Aggregator"
    
    # Notification Settings
    notification_enabled: bool = True
    notification_rate_limit_seconds: int = 300  # 5 minutes cooldown per user per channel
    
    # SMTP Configuration (Gmail, Outlook, etc.)
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    notification_from_email: str = "signals@example.com"

    # Moralis - Unused (fields kept to prevent startup errors if present in .env)
    moralis_api_key: Optional[str] = ""
    moralis_stream_webhook_url: str = ""
    moralis_stream_secret: str = ""
    
    # CoinMarketCap
    coinmarketcap_api_key: str = ""  # Free tier: 30 req/min, 10K/month
    
    @property
    def has_email_credentials(self) -> bool:
        """Check if SMTP credentials are configured."""
        return bool(self.smtp_host and self.smtp_user and self.smtp_password)
    
    @property
    def clean_smtp_password(self) -> str:
        """Remove spaces from password (essential for Gmail App Passwords)."""
        return self.smtp_password.replace(" ", "") if self.smtp_password else ""

    @property
    def telegram_channel_list(self) -> List[str]:
        """Parse telegram_channels into a list."""
        if not self.telegram_channels:
            return []
        return [ch.strip() for ch in self.telegram_channels.split(",") if ch.strip()]
    
    @property
    def has_telegram_credentials(self) -> bool:
        """Check if Telegram API credentials are configured (not phone - that's provided via API)."""
        return bool(self.telegram_api_id and self.telegram_api_hash)
    
    class Config:
        env_file = _env_file
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()

from pydantic_settings import BaseSettings
from typing import Optional
import os


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "釈迦AI (Shaka AI)"
    VERSION: str = "2.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "production"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://user:password@localhost:5432/sns_orchestrator"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Security
    SECRET_KEY: str = "your-secret-key-change-this"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # OAuth
    YOUTUBE_CLIENT_ID: Optional[str] = None
    YOUTUBE_CLIENT_SECRET: Optional[str] = None
    X_CLIENT_ID: Optional[str] = None
    X_CLIENT_SECRET: Optional[str] = None
    INSTAGRAM_CLIENT_ID: Optional[str] = None
    INSTAGRAM_CLIENT_SECRET: Optional[str] = None
    TIKTOK_CLIENT_ID: Optional[str] = None
    TIKTOK_CLIENT_SECRET: Optional[str] = None

    OAUTH_REDIRECT_BASE: str = "http://localhost:8006"

    # AI Services
    ANTHROPIC_API_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None

    # Proxy Services
    BRIGHTDATA_API_KEY: Optional[str] = None
    MULOGIN_API_KEY: Optional[str] = None

    # Rate Limiting
    DEFAULT_RATE_LIMIT_HOURLY: int = 100
    DEFAULT_RATE_LIMIT_DAILY: int = 1000

    # Timezone
    DEFAULT_TIMEZONE: str = "Asia/Tokyo"

    # Monitoring
    ENABLE_MONITORING: bool = True
    ALERT_WEBHOOK_URL: Optional[str] = None

    # WORM Audit
    AUDIT_STORAGE_PATH: str = "./audit_logs"

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()

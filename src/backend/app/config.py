from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./sakn.db"

    # Security
    SECRET_KEY: str = "change-me-in-production-use-at-least-32-bytes-base64"
    SECURITY_DNS_RESOLVER: str = "1.1.1.1"

    # Redis
    REDIS_URL: str = "redis://redis:6379/0"
    RATE_LIMIT_STORAGE: str = "redis"

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Environment
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"

    # CORS
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:8000"

    # SMTP
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "noreply@sakn.example.com"

    # Email verification
    EMAIL_VERIFICATION_REQUIRED: bool = True


settings = Settings()

from urllib.parse import quote_plus

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./sakn.db"
    POSTGRES_USER: str = "sakn"
    POSTGRES_PASSWORD: str = ""
    POSTGRES_HOST: str = "postgres"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "sakn"

    @model_validator(mode="after")
    def assemble_database_url(self) -> "Settings":
        # Keep explicit DATABASE_URL as-is for backward compatibility
        if "DATABASE_URL" in self.model_fields_set:
            return self
        if self.POSTGRES_PASSWORD:
            self.DATABASE_URL = (
                f"postgresql+asyncpg://{quote_plus(self.POSTGRES_USER)}"
                f":{quote_plus(self.POSTGRES_PASSWORD)}"
                f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
            )
        return self

    # Security
    SECRET_KEY: str = "change-me-in-production-use-at-least-32-bytes-base64"
    SECURITY_DNS_RESOLVER: str = "1.1.1.1"

    @model_validator(mode="after")
    def validate_secret_key(self) -> "Settings":
        if self.ENVIRONMENT != "production":
            return self
        if self.SECRET_KEY == "change-me-in-production-use-at-least-32-bytes-base64":
            raise ValueError(
                "SECRET_KEY is still set to the default value. "
                "Generate a real key (at least 32 bytes base64) and set it via the SECRET_KEY environment variable."
            )
        if len(self.SECRET_KEY) < 32:
            raise ValueError(
                f"SECRET_KEY must be at least 32 characters (got {len(self.SECRET_KEY)}). "
                "Generate a real key and set it via the SECRET_KEY environment variable."
            )
        return self

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

    # Reverse proxy trust (see ADR-003)
    TRUSTED_PROXY_HOPS: int = 0

    # Email verification
    EMAIL_VERIFICATION_REQUIRED: bool = True


settings = Settings()

import hashlib
from urllib.parse import quote

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator, model_validator

_KNOWN_DEFAULT_KEY_HASHES: frozenset[str] = frozenset({
    "f1b26d32000838014dae4c8fd56073c2e9de9ba0f4d7c6190097feb2171ac5f1",  # change-me-in-production-use-at-least-32-characters
    "19cd1e7f65109ed570df433a76166522c7d03377a1fcc6f3153f28085d90efe5",  # change-me-in-production-use-at-least-32-bytes-base64
    "a268e47c2aabfd8c9e6eac615564d426d33f08bcd7fd2789315517676987a97f",  # CHANGE-ME
    "e2186dbdb1bb4193608605e84f33208765b5693b55edd4f730a719a100eeea6f",  # change-me
    "057ba03d6c44104863dc7361fe4578965d1887360f90a0895882e58a6248fc86",  # changeme
    "ba01338ba5fa0c1584a6d41f93fe550b1d715a8de2da10d6c673131a85658394",  # CHANGEME
})


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
                f"postgresql+asyncpg://{quote(self.POSTGRES_USER, safe='')}"
                f":{quote(self.POSTGRES_PASSWORD, safe='')}"
                f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
            )
        return self

    # Security
    SECRET_KEY: str = "change-me-in-production-use-at-least-32-characters"
    SECURITY_DNS_RESOLVER: str = "1.1.1.1"

    @model_validator(mode="after")
    def validate_secret_key(self) -> "Settings":
        if self.ENVIRONMENT == "development":
            return self
        key_hash = hashlib.sha256(self.SECRET_KEY.encode()).hexdigest()
        if key_hash in _KNOWN_DEFAULT_KEY_HASHES:
            raise ValueError(
                "SECRET_KEY is still set to a known default or placeholder value. "
                "Generate a real key (at least 32 characters) and set it via the SECRET_KEY environment variable."
            )
        if len(self.SECRET_KEY) < 32:
            raise ValueError(
                f"SECRET_KEY must be at least 32 characters (got {len(self.SECRET_KEY)}). "
                "Generate a real key and set it via the SECRET_KEY environment variable."
            )
        if len(set(self.SECRET_KEY)) < 20:
            raise ValueError(
                f"SECRET_KEY has insufficient entropy ({len(set(self.SECRET_KEY))} distinct characters, "
                "minimum 20 required). Generate a real key and set it via the SECRET_KEY environment variable."
            )
        return self

    @model_validator(mode="after")
    def validate_health_token(self) -> "Settings":
        if self.ENVIRONMENT == "development":
            return self
        if self.HEALTH_FULL_TOKEN == "":
            return self
        if len(self.HEALTH_FULL_TOKEN) < 32:
            raise ValueError(
                f"HEALTH_FULL_TOKEN must be at least 32 characters when set in "
                f"{self.ENVIRONMENT} (got {len(self.HEALTH_FULL_TOKEN)}). "
                'Generate a token with: python -c "import secrets; print(secrets.token_urlsafe(32))"'
            )
        return self

    # Redis
    REDIS_URL: str = "redis://redis:6379/0"
    RATE_LIMIT_STORAGE: str = "redis"

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Environment (required — no default; set explicitly to development, staging, or production)
    ENVIRONMENT: str
    LOG_LEVEL: str = "INFO"

    @field_validator("ENVIRONMENT", mode="after")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        allowed = {"development", "staging", "production"}
        if v not in allowed:
            raise ValueError(f"ENVIRONMENT must be one of {allowed}, got '{v}'")
        return v

    # CORS
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:8000"

    # WebSocket origin validation (see ADR-009)
    WS_REQUIRE_ORIGIN: bool = False  # set true in production for CSWSH protection

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

    # IP-based brute-force protection (see ADR-005)
    BRUTEFORCE_IP_MAX_ATTEMPTS: int = 20  # failed logins per IP before 429
    BRUTEFORCE_IP_WINDOW_SECONDS: int = 900  # 15 minutes sliding window

    # Health check token for /health/full (generate with: python -c "import secrets; print(secrets.token_urlsafe(32))")
    HEALTH_FULL_TOKEN: str = ""


settings = Settings()

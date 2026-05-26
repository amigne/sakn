import hashlib
import hmac
import secrets

from app.config import settings


def generate_token() -> str:
    """CSPRNG 256-bit token, base64url-encoded, ~43 chars."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """HMAC-SHA256(SECRET_KEY, token) — peppered hash (ADR-007)."""
    return hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        token.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def verify_token(token: str, token_hash: str) -> bool:
    """Constant-time comparison via HMAC-SHA256."""
    return secrets.compare_digest(hash_token(token), token_hash)

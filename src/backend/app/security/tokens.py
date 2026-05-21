import hashlib
import hmac
import secrets

from app.config import settings


def generate_token() -> str:
    """CSPRNG 256-bit token, base64url-encoded, ~43 chars."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """HMAC-SHA256(SECRET_KEY, token) — peppered hash for new tokens (ADR-007)."""
    return hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        token.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def hash_token_legacy(token: str) -> str:
    """Plain SHA-256 hex digest — kept for backward compat during migration window.

    Remove after the migration window (30 days, see ADR-007) when all sessions
    have been silently upgraded.
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def verify_token(token: str, token_hash: str) -> bool:
    """Constant-time comparison. Tries HMAC first, legacy SHA-256 as fallback."""
    if secrets.compare_digest(hash_token(token), token_hash):
        return True
    # Legacy fallback — remove after migration window (ADR-007)
    return secrets.compare_digest(hash_token_legacy(token), token_hash)


def is_legacy_hash(token: str, token_hash: str) -> bool:
    """Return True if token_hash matches the legacy SHA-256 (not HMAC).

    Used during migration to detect sessions that need silent upgrade.
    """
    if secrets.compare_digest(hash_token_legacy(token), token_hash):
        # Only return True if it does NOT also match HMAC (shouldn't happen,
        # but HMAC output is different from SHA-256 so this is defensive)
        if not secrets.compare_digest(hash_token(token), token_hash):
            return True
    return False

import hashlib
import secrets


def generate_token() -> str:
    """CSPRNG 256-bit token, base64url-encoded, ~43 chars."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """SHA-256 hex digest of a token."""
    return hashlib.sha256(token.encode()).hexdigest()


def verify_token(token: str, token_hash: str) -> bool:
    """Constant-time comparison of token against stored SHA-256 hash."""
    return secrets.compare_digest(hash_token(token), token_hash)

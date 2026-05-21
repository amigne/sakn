import hashlib
import hmac
import secrets

from app.config import settings
from app.security.tokens import (
    generate_token,
    hash_token,
    hash_token_legacy,
    verify_token,
    is_legacy_hash,
)


class TestTokenGeneration:
    def test_generate_token_length(self):
        token = generate_token()
        assert len(token) == 43

    def test_generate_token_uniqueness(self):
        tokens = [generate_token() for _ in range(100)]
        assert len(set(tokens)) == 100

    def test_hash_token_is_hmac_sha256(self):
        """hash_token() now uses HMAC-SHA256(SECRET_KEY, token) per ADR-007."""
        token = "test-token"
        expected = hmac.new(
            settings.SECRET_KEY.encode("utf-8"),
            token.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        assert hash_token(token) == expected
        assert len(hash_token(token)) == 64

    def test_hash_token_legacy_is_sha256(self):
        """hash_token_legacy() is the old plain SHA-256 kept for backward compat."""
        token = "test-token"
        expected = hashlib.sha256(token.encode()).hexdigest()
        assert hash_token_legacy(token) == expected
        assert len(hash_token_legacy(token)) == 64

    def test_verify_matches_hmac(self):
        token = generate_token()
        h = hash_token(token)
        assert verify_token(token, h)

    def test_verify_matches_legacy(self):
        """verify_token() falls back to legacy SHA-256 for old sessions."""
        token = generate_token()
        legacy_h = hash_token_legacy(token)
        assert verify_token(token, legacy_h)

    def test_verify_rejects_wrong_token(self):
        token = generate_token()
        h = hash_token(token)
        assert not verify_token("wrong-token-here", h)

    def test_verify_uses_compare_digest(self):
        assert not verify_token("", "")
        assert not verify_token("abc", hash_token("def"))

    def test_is_legacy_detects_sha256(self):
        token = generate_token()
        assert is_legacy_hash(token, hash_token_legacy(token)) is True

    def test_is_legacy_rejects_hmac(self):
        token = generate_token()
        assert is_legacy_hash(token, hash_token(token)) is False

import hashlib
import hmac
import secrets

from app.config import settings
from app.security.tokens import (
    generate_token,
    hash_token,
    verify_token,
)


class TestTokenGeneration:
    def test_generate_token_length(self):
        token = generate_token()
        assert len(token) == 43

    def test_generate_token_uniqueness(self):
        tokens = [generate_token() for _ in range(100)]
        assert len(set(tokens)) == 100

    def test_hash_token_is_hmac_sha256(self):
        """hash_token() uses HMAC-SHA256(SECRET_KEY, token) per ADR-007."""
        token = "test-token"
        expected = hmac.new(
            settings.SECRET_KEY.encode("utf-8"),
            token.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        assert hash_token(token) == expected
        assert len(hash_token(token)) == 64

    def test_verify_matches_hmac(self):
        token = generate_token()
        h = hash_token(token)
        assert verify_token(token, h)

    def test_verify_rejects_wrong_token(self):
        token = generate_token()
        h = hash_token(token)
        assert not verify_token("wrong-token-here", h)

    def test_verify_uses_compare_digest(self):
        assert not verify_token("", "")
        assert not verify_token("abc", hash_token("def"))

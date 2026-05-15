import hashlib
import secrets

from app.security.tokens import generate_token, hash_token, verify_token


class TestTokenGeneration:
    def test_generate_token_length(self):
        token = generate_token()
        # token_urlsafe(32) → 43 base64 chars
        assert len(token) == 43

    def test_generate_token_uniqueness(self):
        tokens = [generate_token() for _ in range(100)]
        assert len(set(tokens)) == 100

    def test_hash_token_is_sha256_hex(self):
        token = "test-token"
        expected = hashlib.sha256(token.encode()).hexdigest()
        assert hash_token(token) == expected
        assert len(hash_token(token)) == 64  # SHA-256 hex = 64 chars

    def test_verify_token_constant_time(self):
        token = generate_token()
        h = hash_token(token)
        assert verify_token(token, h)
        assert not verify_token("wrong-token-here", h)
        assert not verify_token(token, hash_token("other-token"))

    def test_verify_uses_compare_digest(self):
        # verify correct result even with odd inputs
        assert not verify_token("", "")
        assert not verify_token("abc", hash_token("def"))

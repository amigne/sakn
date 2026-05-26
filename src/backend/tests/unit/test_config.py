import pytest
from pydantic import ValidationError

from app.config import Settings


class TestValidateSecretKey:
    """ADR-007: SECRET_KEY must be non-default and >= 32 chars in non-development environments."""

    def test_development_skips_secret_key_validation(self, monkeypatch):
        """Non-production environments accept the default placeholder key."""
        monkeypatch.delenv("SECRET_KEY", raising=False)
        s = Settings(
            _env_file=None,
            ENVIRONMENT="development",
        )
        assert s.SECRET_KEY == "change-me-in-production-use-at-least-32-characters"

    def test_staging_default_key_raises(self, monkeypatch):
        """Staging environment must reject the default placeholder key."""
        monkeypatch.delenv("SECRET_KEY", raising=False)
        with pytest.raises(ValueError, match="known default"):
            Settings(
                _env_file=None,
                ENVIRONMENT="staging",
            )

    def test_staging_with_short_key_raises(self):
        """Staging key must be at least 32 characters."""
        with pytest.raises(ValueError, match="at least 32"):
            Settings(
                _env_file=None,
                ENVIRONMENT="staging",
                SECRET_KEY="tooshort",
            )

    def test_staging_with_valid_key_passes(self):
        """A valid 32-char key is accepted in staging."""
        s = Settings(
            _env_file=None,
            ENVIRONMENT="staging",
            SECRET_KEY="abcdefghijklmnopqrstuvwxyz012345",  # 32 chars, 32 distinct
        )
        assert len(s.SECRET_KEY) == 32

    def test_production_with_default_key_raises(self, monkeypatch):
        """Production must not use the default placeholder key."""
        monkeypatch.delenv("SECRET_KEY", raising=False)
        with pytest.raises(ValueError, match="known default"):
            Settings(
                _env_file=None,
                ENVIRONMENT="production",
            )

    def test_production_with_uppercase_change_me_raises(self):
        """Uppercase CHANGE-ME variant is detected as a placeholder."""
        with pytest.raises(ValueError, match="known default"):
            Settings(
                _env_file=None,
                ENVIRONMENT="production",
                SECRET_KEY="CHANGE-ME",
            )

    def test_production_with_lowercase_change_me_raises(self):
        """Lowercase change-me variant is detected as a placeholder."""
        with pytest.raises(ValueError, match="known default"):
            Settings(
                _env_file=None,
                ENVIRONMENT="production",
                SECRET_KEY="change-me",
            )

    def test_production_with_no_dash_changeme_raises(self):
        """No-dash changeme variant is detected as a placeholder."""
        with pytest.raises(ValueError, match="known default"):
            Settings(
                _env_file=None,
                ENVIRONMENT="production",
                SECRET_KEY="changeme",
            )

    def test_production_with_short_key_raises(self):
        """Production key must be at least 32 characters."""
        with pytest.raises(ValueError, match="at least 32"):
            Settings(
                _env_file=None,
                ENVIRONMENT="production",
                SECRET_KEY="tooshort",
            )

    def test_production_with_31_char_key_raises(self):
        """31-char key is still rejected (boundary test)."""
        with pytest.raises(ValueError, match="at least 32"):
            Settings(
                _env_file=None,
                ENVIRONMENT="production",
                SECRET_KEY="a" * 31,
            )

    def test_production_with_32_char_key_passes(self):
        """Exactly 32 characters is the minimum valid key length."""
        s = Settings(
            _env_file=None,
            ENVIRONMENT="production",
            SECRET_KEY="abcdefghijklmnopqrstuvwxyz012345",  # 32 chars, 32 distinct
        )
        assert len(s.SECRET_KEY) == 32

    def test_production_with_64_char_key_passes(self):
        """A long random key is accepted."""
        key = "abcdefghijklmnopqrstuvwxyz0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ-_"
        assert len(key) == 64 and len(set(key)) == 64
        s = Settings(
            _env_file=None,
            ENVIRONMENT="production",
            SECRET_KEY=key,
        )
        assert s.SECRET_KEY == key

    def test_production_with_low_entropy_key_raises(self):
        """A key with only 1 distinct character must be rejected."""
        with pytest.raises(ValueError, match="insufficient entropy"):
            Settings(
                _env_file=None,
                ENVIRONMENT="production",
                SECRET_KEY="a" * 32,
            )

    def test_production_with_exactly_20_distinct_chars_passes(self):
        """A 32-char key with exactly 20 distinct characters is accepted."""
        key = "abcdefghij0123456789" + "a" * 12  # 20 distinct chars, 32 total
        s = Settings(
            _env_file=None,
            ENVIRONMENT="production",
            SECRET_KEY=key,
        )
        assert len(set(s.SECRET_KEY)) == 20

    def test_production_with_19_distinct_chars_raises(self):
        """A 32-char key with only 19 distinct characters is rejected."""
        key = "abcdefghi0123456789" + "a" * 13  # 19 distinct chars, 32 total
        with pytest.raises(ValueError, match="insufficient entropy"):
            Settings(
                _env_file=None,
                ENVIRONMENT="production",
                SECRET_KEY=key,
            )


class TestValidateHealthToken:
    """HEALTH_FULL_TOKEN must be >= 32 chars when set in non-development environments."""

    def test_development_skips_health_token_validation(self, monkeypatch):
        """Development accepts empty or short health tokens."""
        monkeypatch.delenv("SECRET_KEY", raising=False)
        monkeypatch.delenv("HEALTH_FULL_TOKEN", raising=False)
        s = Settings(_env_file=None, ENVIRONMENT="development")
        assert s.HEALTH_FULL_TOKEN == ""

    def test_production_empty_token_is_ok(self, monkeypatch):
        """Empty token in production means /health/full is disabled, which is fine."""
        monkeypatch.delenv("HEALTH_FULL_TOKEN", raising=False)
        s = Settings(
            _env_file=None,
            ENVIRONMENT="production",
            SECRET_KEY="abcdefghijklmnopqrstuvwxyz012345",
        )
        assert s.HEALTH_FULL_TOKEN == ""

    def test_production_short_token_raises(self):
        """Production with a short health token must raise."""
        with pytest.raises(ValueError, match="HEALTH_FULL_TOKEN must be at least 32"):
            Settings(
                _env_file=None,
                ENVIRONMENT="production",
                SECRET_KEY="abcdefghijklmnopqrstuvwxyz012345",
                HEALTH_FULL_TOKEN="short",
            )

    def test_production_valid_token_passes(self):
        """A 32-char health token is accepted in production."""
        s = Settings(
            _env_file=None,
            ENVIRONMENT="production",
            SECRET_KEY="abcdefghijklmnopqrstuvwxyz012345",
            HEALTH_FULL_TOKEN="h" * 32,
        )
        assert s.HEALTH_FULL_TOKEN == "h" * 32

    def test_staging_short_token_raises(self):
        """Staging with a short health token must also raise."""
        with pytest.raises(ValueError, match="HEALTH_FULL_TOKEN must be at least 32"):
            Settings(
                _env_file=None,
                ENVIRONMENT="staging",
                SECRET_KEY="abcdefghijklmnopqrstuvwxyz012345",
                HEALTH_FULL_TOKEN="short",
            )

    def test_staging_empty_token_is_ok(self, monkeypatch):
        """Empty health token in staging is accepted."""
        monkeypatch.delenv("HEALTH_FULL_TOKEN", raising=False)
        s = Settings(
            _env_file=None,
            ENVIRONMENT="staging",
            SECRET_KEY="abcdefghijklmnopqrstuvwxyz012345",
        )
        assert s.HEALTH_FULL_TOKEN == ""


class TestValidateEnvironment:
    """ENVIRONMENT is required and must be one of {development, staging, production}."""

    def test_accepts_development(self, monkeypatch):
        monkeypatch.delenv("SECRET_KEY", raising=False)
        s = Settings(_env_file=None, ENVIRONMENT="development")
        assert s.ENVIRONMENT == "development"

    def test_accepts_staging(self):
        s = Settings(
            _env_file=None,
            ENVIRONMENT="staging",
            SECRET_KEY="abcdefghijklmnopqrstuvwxyz012345",
        )
        assert s.ENVIRONMENT == "staging"

    def test_accepts_production(self):
        s = Settings(
            _env_file=None,
            ENVIRONMENT="production",
            SECRET_KEY="abcdefghijklmnopqrstuvwxyz012345",
        )
        assert s.ENVIRONMENT == "production"

    def test_rejects_invalid_value_test(self):
        with pytest.raises(ValueError, match="must be one of"):
            Settings(_env_file=None, ENVIRONMENT="test")

    def test_rejects_invalid_value_dev(self):
        with pytest.raises(ValueError, match="must be one of"):
            Settings(_env_file=None, ENVIRONMENT="dev")

    def test_rejects_invalid_value_prod(self):
        with pytest.raises(ValueError, match="must be one of"):
            Settings(_env_file=None, ENVIRONMENT="prod")

    def test_rejects_empty_string(self):
        with pytest.raises(ValueError, match="must be one of"):
            Settings(_env_file=None, ENVIRONMENT="")

    def test_environment_is_required(self, monkeypatch):
        """Passing no ENVIRONMENT raises a pydantic ValidationError."""
        monkeypatch.delenv("ENVIRONMENT", raising=False)
        with pytest.raises(ValidationError):
            Settings(_env_file=None)


class TestNormalizeCorsOrigins:
    """#47: CORS_ORIGINS are normalized (lowercase, no trailing slash, default ports stripped)."""

    def test_default_unchanged(self, monkeypatch):
        """Default CORS_ORIGINS value is left as-is."""
        monkeypatch.delenv("CORS_ORIGINS", raising=False)
        monkeypatch.delenv("SECRET_KEY", raising=False)
        s = Settings(_env_file=None, ENVIRONMENT="development")
        assert s.CORS_ORIGINS == "http://localhost:5173,http://localhost:8000"

    def test_mixed_case_lowered(self, monkeypatch):
        """Scheme and host are lowercased."""
        monkeypatch.delenv("SECRET_KEY", raising=False)
        s = Settings(
            _env_file=None,
            ENVIRONMENT="development",
            CORS_ORIGINS="https://Example.COM",
        )
        assert s.CORS_ORIGINS == "https://example.com"

    def test_trailing_slash_removed(self, monkeypatch):
        """Trailing slash is stripped (browser never sends it in Origin)."""
        monkeypatch.delenv("SECRET_KEY", raising=False)
        s = Settings(
            _env_file=None,
            ENVIRONMENT="development",
            CORS_ORIGINS="https://example.com/",
        )
        assert s.CORS_ORIGINS == "https://example.com"

    def test_default_https_port_removed(self, monkeypatch):
        """:443 is stripped for HTTPS origins (browser omits default ports)."""
        monkeypatch.delenv("SECRET_KEY", raising=False)
        s = Settings(
            _env_file=None,
            ENVIRONMENT="development",
            CORS_ORIGINS="https://example.com:443",
        )
        assert s.CORS_ORIGINS == "https://example.com"

    def test_default_http_port_removed(self, monkeypatch):
        """:80 is stripped for HTTP origins (browser omits default ports)."""
        monkeypatch.delenv("SECRET_KEY", raising=False)
        s = Settings(
            _env_file=None,
            ENVIRONMENT="development",
            CORS_ORIGINS="http://example.com:80",
        )
        assert s.CORS_ORIGINS == "http://example.com"

    def test_non_default_port_preserved(self, monkeypatch):
        """Non-default ports (e.g. :5173, :8000) are preserved."""
        monkeypatch.delenv("SECRET_KEY", raising=False)
        s = Settings(
            _env_file=None,
            ENVIRONMENT="development",
            CORS_ORIGINS="http://localhost:5173",
        )
        assert s.CORS_ORIGINS == "http://localhost:5173"

    def test_duplicates_deduplicated(self, monkeypatch):
        """Duplicate origins after normalization are collapsed to one entry."""
        monkeypatch.delenv("SECRET_KEY", raising=False)
        s = Settings(
            _env_file=None,
            ENVIRONMENT="development",
            CORS_ORIGINS="https://example.com,https://example.com/,HTTPS://Example.COM:443",
        )
        assert s.CORS_ORIGINS == "https://example.com"

    def test_whitespace_trimmed(self, monkeypatch):
        """Leading/trailing whitespace around entries is trimmed."""
        monkeypatch.delenv("SECRET_KEY", raising=False)
        s = Settings(
            _env_file=None,
            ENVIRONMENT="development",
            CORS_ORIGINS=" https://a.com , http://b.com ",
        )
        assert s.CORS_ORIGINS == "https://a.com,http://b.com"

    def test_empty_entries_skipped(self, monkeypatch):
        """Empty entries (double comma, trailing comma) are skipped."""
        monkeypatch.delenv("SECRET_KEY", raising=False)
        s = Settings(
            _env_file=None,
            ENVIRONMENT="development",
            CORS_ORIGINS="https://a.com,,https://b.com,",
        )
        assert s.CORS_ORIGINS == "https://a.com,https://b.com"

    def test_invalid_url_preserved_as_is(self, monkeypatch):
        """Unparseable entries are passed through unchanged (no crash)."""
        monkeypatch.delenv("SECRET_KEY", raising=False)
        s = Settings(
            _env_file=None,
            ENVIRONMENT="development",
            CORS_ORIGINS="not-a-url,*",
        )
        assert "not-a-url" in s.CORS_ORIGINS
        assert "*" in s.CORS_ORIGINS

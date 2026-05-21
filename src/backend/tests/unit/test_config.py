import pytest
from pydantic import ValidationError

from app.config import Settings


class TestValidateSecretKey:
    """ADR-007: SECRET_KEY must be non-default and >= 32 chars in production."""

    def test_development_skips_secret_key_validation(self):
        """Non-production environments accept the default placeholder key."""
        s = Settings(
            _env_file=None,
            ENVIRONMENT="development",
        )
        assert s.SECRET_KEY == "change-me-in-production-use-at-least-32-bytes-base64"

    def test_staging_skips_secret_key_validation(self):
        """Staging environment also skips key validation."""
        s = Settings(
            _env_file=None,
            ENVIRONMENT="staging",
        )
        assert s.SECRET_KEY

    def test_production_with_default_key_raises(self):
        """Production must not use the default placeholder key."""
        with pytest.raises(ValueError, match="default value"):
            Settings(
                _env_file=None,
                ENVIRONMENT="production",
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
            SECRET_KEY="b" * 32,
        )
        assert len(s.SECRET_KEY) == 32

    def test_production_with_64_char_key_passes(self):
        """A long random key is accepted."""
        key = "x" * 64
        s = Settings(
            _env_file=None,
            ENVIRONMENT="production",
            SECRET_KEY=key,
        )
        assert s.SECRET_KEY == key


class TestValidateEnvironment:
    """ENVIRONMENT is required and must be one of {development, staging, production}."""

    def test_accepts_development(self):
        s = Settings(_env_file=None, ENVIRONMENT="development")
        assert s.ENVIRONMENT == "development"

    def test_accepts_staging(self):
        s = Settings(_env_file=None, ENVIRONMENT="staging")
        assert s.ENVIRONMENT == "staging"

    def test_accepts_production(self):
        s = Settings(
            _env_file=None,
            ENVIRONMENT="production",
            SECRET_KEY="p" * 32,
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

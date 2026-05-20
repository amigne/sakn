from urllib.parse import urlparse

from app.config import Settings


class TestDatabaseUrlAssembly:
    def test_database_url_assembled_from_components(self):
        s = Settings(
            _env_file=None,
            POSTGRES_USER="sakn",
            POSTGRES_PASSWORD="secret",
            POSTGRES_HOST="localhost",
            POSTGRES_PORT=5432,
            POSTGRES_DB="sakn",
        )
        assert s.DATABASE_URL == "postgresql+asyncpg://sakn:secret@localhost:5432/sakn"

    def test_database_url_quote_plus_special_chars(self):
        s = Settings(_env_file=None, POSTGRES_PASSWORD="p@ss/w+ord%#?")
        url = s.DATABASE_URL
        # URL must be parseable
        parsed = urlparse(url)
        assert parsed.scheme == "postgresql+asyncpg"
        # Password must be encoded
        assert "p%40ss%2Fw%2Bord%25%23%3F" in url  # quote and quote_plus encode identically on these chars

    def test_database_url_explicit_override_bypasses_assembly(self):
        s = Settings(
            _env_file=None,
            DATABASE_URL="postgresql+asyncpg://custom:override@host/db",
            POSTGRES_PASSWORD="ignored",
        )
        assert s.DATABASE_URL == "postgresql+asyncpg://custom:override@host/db"

    def test_database_url_default_dev_sqlite(self):
        s = Settings(_env_file=None)
        assert s.DATABASE_URL == "sqlite+aiosqlite:///./sakn.db"

    def test_postgres_user_special_chars_quoted(self):
        s = Settings(_env_file=None, POSTGRES_USER="user@name", POSTGRES_PASSWORD="secret")
        assert "user%40name" in s.DATABASE_URL

    def test_database_url_password_with_space(self):
        s = Settings(_env_file=None, POSTGRES_PASSWORD="pass word")
        assert "pass%20word" in s.DATABASE_URL
        assert "pass+word" not in s.DATABASE_URL

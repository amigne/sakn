"""Unit tests for ensure_aware() — regression guards for issue #292 (timezone comparison TypeError)."""
from datetime import UTC, datetime

from app.models.base import ensure_aware


class TestEnsureAware:
    """ensure_aware() normalizes DB values before comparison with utcnow().

    On PostgreSQL, DateTime(timezone=True) columns return aware datetimes.
    On SQLite, they return naive datetimes (no timezone stored).
    ensure_aware() normalizes both cases to timezone-aware UTC."""

    def test_aware_input_unchanged(self):
        """Aware datetime is returned as-is."""
        aware = datetime(2026, 1, 1, tzinfo=UTC)
        result = ensure_aware(aware)
        assert result == aware
        assert result.tzinfo is not None

    def test_naive_input_becomes_aware_utc(self):
        """Naive datetime is assumed UTC and upgraded to aware."""
        naive = datetime(2026, 1, 1)  # no tzinfo
        result = ensure_aware(naive)
        assert result == datetime(2026, 1, 1, tzinfo=UTC)
        assert result.tzinfo is not None

    def test_naive_now_compares_with_aware_past(self):
        """Simulates SQLite: DB returns naive, utcnow() is aware. Comparison works."""
        db_value = datetime(2025, 1, 1)  # naive (SQLite)
        now = datetime.now(UTC)  # aware
        assert ensure_aware(db_value) < now  # past < now → True

    def test_naive_future_compares_with_aware_now(self):
        """Simulates SQLite: future naive DB value > aware now."""
        db_value = datetime(2099, 1, 1)  # naive (SQLite)
        now = datetime.now(UTC)  # aware
        assert ensure_aware(db_value) > now  # future > now → True

    def test_aware_past_compares_with_aware_now(self):
        """Simulates PostgreSQL: DB returns aware, utcnow() is aware."""
        db_value = datetime(2025, 1, 1, tzinfo=UTC)  # aware (PostgreSQL)
        now = datetime.now(UTC)  # aware
        assert ensure_aware(db_value) < now  # past < now → True

    def test_aware_future_compares_with_aware_now(self):
        """Simulates PostgreSQL: future aware DB value > aware now."""
        db_value = datetime(2099, 1, 1, tzinfo=UTC)  # aware (PostgreSQL)
        now = datetime.now(UTC)  # aware
        assert ensure_aware(db_value) > now  # future > now → True

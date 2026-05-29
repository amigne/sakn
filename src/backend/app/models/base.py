from datetime import UTC, datetime

from sqlalchemy import DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(UTC)


def ensure_aware(dt: datetime) -> datetime:
    """Normalize a datetime to timezone-aware UTC.

    On PostgreSQL, DateTime(timezone=True) columns return aware datetimes.
    On SQLite, they return naive datetimes (stored without timezone info).
    This helper normalizes both cases so comparisons with utcnow() are safe.
    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


def new_uuid7() -> str:
    from uuid_extensions import uuid7

    return str(uuid7())


class Base(DeclarativeBase):
    pass


class UUID7Mixin:
    id: Mapped[str] = mapped_column(
        primary_key=True,
        default=new_uuid7,
    )


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
        nullable=False,
    )

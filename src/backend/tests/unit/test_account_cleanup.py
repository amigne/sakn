from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.models.user import User
from app.services.account_cleanup_service import cleanup_unverified_accounts
from tests.factories import create_user


@pytest.mark.asyncio
async def test_deletes_unverified_account_older_than_retention(db_session):
    """Unverified account older than 7 days should be deleted."""
    old_date = datetime.now(timezone.utc) - timedelta(days=8)
    user = User(
        email="old-unverified@example.com",
        password_hash="hash",
        status="pending",
        email_verified_at=None,
    )
    user.created_at = old_date
    db_session.add(user)
    await db_session.flush()

    count = await cleanup_unverified_accounts(db_session, retention_days=7)

    assert count == 1
    result = await db_session.execute(select(User).where(User.id == user.id))
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_keeps_recent_unverified_account(db_session):
    """Unverified account less than 7 days old should be kept."""
    recent_date = datetime.now(timezone.utc) - timedelta(days=3)
    user = User(
        email="recent-unverified@example.com",
        password_hash="hash",
        status="pending",
        email_verified_at=None,
    )
    user.created_at = recent_date
    db_session.add(user)
    await db_session.flush()

    count = await cleanup_unverified_accounts(db_session, retention_days=7)

    assert count == 0
    result = await db_session.execute(select(User).where(User.id == user.id))
    assert result.scalar_one_or_none() is not None


@pytest.mark.asyncio
async def test_keeps_verified_account_older_than_retention(db_session):
    """Verified account older than 7 days should be kept."""
    old_date = datetime.now(timezone.utc) - timedelta(days=10)
    user = User(
        email="old-verified@example.com",
        password_hash="hash",
        status="active",
        email_verified_at=old_date,
    )
    user.created_at = old_date
    db_session.add(user)
    await db_session.flush()

    count = await cleanup_unverified_accounts(db_session, retention_days=7)

    assert count == 0
    result = await db_session.execute(select(User).where(User.id == user.id))
    assert result.scalar_one_or_none() is not None

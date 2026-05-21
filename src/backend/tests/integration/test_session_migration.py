"""Test silent upgrade of legacy SHA-256 session hashes to HMAC (ADR-007)."""
from datetime import timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import User, Session
from app.models.base import new_uuid7, utcnow
from app.security.tokens import generate_token, hash_token, hash_token_legacy
from app.security.password import hash_password


STRONG_PW = "MyC0rrectHorseBatteryStaple!"
TEST_EMAIL = "migration@example.com"


@pytest.mark.asyncio
async def test_legacy_session_authenticates_and_upgrades(
    client: AsyncClient, db_session: AsyncSession, _engine,
):
    """A session stored with legacy SHA-256 should authenticate and be upgraded."""
    # Create user
    user = User(
        id=new_uuid7(),
        email=TEST_EMAIL,
        password_hash=hash_password(STRONG_PW),
        role="authenticated",
        status="active",
        email_verified_at=utcnow(),
    )
    db_session.add(user)
    await db_session.flush()

    # Create session with LEGACY SHA-256 hash
    raw_token = generate_token()
    legacy_hash = hash_token_legacy(raw_token)
    session = Session(
        id=new_uuid7(),
        user_id=user.id,
        token_hash=legacy_hash,  # <-- stored as legacy SHA-256
        ip_address="127.0.0.1",
        expires_at=utcnow() + timedelta(hours=23),
        last_activity_at=utcnow(),
        created_at=utcnow(),
    )
    db_session.add(session)
    await db_session.commit()
    session_id = session.id

    cookies = {"sakn_session": raw_token}

    # Request that goes through SessionMiddleware — should authenticate via legacy fallback
    resp = await client.get("/api/v1/auth/me", cookies=cookies)
    assert resp.status_code == 200, f"Legacy session should authenticate. Body: {resp.text}"
    data = resp.json()
    assert data["user"]["email"] == TEST_EMAIL

    # Verify the session was silently upgraded in DB
    # Use a fresh session from the test engine (fixture transaction was committed)
    verify_factory = async_sessionmaker(_engine, class_=AsyncSession)
    async with verify_factory() as verify_session:
        upgraded = await verify_session.execute(
            select(Session.token_hash).where(Session.id == session_id)
        )
        result_hash = upgraded.scalar_one()
        assert result_hash == hash_token(raw_token), (
            f"Session hash should be upgraded from SHA-256 to HMAC. "
            f"Expected {hash_token(raw_token)[:16]}..., got {result_hash[:16]}..."
        )


@pytest.mark.asyncio
async def test_hmac_session_works_directly(
    client: AsyncClient, db_session: AsyncSession,
):
    """A session stored with HMAC hash should work normally (no fallback needed)."""
    user = User(
        id=new_uuid7(),
        email="hmac@example.com",
        password_hash=hash_password(STRONG_PW),
        role="authenticated",
        status="active",
        email_verified_at=utcnow(),
    )
    db_session.add(user)
    await db_session.flush()

    # Create session with HMAC hash (new format)
    raw_token = generate_token()
    hmac_hash = hash_token(raw_token)
    session = Session(
        id=new_uuid7(),
        user_id=user.id,
        token_hash=hmac_hash,
        ip_address="127.0.0.1",
        expires_at=utcnow() + timedelta(hours=23),
        last_activity_at=utcnow(),
        created_at=utcnow(),
    )
    db_session.add(session)
    await db_session.commit()

    cookies = {"sakn_session": raw_token}
    resp = await client.get("/api/v1/auth/me", cookies=cookies)
    assert resp.status_code == 200
    data = resp.json()
    assert data["user"]["email"] == "hmac@example.com"

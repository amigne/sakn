"""Test HMAC session authentication (ADR-007 — migration completed)."""
from datetime import timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User, Session
from app.models.base import new_uuid7, utcnow
from app.security.tokens import generate_token, hash_token
from app.security.password import hash_password


STRONG_PW = "MyC0rrectHorseBatteryStaple!"


@pytest.mark.asyncio
async def test_hmac_session_works(
    client: AsyncClient, db_session: AsyncSession,
):
    """A session stored with HMAC hash should work normally."""
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

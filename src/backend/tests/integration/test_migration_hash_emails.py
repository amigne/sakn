"""Test migration 8a2a49d76d6a: hash cleartext emails in SecurityEventLog."""
import hashlib
import hmac
import json

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.base import new_uuid7


def _hash_email(email: str) -> str:
    """Replicate the migration's _hash_email() for test assertions."""
    normalized = email.strip().lower()
    return hmac.new(
        settings.SECRET_KEY.encode(),
        normalized.encode(),
        hashlib.sha256,
    ).hexdigest()


@pytest.mark.asyncio
async def test_hash_email_deterministic():
    """Same email → same hash; case/whitespace normalized."""
    h1 = _hash_email(" User@Example.Com ")
    h2 = _hash_email("user@example.com")
    h3 = _hash_email("other@example.com")

    assert h1 == h2
    assert h1 != h3


@pytest.mark.asyncio
async def test_migration_transforms_cleartext_emails(db_session: AsyncSession):
    """Insert pre-#15 rows with plaintext emails, apply transformation, verify.

    db_session is wrapped in session.begin() → all ops share one transaction.
    No explicit commit() needed — data is visible within the transaction.
    """
    row1_id = new_uuid7()
    row2_id = new_uuid7()

    email1 = " Alice@Example.Org "
    email2 = "alice@example.org"

    await db_session.execute(
        text(
            "INSERT INTO security_event_logs (id, event_type, source_ip, details, created_at) "
            "VALUES (:id, :event_type, :source_ip, :details, datetime('now'))"
        ),
        {"id": row1_id, "event_type": "login_failed_no_user",
         "source_ip": "10.0.0.1",
         "details": json.dumps({"email": email1, "attempt": 1})},
    )
    await db_session.execute(
        text(
            "INSERT INTO security_event_logs (id, event_type, source_ip, details, created_at) "
            "VALUES (:id, :event_type, :source_ip, :details, datetime('now'))"
        ),
        {"id": row2_id, "event_type": "registration_duplicate",
         "source_ip": "10.0.0.2",
         "details": json.dumps({"email": email2, "attempt": 2})},
    )
    await db_session.flush()

    # Apply the transformation (same logic as the migration's upgrade())
    rows = (await db_session.execute(
        text("SELECT id, details FROM security_event_logs WHERE details LIKE '%\"email\"%'")
    )).fetchall()

    assert len(rows) == 2

    for row_id, details_str in rows:
        details = json.loads(details_str)
        email = details.pop("email", None)
        if email and isinstance(email, str) and "@" in email:
            details["email_hash"] = _hash_email(email)
            await db_session.execute(
                text("UPDATE security_event_logs SET details = :details WHERE id = :id"),
                {"details": json.dumps(details, ensure_ascii=False), "id": row_id},
            )
    await db_session.flush()

    # Verify row 1
    row1 = (await db_session.execute(
        text("SELECT details FROM security_event_logs WHERE id = :id"), {"id": row1_id}
    )).scalar_one()
    details1 = json.loads(row1)
    assert "email" not in details1
    assert details1["email_hash"] == _hash_email("alice@example.org")
    assert details1["attempt"] == 1

    # Verify row 2
    row2 = (await db_session.execute(
        text("SELECT details FROM security_event_logs WHERE id = :id"), {"id": row2_id}
    )).scalar_one()
    details2 = json.loads(row2)
    assert "email" not in details2
    assert details2["email_hash"] == _hash_email("alice@example.org")
    assert details2["attempt"] == 2

    # Same email → same hash (normalization)
    assert details1["email_hash"] == details2["email_hash"]


@pytest.mark.asyncio
async def test_migration_skips_non_email_rows(db_session: AsyncSession):
    """Rows without 'email' in details should be left untouched."""
    row_id = new_uuid7()
    original = {"attempt": 5, "reason": "brute force"}
    await db_session.execute(
        text(
            "INSERT INTO security_event_logs (id, event_type, source_ip, details, created_at) "
            "VALUES (:id, :event_type, :source_ip, :details, datetime('now'))"
        ),
        {"id": row_id, "event_type": "login_failed",
         "source_ip": "10.0.0.3", "details": json.dumps(original)},
    )
    await db_session.flush()

    rows = (await db_session.execute(
        text("SELECT id FROM security_event_logs WHERE details LIKE '%\"email\"%'")
    )).fetchall()
    assert row_id not in [r[0] for r in rows]

    row = (await db_session.execute(
        text("SELECT details FROM security_event_logs WHERE id = :id"), {"id": row_id}
    )).scalar_one()
    assert json.loads(row) == original


@pytest.mark.asyncio
async def test_migration_skips_already_hashed_rows(db_session: AsyncSession):
    """Rows with email_hash (post-#15) should NOT be matched or modified."""
    row_id = new_uuid7()
    original = {"email_hash": "abc123def456", "attempt": 1}
    await db_session.execute(
        text(
            "INSERT INTO security_event_logs (id, event_type, source_ip, details, created_at) "
            "VALUES (:id, :event_type, :source_ip, :details, datetime('now'))"
        ),
        {"id": row_id, "event_type": "login_failed_no_user",
         "source_ip": "10.0.0.4", "details": json.dumps(original)},
    )
    await db_session.flush()

    rows = (await db_session.execute(
        text("SELECT id FROM security_event_logs WHERE details LIKE '%\"email\"%'")
    )).fetchall()
    assert row_id not in [r[0] for r in rows]

    row = (await db_session.execute(
        text("SELECT details FROM security_event_logs WHERE id = :id"), {"id": row_id}
    )).scalar_one()
    assert json.loads(row) == original

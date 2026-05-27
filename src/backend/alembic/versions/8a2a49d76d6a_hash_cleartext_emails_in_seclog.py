"""hash_cleartext_emails_in_seclog

Revision ID: 8a2a49d76d6a
Revises: d7091a29b949
Create Date: 2026-05-25

Replace plaintext email in SecurityEventLog.details with HMAC-SHA256(email, SECRET_KEY).
Pre-#15 records may still contain details->>'email' (cleartext PII). This migration:
  1. SELECTs rows where details has a non-null, non-empty "email" key
  2. Computes email_hash = HMAC-SHA256(SECRET_KEY, normalized_email)
  3. Replaces the "email" key with "email_hash" in the JSON blob
  4. Uses batch_size=1000 with per-batch commits for large tables

Forward-only: downgrade cannot restore the plaintext email from the hash.
"""
import hashlib
import hmac
import json
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import text

from alembic import op
from app.config import settings

revision: str = '8a2a49d76d6a'
down_revision: str | None = 'd7091a29b949'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _hash_email(email: str) -> str:
    """HMAC-SHA256 the email — must match auth_service._hash_email_for_log()."""
    normalized = email.strip().lower()
    return hmac.new(
        settings.SECRET_KEY.encode(),
        normalized.encode(),
        hashlib.sha256,
    ).hexdigest()


def upgrade() -> None:
    conn = op.get_bind()
    table = sa.table(
        "security_event_logs",
        sa.column("id", sa.String),
        sa.column("details", sa.Text),
    )

    # Count rows with plaintext email in details
    # SQLite: JSON_EXTRACT(details, '$.email'); PostgreSQL: details->>'email'
    # Use LIKE for cross-engine compat (SQLite in tests, PostgreSQL in CI/prod)
    count_q = text(
        "SELECT COUNT(*) FROM security_event_logs "
        "WHERE details LIKE '%\"email\"%'"
    )
    total = conn.execute(count_q).scalar()
    if total == 0:
        return

    # Fetch and process in batches
    batch_size = 1000
    offset = 0

    while offset < total:
        rows = conn.execute(
            sa.select(table.c.id, table.c.details).where(
                table.c.details.like('%\"email\"%')
            ).limit(batch_size).offset(offset)
        ).fetchall()

        if not rows:
            break

        for row in rows:
            try:
                details = json.loads(row.details)
            except (json.JSONDecodeError, TypeError):
                continue

            email = details.pop("email", None)
            if not email or not isinstance(email, str) or "@" not in email:
                continue

            details["email_hash"] = _hash_email(email)
            conn.execute(
                table.update().where(table.c.id == row.id).values(
                    details=json.dumps(details, ensure_ascii=False)
                )
            )

        conn.commit()
        offset += batch_size


def downgrade() -> None:
    """No-op: email hashes cannot be reversed to plaintext.

    This downgrade intentionally does nothing. The data transformation is
    cryptographically irreversible — HMAC-SHA256 is a one-way function
    keyed with SECRET_KEY. Even with the key, you cannot recover the
    original email from the hash (you would need to brute-force the email
    space).

    Downgrading the schema past this migration leaves the data as-is
    (hashed), which is the secure state. No data loss, no corruption.
    """
    pass

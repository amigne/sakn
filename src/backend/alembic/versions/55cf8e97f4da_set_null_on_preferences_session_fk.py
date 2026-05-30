"""set_null_on_preferences_session_fk

Revision ID: 55cf8e97f4da
Revises: 8a2a49d76d6a
Create Date: 2026-05-29 21:39:36.766246

Change user_preferences.session_id FK from ON DELETE CASCADE to ON DELETE SET NULL
so that user preferences survive logout (session deletion).
"""

from collections.abc import Sequence

from alembic import op

revision: str = "55cf8e97f4da"
down_revision: str | None = "8a2a49d76d6a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE user_preferences DROP CONSTRAINT IF EXISTS user_preferences_session_id_fkey"
    )
    op.create_foreign_key(
        None,
        "user_preferences",
        "sessions",
        ["session_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE user_preferences DROP CONSTRAINT IF EXISTS user_preferences_session_id_fkey"
    )
    op.create_foreign_key(
        None,
        "user_preferences",
        "sessions",
        ["session_id"],
        ["id"],
        ondelete="CASCADE",
    )

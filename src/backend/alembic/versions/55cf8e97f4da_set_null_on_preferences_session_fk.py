"""set_null_on_preferences_session_fk

Revision ID: 55cf8e97f4da
Revises: 8a2a49d76d6a
Create Date: 2026-05-29 21:39:36.766246

Change user_preferences.session_id FK from ON DELETE CASCADE to ON DELETE SET NULL
so that user preferences survive logout (session deletion).
"""

import re
from collections.abc import Sequence

from sqlalchemy import text

from alembic import op

revision: str = "55cf8e97f4da"
down_revision: str | None = "8a2a49d76d6a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _replace_session_fk_sqlite(ondelete: str) -> None:
    """Recreate user_preferences table with updated FK ondelete behavior.

    SQLite does not support ALTER TABLE … DROP|ADD CONSTRAINT, and its FK
    constraints are unnamed (inline in CREATE TABLE), defeating batch mode's
    named-constraint lookup. Instead we extract the current DDL from
    sqlite_master, rewrite the FK clause, copy data, and swap.
    """
    conn = op.get_bind()
    result = conn.execute(
        text("SELECT sql FROM sqlite_master WHERE type='table' AND name='user_preferences'")
    )
    create_sql = result.scalar()
    if create_sql is None:
        return

    # Replace ON DELETE <action> with the target action.
    # Enumerate ANSI SQL actions explicitly — \w+ does not capture
    # multi-word actions (SET NULL, NO ACTION, SET DEFAULT).
    new_sql = re.sub(
        r"REFERENCES\s+sessions\s*\(\s*id\s*\)\s*ON\s+DELETE\s+"
        r"(?:CASCADE|RESTRICT|NO\s+ACTION|SET\s+NULL|SET\s+DEFAULT)",
        f"REFERENCES sessions(id) ON DELETE {ondelete}",
        create_sql,
        flags=re.IGNORECASE,
    )
    if new_sql == create_sql:
        raise RuntimeError(
            "Failed to locate user_preferences.session_id FK clause in DDL "
            f"(schema drift?). DDL:\n{create_sql}"
        )

    # PRAGMA foreign_keys is only effective outside a transaction.
    # Alembic logs "Will assume non-transactional DDL" for SQLite,
    # so these take effect, but they would be silently ignored if
    # transaction_per_migration=True were ever set.
    op.execute("PRAGMA foreign_keys = OFF")
    op.execute("ALTER TABLE user_preferences RENAME TO _alembic_tmp_user_preferences")
    op.execute(text(new_sql))
    op.execute(
        "INSERT INTO user_preferences SELECT * FROM _alembic_tmp_user_preferences"
    )
    op.execute("DROP TABLE _alembic_tmp_user_preferences")
    op.execute("PRAGMA foreign_keys = ON")


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        _replace_session_fk_sqlite("SET NULL")
    else:
        op.execute(
            "ALTER TABLE user_preferences DROP CONSTRAINT IF EXISTS "
            "user_preferences_session_id_fkey"
        )
        op.create_foreign_key(
            "user_preferences_session_id_fkey",
            "user_preferences",
            "sessions",
            ["session_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        _replace_session_fk_sqlite("CASCADE")
    else:
        op.execute(
            "ALTER TABLE user_preferences DROP CONSTRAINT IF EXISTS "
            "user_preferences_session_id_fkey"
        )
        op.create_foreign_key(
            "user_preferences_session_id_fkey",
            "user_preferences",
            "sessions",
            ["session_id"],
            ["id"],
            ondelete="CASCADE",
        )

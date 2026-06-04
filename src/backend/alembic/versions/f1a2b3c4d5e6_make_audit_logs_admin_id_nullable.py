"""make audit_logs.admin_id nullable (#370)

The admin_id FK uses ON DELETE SET NULL, which is incoherent with a
NOT NULL column: deleting a referenced admin would attempt to set NULL
on a non-nullable column (IntegrityError on PostgreSQL). This migration
makes the column nullable so SET NULL is consistent, and lets audit
entries be written with admin_id=NULL when the actor is unknown
(instead of the invalid "unknown" sentinel that violated the FK).

Revision ID: f1a2b3c4d5e6
Revises: a1b2c3d4e5f6
Create Date: 2026-06-03 09:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f1a2b3c4d5e6"
down_revision: str | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # batch_alter_table keeps the change portable to SQLite (table rebuild).
    with op.batch_alter_table("audit_logs") as batch_op:
        batch_op.alter_column(
            "admin_id",
            existing_type=sa.String(),
            nullable=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("audit_logs") as batch_op:
        batch_op.alter_column(
            "admin_id",
            existing_type=sa.String(),
            nullable=False,
        )

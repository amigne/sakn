"""add 'cli' to oui_sync_log.triggered_by CHECK constraint

The `sakn-cli sync-oui` command (Sprint 6) records runs with
triggered_by="cli", but the original constraint only allowed
'scheduler' and 'admin', so the first CLI run failed with an
IntegrityError. Broaden the constraint to include 'cli'.

Revision ID: c5d6e7f8a9b0
Revises: f1a2b3c4d5e6
Create Date: 2026-06-03 09:30:00.000000
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c5d6e7f8a9b0"
down_revision: str | None = "f1a2b3c4d5e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CONSTRAINT = "ck_oui_sync_log_triggered_by"


def upgrade() -> None:
    # batch_alter_table rebuilds the table on SQLite (portable); on PostgreSQL
    # it emits a plain DROP/ADD CONSTRAINT.
    with op.batch_alter_table("oui_sync_log") as batch_op:
        batch_op.drop_constraint(_CONSTRAINT, type_="check")
        batch_op.create_check_constraint(
            _CONSTRAINT,
            "triggered_by IN ('scheduler', 'admin', 'cli')",
        )


def downgrade() -> None:
    with op.batch_alter_table("oui_sync_log") as batch_op:
        batch_op.drop_constraint(_CONSTRAINT, type_="check")
        batch_op.create_check_constraint(
            _CONSTRAINT,
            "triggered_by IN ('scheduler', 'admin')",
        )

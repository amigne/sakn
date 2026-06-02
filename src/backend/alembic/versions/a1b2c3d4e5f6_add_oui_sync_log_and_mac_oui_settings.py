"""add oui_sync_log table and mac_oui default settings

Revision ID: a1b2c3d4e5f6
Revises: 93ecd1cea639
Create Date: 2026-06-02 10:00:00.000000
"""

import uuid
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "93ecd1cea639"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Default MAC OUI settings
MAC_OUI_DEFAULT_SETTINGS: list[dict[str, str]] = [
    {"key": "module.mac_oui.MAC_OUI_FRONTEND_INPUT_MAX_CHARS", "value": "50000"},
    {"key": "module.mac_oui.MAC_OUI_BACKEND_BATCH_MAX_SIZE", "value": "2000"},
    {"key": "module.mac_oui.MAC_OUI_HISTORY_PAGE_SIZE", "value": "10"},
    {"key": "module.mac_oui.OUI_SYNC_HOUR", "value": "3"},
]


def upgrade() -> None:
    # --- Create oui_sync_log table (portable: create_table works on SQLite & PG) ---
    op.create_table(
        "oui_sync_log",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("triggered_by", sa.String(20), nullable=False),
        sa.Column(
            "triggered_by_user_id",
            sa.String(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("added", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("changed", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("confirmed", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("files_failed", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "triggered_by IN ('scheduler', 'admin')",
            name="ck_oui_sync_log_triggered_by",
        ),
        sa.CheckConstraint(
            "status IN ('running', 'success', 'partial', 'failed')",
            name="ck_oui_sync_log_status",
        ),
    )
    op.create_index(
        "ix_oui_sync_log_started_at_desc",
        "oui_sync_log",
        [sa.text("started_at DESC")],
    )

    # --- Insert default MAC OUI settings (idempotent: skip if key exists) ---
    # Use Python-side uuid4() for portable ID generation.
    for s in MAC_OUI_DEFAULT_SETTINGS:
        row_id = str(uuid.uuid4())
        op.execute(
            sa.text(
                "INSERT INTO global_settings (id, key, value) "
                "SELECT :id, :key, :value "
                "WHERE NOT EXISTS (SELECT 1 FROM global_settings WHERE key = :key2)"
            ).bindparams(id=row_id, key=s["key"], value=s["value"], key2=s["key"])
        )


def downgrade() -> None:
    op.drop_index("ix_oui_sync_log_started_at_desc", table_name="oui_sync_log")
    op.drop_table("oui_sync_log")
    # We intentionally do NOT delete the 4 settings rows in downgrade —
    # they are idempotent inserts; removing them could break a running app.
    # If a full rollback is needed, delete manually:
    #   DELETE FROM global_settings WHERE key LIKE 'module.mac_oui.%'

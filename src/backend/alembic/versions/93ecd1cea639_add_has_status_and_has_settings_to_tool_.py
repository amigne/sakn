"""add has_status and has_settings to tool_module

Revision ID: 93ecd1cea639
Revises: dd34a44b95cf
Create Date: 2026-06-01 19:23:48.785225
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "93ecd1cea639"
down_revision: str | None = "dd34a44b95cf"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Pre-compute the mac_oui tool module id for idempotent seed.
# Using a stable UUIDv7-like pattern based on a namespace (RFC 9562 style).
# In practice the runtime seed in main.py will create the row with a UUIDv7,
# so we only backfill here if the row already exists from a prior startup.
MAC_OUI_TOOL_NAME = "mac_oui"


def upgrade() -> None:
    # --- Schema change: add has_settings and has_status to tool_modules -------
    # Must use batch_alter_table for SQLite compatibility (project decision
    # 2026-05-31: SQLite is a supported production target for small setups).
    with op.batch_alter_table("tool_modules") as batch_op:
        batch_op.add_column(
            sa.Column(
                "has_settings",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )
        batch_op.add_column(
            sa.Column(
                "has_status",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )

    # --- Data migration: backfill mac_oui tool if it exists -------------------
    # Idempotent: UPDATE the has_status flag for the mac_oui tool row if it
    # was already created by a prior startup.  The has_settings flag follows
    # the same logic.
    #
    # If the row does not exist yet, this is a no-op — main.py will create it
    # at next startup with the correct flags.
    op.execute(
        sa.text(
            "UPDATE tool_modules SET has_settings = true, has_status = true "
            "WHERE name = :name"
        ).bindparams(name=MAC_OUI_TOOL_NAME)
    )


def downgrade() -> None:
    with op.batch_alter_table("tool_modules") as batch_op:
        batch_op.drop_column("has_status")
        batch_op.drop_column("has_settings")

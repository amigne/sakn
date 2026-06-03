"""Add UniqueConstraint on rate_limit_configs (role, tool_id)

Revision ID: 9e3d5a7b8c2f
Revises: 55cf8e97f4da
Create Date: 2026-06-03

Strategy (ADR-006):
1. Dedup: DELETE rows where id is not the MIN(id) for its (role, tool_id) group
   UUIDv7 is time-sortable → MIN(id) = oldest = original seed row
2. Add UniqueConstraint + index on (role, tool_id)
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9e3d5a7b8c2f"
down_revision: str | None = "55cf8e97f4da"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Step 1: Dedup — keep the oldest row for each (role, tool_id) group.
    # NULL tool_ids (global limits) are handled correctly: NULL != NULL in SQL,
    # so each row with tool_id IS NULL is treated as a separate group entry.
    op.execute(sa.text("""
        DELETE FROM rate_limit_configs
        WHERE id NOT IN (
            SELECT MIN(id) FROM rate_limit_configs GROUP BY role, tool_id
        )
    """))

    # Step 2: Add unique constraint
    op.create_unique_constraint(
        "uq_rate_limit_config_role_tool",
        "rate_limit_configs",
        ["role", "tool_id"],
    )

    # Step 3: Add index for lookups
    op.create_index(
        "ix_rate_limit_config_role_tool",
        "rate_limit_configs",
        ["role", "tool_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_rate_limit_config_role_tool", table_name="rate_limit_configs")
    op.drop_constraint("uq_rate_limit_config_role_tool", table_name="rate_limit_configs")

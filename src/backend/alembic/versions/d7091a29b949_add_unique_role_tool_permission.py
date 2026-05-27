"""Add UniqueConstraint on role_tool_permissions (role, tool_id)

Revision ID: d7091a29b949
Revises: 4cf8dd599766
Create Date: 2026-05-21

Strategy (ADR-006):
1. Dedup: DELETE rows where id is not the MIN(id) for its (role, tool_id) group
   UUIDv7 is time-sortable → MIN(id) = oldest = original seed row
2. Add UniqueConstraint + index on (role, tool_id)
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d7091a29b949"
down_revision: str | None = "4cf8dd599766"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Step 1: Dedup — keep the oldest row for each (role, tool_id) group
    op.execute(sa.text("""
        DELETE FROM role_tool_permissions
        WHERE id NOT IN (
            SELECT MIN(id) FROM role_tool_permissions GROUP BY role, tool_id
        )
    """))

    # Step 2: Add unique constraint
    op.create_unique_constraint(
        "uq_role_tool_permission_role_tool",
        "role_tool_permissions",
        ["role", "tool_id"],
    )

    # Step 3: Add index for lookups
    op.create_index(
        "ix_role_tool_permission_role_tool",
        "role_tool_permissions",
        ["role", "tool_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_role_tool_permission_role_tool", table_name="role_tool_permissions")
    op.drop_constraint("uq_role_tool_permission_role_tool", table_name="role_tool_permissions")

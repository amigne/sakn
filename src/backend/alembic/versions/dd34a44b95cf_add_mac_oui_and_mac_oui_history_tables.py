"""add mac_oui and mac_oui_history tables

Revision ID: dd34a44b95cf
Revises: 55cf8e97f4da
Create Date: 2026-05-31 14:53:20.555832
"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "dd34a44b95cf"
down_revision: str | None = "55cf8e97f4da"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "mac_oui",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("oui", sa.String(12), nullable=False),
        sa.Column("oui_type", sa.String(4), nullable=False),
        sa.Column("organization", sa.String(255), nullable=False),
        sa.Column("address", sa.Text(), nullable=False),
        sa.Column("first_seen", sa.Date(), nullable=False),
        sa.Column("last_seen", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "oui_type IN ('MA-L', 'MA-M', 'MA-S')",
            name="ck_mac_oui_oui_type",
        ),
        sa.UniqueConstraint("oui", "oui_type", name="uq_mac_oui_oui_type"),
    )
    op.create_index("ix_mac_oui_oui", "mac_oui", ["oui"])
    op.create_index("ix_mac_oui_oui_type", "mac_oui", ["oui_type"])

    op.create_table(
        "mac_oui_history",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column(
            "oui_id",
            sa.String(),
            sa.ForeignKey("mac_oui.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("oui", sa.String(12), nullable=False),
        sa.Column("previous_organization", sa.String(255), nullable=False),
        sa.Column("new_organization", sa.String(255), nullable=False),
        sa.Column("previous_address", sa.Text(), nullable=True),
        sa.Column("new_address", sa.Text(), nullable=True),
        sa.Column("change_type", sa.String(20), nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "change_type IN ('name_change', 'address_change', 'revoked')",
            name="ck_mac_oui_history_change_type",
        ),
    )
    op.create_index("ix_mac_oui_history_oui_id", "mac_oui_history", ["oui_id"])
    op.create_index("ix_mac_oui_history_detected_at", "mac_oui_history", ["detected_at"])


def downgrade() -> None:
    op.drop_index("ix_mac_oui_history_detected_at", table_name="mac_oui_history")
    op.drop_index("ix_mac_oui_history_oui_id", table_name="mac_oui_history")
    op.drop_table("mac_oui_history")
    op.drop_index("ix_mac_oui_oui_type", table_name="mac_oui")
    op.drop_index("ix_mac_oui_oui", table_name="mac_oui")
    op.drop_table("mac_oui")

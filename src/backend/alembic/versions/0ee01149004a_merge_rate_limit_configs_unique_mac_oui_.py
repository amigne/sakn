"""merge rate_limit_configs unique + mac_oui heads (#418)

Revision ID: 0ee01149004a
Revises: c5d6e7f8a9b0, 9e3d5a7b8c2f
Create Date: 2026-06-04 10:19:51.326608

No-op merge migration: unites the two Alembic heads that both descend from
55cf8e97f4da — 9e3d5a7b8c2f (rate_limit_configs UNIQUE, dev0.2.0) and the
MAC OUI chain head c5d6e7f8a9b0 (dev0.2.0-macoui). See #418.
"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "0ee01149004a"
down_revision: tuple[str, ...] = ("c5d6e7f8a9b0", "9e3d5a7b8c2f")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

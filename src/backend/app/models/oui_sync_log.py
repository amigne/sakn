"""OuiSyncLog — persistent log of IEEE OUI sync executions (Sprint 5).

Each row records one invocation of the OUI sync service (scheduled or manual).
The service writes a row at start (status='running') and updates it at finish.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUID7Mixin


class OuiSyncLog(Base, UUID7Mixin):
    __tablename__ = "oui_sync_log"

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    triggered_by: Mapped[str] = mapped_column(
        String(20), nullable=False
    )
    triggered_by_user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False
    )
    added: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    changed: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    confirmed: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    files_failed: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # JSON array, e.g. '["MA-L"]'
    error_message: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )

    __table_args__ = (
        Index("ix_oui_sync_log_started_at_desc", started_at.desc()),
    )

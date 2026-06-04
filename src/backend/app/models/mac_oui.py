from __future__ import annotations

from datetime import date

from sqlalchemy import CheckConstraint, Date, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUID7Mixin


class MacOui(Base, UUID7Mixin, TimestampMixin):
    __tablename__ = "mac_oui"

    oui: Mapped[str] = mapped_column(String(12), nullable=False)
    oui_type: Mapped[str] = mapped_column(String(4), nullable=False)
    organization: Mapped[str] = mapped_column(String(255), nullable=False)
    address: Mapped[str] = mapped_column(Text(), nullable=False)
    first_seen: Mapped[date] = mapped_column(Date(), nullable=False)
    last_seen: Mapped[date] = mapped_column(Date(), nullable=False)

    history: Mapped[list[MacOuiHistory]] = relationship(  # noqa: F821
        "MacOuiHistory",
        cascade="all, delete-orphan",
        order_by="MacOuiHistory.detected_at",
        back_populates="parent",
    )

    __table_args__ = (
        CheckConstraint(
            "oui_type IN ('MA-L', 'MA-M', 'MA-S')",
            name="ck_mac_oui_oui_type",
        ),
        UniqueConstraint("oui", "oui_type", name="uq_mac_oui_oui_type"),
        Index("ix_mac_oui_oui", "oui"),
        Index("ix_mac_oui_oui_type", "oui_type"),
    )

    def __repr__(self) -> str:
        return f"<MacOui oui={self.oui} type={self.oui_type}>"

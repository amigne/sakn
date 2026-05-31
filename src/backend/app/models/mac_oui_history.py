from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUID7Mixin


class MacOuiHistory(Base, UUID7Mixin):
    __tablename__ = "mac_oui_history"

    oui_id: Mapped[str] = mapped_column(
        ForeignKey("mac_oui.id", ondelete="CASCADE"), nullable=False
    )
    oui: Mapped[str] = mapped_column(String(12), nullable=False)
    previous_organization: Mapped[str] = mapped_column(String(255), nullable=False)
    new_organization: Mapped[str] = mapped_column(String(255), nullable=False)
    previous_address: Mapped[str | None] = mapped_column(Text(), nullable=True)
    new_address: Mapped[str | None] = mapped_column(Text(), nullable=True)
    change_type: Mapped[str] = mapped_column(String(20), nullable=False)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    parent = relationship("MacOui", back_populates="history")

    __table_args__ = (
        CheckConstraint(
            "change_type IN ('name_change', 'address_change', 'revoked')",
            name="ck_mac_oui_history_change_type",
        ),
        Index("ix_mac_oui_history_oui_id", "oui_id"),
        Index("ix_mac_oui_history_detected_at", "detected_at"),
    )

    def __repr__(self) -> str:
        return f"<MacOuiHistory oui={self.oui} type={self.change_type}>"

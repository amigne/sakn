from datetime import datetime

from sqlalchemy import String, Integer, DateTime, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUID7Mixin, utcnow


class ToolExecutionLog(Base, UUID7Mixin):
    __tablename__ = "tool_execution_logs"

    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    session_id: Mapped[str | None] = mapped_column(ForeignKey("sessions.id", ondelete="SET NULL"), nullable=True)
    source_ip: Mapped[str] = mapped_column(String(45), nullable=False)
    tool_name: Mapped[str] = mapped_column(String(64), nullable=False)
    parameters: Mapped[str] = mapped_column(Text, nullable=False)  # JSONB → Text for SQLite compat
    result: Mapped[str] = mapped_column(String(20), nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, index=True
    )


class SecurityEventLog(Base, UUID7Mixin):
    __tablename__ = "security_event_logs"

    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    source_ip: Mapped[str] = mapped_column(String(45), nullable=False)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    details: Mapped[str] = mapped_column(Text, nullable=False)  # JSONB → Text
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, index=True
    )


class AuditLog(Base, UUID7Mixin):
    __tablename__ = "audit_logs"

    admin_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(64), nullable=False)
    old_value: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSONB → Text
    new_value: Mapped[str] = mapped_column(Text, nullable=False)  # JSONB → Text
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, index=True
    )

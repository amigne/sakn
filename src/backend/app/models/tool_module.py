from sqlalchemy import String, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUID7Mixin, TimestampMixin


class ToolModule(Base, UUID7Mixin, TimestampMixin):
    __tablename__ = "tool_modules"

    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    display_name_key: Mapped[str] = mapped_column(String(128), nullable=False)
    description_key: Mapped[str] = mapped_column(String(128), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    version: Mapped[str] = mapped_column(String(20), nullable=False)


class RoleToolPermission(Base, UUID7Mixin):
    __tablename__ = "role_tool_permissions"

    role: Mapped[str] = mapped_column(String(20), nullable=False)
    tool_id: Mapped[str] = mapped_column(ForeignKey("tool_modules.id", ondelete="CASCADE"), nullable=False)
    allowed: Mapped[bool] = mapped_column(Boolean, nullable=False)

    __table_args__ = (
        UniqueConstraint("role", "tool_id", name="uq_role_tool_permission_role_tool"),
    )


class RateLimitConfig(Base, UUID7Mixin):
    __tablename__ = "rate_limit_configs"

    role: Mapped[str] = mapped_column(String(20), nullable=False)
    tool_id: Mapped[str | None] = mapped_column(ForeignKey("tool_modules.id", ondelete="CASCADE"), nullable=True)
    soft_limit: Mapped[int] = mapped_column(nullable=False, default=0)
    hard_limit: Mapped[int] = mapped_column(nullable=False, default=0)
    window_seconds: Mapped[int] = mapped_column(nullable=False, default=60)


class DnsServerPreset(Base, UUID7Mixin):
    __tablename__ = "dns_server_presets"

    tool_module_id: Mapped[str] = mapped_column(
        ForeignKey("tool_modules.id", ondelete="CASCADE"), nullable=False
    )
    ip_address: Mapped[str] = mapped_column(String(45), nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    sort_order: Mapped[int] = mapped_column(nullable=False, default=0)

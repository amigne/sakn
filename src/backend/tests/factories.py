from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    DnsServerPreset,
    EmailVerification,
    GlobalSetting,
    PasswordReset,
    RateLimitConfig,
    RoleToolPermission,
    Session,
    ToolModule,
    User,
    UserPreference,
)
from app.constants.roles import ROLE_AUTHENTICATED
from app.models.base import new_uuid7


def utcnow() -> datetime:
    return datetime.now(UTC)


async def create_user(
    db: AsyncSession,
    *,
    email: str = "test@example.com",
    password_hash: str = "hashed_password",
    role: str = ROLE_AUTHENTICATED,
    status: str = "active",
    email_verified: bool = True,
) -> User:
    user = User(
        id=new_uuid7(),
        email=email,
        password_hash=password_hash,
        role=role,
        status=status,
        email_verified_at=utcnow() if email_verified else None,
    )
    db.add(user)
    await db.flush()
    return user


async def create_session(
    db: AsyncSession,
    *,
    user_id: str | None = None,
    token_hash: str | None = None,
    ip_address: str = "127.0.0.1",
) -> Session:
    session = Session(
        id=new_uuid7(),
        user_id=user_id,
        token_hash=token_hash or f"hash_{new_uuid7()}",
        ip_address=ip_address,
        expires_at=utcnow() + timedelta(hours=24),
    )
    db.add(session)
    await db.flush()
    return session


async def create_tool_module(
    db: AsyncSession,
    *,
    name: str = "ping",
    enabled: bool = True,
) -> ToolModule:
    tool = ToolModule(
        id=new_uuid7(),
        name=name,
        display_name_key=f"tools.{name}.name",
        description_key=f"tools.{name}.description",
        enabled=enabled,
        version="1.0.0",
    )
    db.add(tool)
    await db.flush()
    return tool


async def create_role_permission(
    db: AsyncSession,
    *,
    role: str = ROLE_AUTHENTICATED,
    tool_id: str,
    allowed: bool = True,
) -> RoleToolPermission:
    perm = RoleToolPermission(
        id=new_uuid7(),
        role=role,
        tool_id=tool_id,
        allowed=allowed,
    )
    db.add(perm)
    await db.flush()
    return perm


async def create_rate_limit_config(
    db: AsyncSession,
    *,
    role: str = ROLE_AUTHENTICATED,
    tool_id: str | None = None,
    soft_limit: int = 0,
    hard_limit: int = 0,
) -> RateLimitConfig:
    config = RateLimitConfig(
        id=new_uuid7(),
        role=role,
        tool_id=tool_id,
        soft_limit=soft_limit,
        hard_limit=hard_limit,
    )
    db.add(config)
    await db.flush()
    return config


async def create_dns_server_preset(
    db: AsyncSession,
    *,
    tool_module_id: str,
    ip_address: str = "8.8.8.8",
    description: str = "Google DNS",
    sort_order: int = 0,
) -> DnsServerPreset:
    preset = DnsServerPreset(
        id=new_uuid7(),
        tool_module_id=tool_module_id,
        ip_address=ip_address,
        description=description,
        sort_order=sort_order,
    )
    db.add(preset)
    await db.flush()
    return preset


async def create_user_preference(
    db: AsyncSession,
    *,
    user_id: str | None = None,
    session_id: str | None = None,
    key: str = "theme",
    value: str = "dark",
) -> UserPreference:
    pref = UserPreference(
        id=new_uuid7(),
        user_id=user_id,
        session_id=session_id,
        key=key,
        value=value,
    )
    db.add(pref)
    await db.flush()
    return pref


async def create_email_verification(
    db: AsyncSession,
    *,
    user_id: str,
    token_hash: str | None = None,
    used: bool = False,
) -> EmailVerification:
    ev = EmailVerification(
        id=new_uuid7(),
        user_id=user_id,
        token_hash=token_hash or f"hash_{new_uuid7()}",
        expires_at=utcnow() + timedelta(hours=24),
        used=used,
    )
    db.add(ev)
    await db.flush()
    return ev


async def create_password_reset(
    db: AsyncSession,
    *,
    user_id: str,
    token_hash: str | None = None,
    used: bool = False,
) -> PasswordReset:
    pr = PasswordReset(
        id=new_uuid7(),
        user_id=user_id,
        token_hash=token_hash or f"hash_{new_uuid7()}",
        expires_at=utcnow() + timedelta(hours=1),
        used=used,
    )
    db.add(pr)
    await db.flush()
    return pr


async def create_global_setting(
    db: AsyncSession,
    *,
    key: str = "log_retention_days",
    value: str = "90",
) -> GlobalSetting:
    setting = GlobalSetting(
        id=new_uuid7(),
        key=key,
        value=value,
    )
    db.add(setting)
    await db.flush()
    return setting

import pytest
from sqlalchemy import select

from app.models import User, Session, ToolModule, RoleToolPermission, RateLimitConfig, GlobalSetting
from tests.factories import (
    create_user,
    create_session,
    create_tool_module,
    create_role_permission,
    create_rate_limit_config,
    create_global_setting,
    create_user_preference,
    create_email_verification,
    create_password_reset,
    create_dns_server_preset,
)


@pytest.mark.asyncio
async def test_create_user(db_session):
    user = await create_user(db_session, email="test@example.com", role="authenticated", status="active")
    assert user.id is not None
    assert user.email == "test@example.com"
    assert user.role == "authenticated"
    assert user.status == "active"


@pytest.mark.asyncio
async def test_user_defaults(db_session):
    user = User(
        email="new@example.com",
        password_hash="hash",
    )
    db_session.add(user)
    await db_session.flush()
    assert user.role == "authenticated"
    assert user.status == "pending"
    assert user.failed_login_attempts == 0
    assert user.locked_until is None


@pytest.mark.asyncio
async def test_user_unique_email(db_session):
    await create_user(db_session, email="dup@example.com")
    user2 = User(email="dup@example.com", password_hash="hash")
    db_session.add(user2)
    with pytest.raises(Exception):
        await db_session.flush()


@pytest.mark.asyncio
async def test_create_session(db_session):
    user = await create_user(db_session)
    sess = await create_session(db_session, user_id=user.id, ip_address="10.0.0.1")
    assert sess.id is not None
    assert sess.user_id == user.id
    assert sess.ip_address == "10.0.0.1"
    assert sess.token_hash.startswith("hash_")


@pytest.mark.asyncio
async def test_session_visitor(db_session):
    sess = await create_session(db_session, user_id=None)
    assert sess.user_id is None


@pytest.mark.asyncio
async def test_create_tool_module(db_session):
    tool = await create_tool_module(db_session, name="test_models_create")
    assert tool.name == "test_models_create"
    assert tool.enabled is True
    assert tool.version == "1.0.0"


@pytest.mark.asyncio
async def test_tool_module_unique_name(db_session):
    await create_tool_module(db_session, name="test_models_unique")
    tool2 = ToolModule(name="test_models_unique", display_name_key="k", description_key="d", version="1.0.0")
    db_session.add(tool2)
    with pytest.raises(Exception):
        await db_session.flush()


@pytest.mark.asyncio
async def test_create_role_permission(db_session):
    tool = await create_tool_module(db_session, name="test_models_perm")
    perm = await create_role_permission(db_session, role="visitor", tool_id=tool.id)
    assert perm.role == "visitor"
    assert perm.tool_id == tool.id
    assert perm.allowed is True


@pytest.mark.asyncio
async def test_role_permission_unique_constraint(db_session):
    """Inserting a duplicate (role, tool_id) must raise IntegrityError."""
    from sqlalchemy.exc import IntegrityError
    from app.models.base import new_uuid7
    from app.models.tool_module import RoleToolPermission

    tool = await create_tool_module(db_session, name="unique-ping")

    perm1 = RoleToolPermission(id=new_uuid7(), role="visitor", tool_id=tool.id, allowed=True)
    db_session.add(perm1)
    await db_session.flush()

    perm2 = RoleToolPermission(id=new_uuid7(), role="visitor", tool_id=tool.id, allowed=False)
    db_session.add(perm2)
    with pytest.raises(IntegrityError):
        await db_session.flush()


@pytest.mark.asyncio
async def test_create_rate_limit_config(db_session):
    config = await create_rate_limit_config(db_session, role="authenticated", soft_limit=1, hard_limit=500)
    assert config.role == "authenticated"
    assert config.soft_limit == 1
    assert config.hard_limit == 500
    assert config.tool_id is None  # global


@pytest.mark.asyncio
async def test_rate_limit_config_per_tool(db_session):
    tool = await create_tool_module(db_session, name="dns_lookup")
    config = await create_rate_limit_config(db_session, role="authenticated", tool_id=tool.id, soft_limit=2)
    assert config.tool_id == tool.id
    assert config.soft_limit == 2


@pytest.mark.asyncio
async def test_create_user_preference(db_session):
    user = await create_user(db_session)
    pref = await create_user_preference(db_session, user_id=user.id, key="theme", value="dark")
    assert pref.user_id == user.id
    assert pref.key == "theme"
    assert pref.value == "dark"


@pytest.mark.asyncio
async def test_create_email_verification(db_session):
    user = await create_user(db_session)
    ev = await create_email_verification(db_session, user_id=user.id)
    assert ev.user_id == user.id
    assert ev.used is False
    assert ev.expires_at is not None


@pytest.mark.asyncio
async def test_create_password_reset(db_session):
    user = await create_user(db_session)
    pr = await create_password_reset(db_session, user_id=user.id)
    assert pr.user_id == user.id
    assert pr.used is False
    assert pr.expires_at is not None


@pytest.mark.asyncio
async def test_create_dns_server_preset(db_session):
    tool = await create_tool_module(db_session, name="dns_lookup")
    preset = await create_dns_server_preset(db_session, tool_module_id=tool.id)
    assert preset.tool_module_id == tool.id
    assert preset.ip_address == "8.8.8.8"
    assert preset.sort_order == 0


@pytest.mark.asyncio
async def test_create_global_setting(db_session):
    setting = await create_global_setting(db_session, key="log_retention_days", value="90")
    assert setting.key == "log_retention_days"
    assert setting.value == "90"


@pytest.mark.asyncio
async def test_global_setting_unique_key(db_session):
    await create_global_setting(db_session, key="x", value="1")
    setting2 = GlobalSetting(key="x", value="2")
    db_session.add(setting2)
    with pytest.raises(Exception):
        await db_session.flush()

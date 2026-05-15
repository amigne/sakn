from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import UserPreference
from app.models.base import new_uuid7

VALID_PREFERENCES = {"language", "locale", "theme", "display_mode"}


async def get_preferences(db: AsyncSession, *, user_id: str | None, session_id: str | None) -> dict:
    """Get preferences for a user or session. Returns key-value dict."""
    if user_id:
        result = await db.execute(
            select(UserPreference).where(UserPreference.user_id == user_id)
        )
    elif session_id:
        result = await db.execute(
            select(UserPreference).where(UserPreference.session_id == session_id)
        )
    else:
        return {}

    prefs = result.scalars().all()
    return {p.key: p.value for p in prefs}


async def set_preferences(
    db: AsyncSession,
    *,
    user_id: str | None,
    session_id: str | None,
    updates: dict[str, str],
) -> dict:
    """Set preferences for a user or session. Only valid keys are stored."""
    for key, value in updates.items():
        if key not in VALID_PREFERENCES:
            continue

        if user_id:
            result = await db.execute(
                select(UserPreference).where(
                    UserPreference.user_id == user_id,
                    UserPreference.key == key,
                )
            )
        elif session_id:
            result = await db.execute(
                select(UserPreference).where(
                    UserPreference.session_id == session_id,
                    UserPreference.key == key,
                )
            )
        else:
            continue

        pref = result.scalar_one_or_none()
        if pref:
            pref.value = value
        else:
            pref = UserPreference(
                id=new_uuid7(),
                user_id=user_id,
                session_id=session_id,
                key=key,
                value=value,
            )
            db.add(pref)

    await db.flush()
    return await get_preferences(db, user_id=user_id, session_id=session_id)

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.preferences import UserPreference


async def cleanup_orphan_preferences(db: AsyncSession) -> int:
    """Delete user_preferences rows where both user_id and session_id are NULL.

    These rows become unreachable after ON DELETE SET NULL on anonymous sessions
    (migration #296). The revoke() path handles the common case synchronously;
    this periodic cleanup catches any rows that may have been left behind by
    edge cases (e.g. direct session expiration, Redis-only cleanup).

    Returns the number of deleted rows.
    """
    result = await db.execute(
        delete(UserPreference).where(
            UserPreference.user_id.is_(None),
            UserPreference.session_id.is_(None),
        )
    )
    # NOTE: result.rowcount is reliable with asyncpg and aiosqlite (the two
    # supported backends). If the DB driver changes, verify rowcount semantics
    # for Core-level DELETE statements on the new dialect.
    return result.rowcount

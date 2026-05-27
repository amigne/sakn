from datetime import UTC, datetime

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Session


async def cleanup_expired_anonymous_sessions(db: AsyncSession) -> int:
    """Delete anonymous sessions (user_id IS NULL) past expires_at. Returns rowcount."""
    result = await db.execute(
        delete(Session).where(
            Session.user_id.is_(None),
            Session.expires_at < datetime.now(UTC),
        )
    )
    return result.rowcount

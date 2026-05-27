from datetime import UTC, datetime, timedelta

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


async def cleanup_unverified_accounts(db: AsyncSession, retention_days: int = 7) -> int:
    """Delete unverified accounts older than retention_days. Returns count deleted."""
    cutoff = datetime.now(UTC) - timedelta(days=retention_days)
    result = await db.execute(
        delete(User).where(
            User.email_verified_at.is_(None),
            User.created_at < cutoff,
        )
    )
    await db.flush()
    return result.rowcount

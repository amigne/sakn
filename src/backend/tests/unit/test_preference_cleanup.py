"""Regression guards for issue #297: orphan preference cleanup."""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import new_uuid7
from app.models.preferences import UserPreference
from app.services.preference_cleanup_service import cleanup_orphan_preferences
from app.services.session_service import revoke
from tests.factories import create_session, create_user, create_user_preference


class TestRevokeAnonymousSessionCleansPreferences:
    """When an anonymous session is revoked, its preferences must be deleted
    synchronously — not left as (NULL, NULL) orphans after SET NULL."""

    @pytest.mark.asyncio
    async def test_revoke_anonymous_session_deletes_preferences(self, db_session: AsyncSession):
        # Create an anonymous session (user_id=None)
        session = await create_session(db_session, user_id=None)
        session_id = session.id

        # Add preferences for this anonymous session
        await create_user_preference(db_session, session_id=session_id, key="language", value="fr")

        # Verify preferences exist
        result = await db_session.execute(
            select(UserPreference).where(UserPreference.session_id == session_id)
        )
        assert len(result.scalars().all()) == 1

        # Revoke the anonymous session
        result_token = await revoke(db_session, session_id)
        assert result_token is not None

        # Preferences must be gone (not (NULL, NULL) orphans)
        result = await db_session.execute(
            select(UserPreference).where(UserPreference.session_id == session_id)
        )
        assert len(result.scalars().all()) == 0

    @pytest.mark.asyncio
    async def test_revoke_authenticated_session_preserves_preferences(self, db_session: AsyncSession):
        """Non-regression guard: authenticated user preferences must survive
        logout — that's what migration #296 was designed to protect."""
        # Create a user
        user = await create_user(db_session, email="pref-test@example.com")

        # Create an authenticated session
        session = await create_session(db_session, user_id=user.id)
        session_id = session.id

        # Add preferences tied to both user AND session
        await create_user_preference(
            db_session, user_id=user.id, session_id=session_id, key="theme", value="dark"
        )

        # Revoke the authenticated session
        result_token = await revoke(db_session, session_id)
        assert result_token is not None

        # Preferences must survive (user_id still set)
        result = await db_session.execute(
            select(UserPreference).where(UserPreference.user_id == user.id)
        )
        prefs = result.scalars().all()
        assert len(prefs) == 1
        assert prefs[0].key == "theme"
        assert prefs[0].value == "dark"
        # Session FK should be NULL now (SET NULL) but user FK intact
        assert prefs[0].session_id is None


class TestCleanupOrphanPreferences:
    """The periodic cleanup must remove only (NULL, NULL) rows,
    leaving valid preferences untouched."""

    @pytest.mark.asyncio
    async def test_cleanup_removes_only_null_null_rows(self, db_session: AsyncSession):
        # Insert a (NULL, NULL) orphan row (simulating what SET NULL leaves behind)
        # We bypass the factory and insert directly since factory requires a valid session/user
        orphan = UserPreference(
            id=new_uuid7(),
            user_id=None,
            session_id=None,
            key="language",
            value="en",
        )
        db_session.add(orphan)
        await db_session.flush()

        # Insert a valid row (authenticated user, no session)
        user = await create_user(db_session, email="orphan-test@example.com")
        await create_user_preference(db_session, user_id=user.id, key="theme", value="light")

        # Run cleanup
        deleted = await cleanup_orphan_preferences(db_session)
        assert deleted == 1, "Only the (NULL, NULL) row should be deleted"

        # Verify: orphan gone, valid row stays
        result = await db_session.execute(
            select(UserPreference).where(UserPreference.user_id.is_(None))
        )
        assert len(result.scalars().all()) == 0

        result = await db_session.execute(
            select(UserPreference).where(UserPreference.user_id == user.id)
        )
        assert len(result.scalars().all()) == 1

    @pytest.mark.asyncio
    async def test_cleanup_no_orphans_is_noop(self, db_session: AsyncSession):
        """When there are no orphans, cleanup should return 0 and not error."""
        # Insert only valid rows
        user = await create_user(db_session, email="noop-test@example.com")
        await create_user_preference(db_session, user_id=user.id, key="theme", value="dark")

        deleted = await cleanup_orphan_preferences(db_session)
        assert deleted == 0

        # Valid row untouched
        result = await db_session.execute(
            select(UserPreference).where(UserPreference.user_id == user.id)
        )
        assert len(result.scalars().all()) == 1

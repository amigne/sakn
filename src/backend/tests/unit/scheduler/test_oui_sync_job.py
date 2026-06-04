"""Covers #326 — OUI_SYNC_ENABLED gating on register_oui_sync_job."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.scheduler.jobs.oui_sync_job import register_oui_sync_job

pytestmark = pytest.mark.asyncio


async def test_register_oui_sync_job_disabled():
    """When OUI_SYNC_ENABLED=False, no job is registered."""
    scheduler = MagicMock()
    async_session_factory = AsyncMock()
    with (
        patch("app.scheduler.jobs.oui_sync_job.settings") as mock_settings,
    ):
        mock_settings.OUI_SYNC_ENABLED = False
        await register_oui_sync_job(scheduler, async_session_factory)
        scheduler.scheduled_job.assert_not_called()


async def test_register_oui_sync_job_enabled():
    """When OUI_SYNC_ENABLED=True, the job is registered."""
    scheduler = MagicMock()
    async_session_factory = AsyncMock()
    with (
        patch("app.scheduler.jobs.oui_sync_job.settings") as mock_settings,
        patch(
            "app.scheduler.jobs.oui_sync_job._get_effective_sync_hour",
            AsyncMock(return_value=4),
        ),
    ):
        mock_settings.OUI_SYNC_ENABLED = True
        mock_settings.OUI_SYNC_HOUR = 4
        await register_oui_sync_job(scheduler, async_session_factory)
        scheduler.scheduled_job.assert_called_once()

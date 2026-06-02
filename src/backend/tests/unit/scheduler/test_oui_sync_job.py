"""Covers #326 — OUI_SYNC_ENABLED gating on register_oui_sync_job."""

from unittest.mock import MagicMock, patch

from app.scheduler.jobs.oui_sync_job import register_oui_sync_job


def test_register_oui_sync_job_disabled():
    """When OUI_SYNC_ENABLED=False, no job is registered."""
    scheduler = MagicMock()
    with (
        patch("app.scheduler.jobs.oui_sync_job.settings") as mock_settings,
    ):
        mock_settings.OUI_SYNC_ENABLED = False
        register_oui_sync_job(scheduler, MagicMock())
        scheduler.scheduled_job.assert_not_called()


def test_register_oui_sync_job_enabled():
    """When OUI_SYNC_ENABLED=True, the job is registered."""
    scheduler = MagicMock()
    with (
        patch("app.scheduler.jobs.oui_sync_job.settings") as mock_settings,
    ):
        mock_settings.OUI_SYNC_ENABLED = True
        mock_settings.OUI_SYNC_HOUR = 4
        register_oui_sync_job(scheduler, MagicMock())
        scheduler.scheduled_job.assert_called_once()

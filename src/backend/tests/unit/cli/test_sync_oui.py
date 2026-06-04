"""Unit tests for the `sakn-cli sync-oui` command."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from click.testing import CliRunner

from app.cli.sync_oui import sync_oui
from app.services.oui_sync_service import SyncReport


def _patched_service(report: SyncReport):
    """Patch OuiSyncService so its instance.sync_all returns `report`."""
    instance = MagicMock()
    instance.sync_all = AsyncMock(return_value=report)
    return patch(
        "app.services.oui_sync_service.OuiSyncService",
        return_value=instance,
    ), instance


def test_sync_oui_success_reports_counts_and_exits_zero():
    report = SyncReport(added=3, changed=2, confirmed=10, files_failed=[])
    patcher, instance = _patched_service(report)
    with patcher:
        result = CliRunner().invoke(sync_oui, [])

    assert result.exit_code == 0
    assert "added:     3" in result.output
    assert "changed:   2" in result.output
    assert "confirmed: 10" in result.output
    # The CLI must tag the run as triggered_by="cli".
    instance.sync_all.assert_awaited_once_with(triggered_by="cli")


def test_sync_oui_files_failed_exits_one():
    report = SyncReport(added=1, changed=0, confirmed=0, files_failed=["MA-L"])
    patcher, _ = _patched_service(report)
    with patcher:
        result = CliRunner().invoke(sync_oui, [])

    assert result.exit_code == 1
    assert "MA-L" in result.output


def test_sync_oui_lock_held_exits_zero_with_message():
    # Empty report (no work, no failure) == sync_all returned early on the lock.
    report = SyncReport(added=0, changed=0, confirmed=0, files_failed=[])
    patcher, _ = _patched_service(report)
    with patcher:
        result = CliRunner().invoke(sync_oui, [])

    assert result.exit_code == 0
    assert "did not run" in result.output

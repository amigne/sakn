import asyncio
import sys

import click
import httpx

from app.config import settings
from app.database import async_session_factory


@click.command("sync-oui")
def sync_oui():
    """Force an on-demand IEEE MAC OUI synchronization.

    Downloads the three IEEE registries (MA-L / MA-M / MA-S) and updates the
    local OUI database, exactly like the daily scheduled job — without needing
    an authenticated admin HTTP call. The run is recorded in oui_sync_log with
    triggered_by="cli".

    If a sync is already running (lock held), the command reports it and exits 0.
    Exits 1 if one or more IEEE files failed to sync.
    """

    async def _run() -> int:
        from app.services.oui_sync_service import OuiSyncService

        http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(settings.OUI_DOWNLOAD_TIMEOUT_SECONDS),
            follow_redirects=False,
        )
        try:
            service = OuiSyncService(
                db_session_factory=async_session_factory,
                http_client=http_client,
            )
            report = await service.sync_all(triggered_by="cli")
        finally:
            await http_client.aclose()

        # A report with no work and no failures most likely means the lock was
        # held by a concurrent run (sync_all returns early in that case).
        if (
            report.added == 0
            and report.changed == 0
            and report.confirmed == 0
            and not report.files_failed
        ):
            click.echo("MAC OUI sync did not run (another sync may be in progress).")
            return 0

        click.echo("MAC OUI sync finished:")
        click.echo(f"  added:     {report.added}")
        click.echo(f"  changed:   {report.changed}")
        click.echo(f"  confirmed: {report.confirmed}")
        if report.files_failed:
            click.echo(f"  files failed: {', '.join(report.files_failed)}", err=True)
            return 1
        return 0

    sys.exit(asyncio.run(_run()))

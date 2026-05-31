"""APScheduler job for daily IEEE OUI sync."""

import logging

from app.config import settings

logger = logging.getLogger(__name__)


def register_oui_sync_job(scheduler, async_session_factory) -> None:
    """Register the OUI sync job on the APScheduler instance, if enabled."""

    if not settings.OUI_SYNC_ENABLED:
        logger.info("OUI sync job disabled (OUI_SYNC_ENABLED=False)")
        return

    @scheduler.scheduled_job(
        "cron",
        hour=settings.OUI_SYNC_HOUR,
        minute=0,
        timezone="UTC",
        max_instances=1,
        coalesce=True,
        id="oui_sync_daily",
        name="MAC OUI IEEE daily sync",
    )
    async def oui_sync_daily():
        import httpx

        from app.services.oui_sync_service import OuiSyncService

        logger.info("oui_sync_job_started")
        http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(settings.OUI_DOWNLOAD_TIMEOUT_SECONDS),
            follow_redirects=False,
        )
        try:
            service = OuiSyncService(
                db_session_factory=async_session_factory,
                http_client=http_client,
            )
            report = await service.sync_all()
            logger.info(
                "oui_sync_job_finished",
                extra={
                    "added": report.added,
                    "changed": report.changed,
                    "confirmed": report.confirmed,
                    "files_failed": report.files_failed,
                },
            )
        except Exception:
            logger.exception("oui_sync_job_failed")
        finally:
            await http_client.aclose()

    logger.info(
        "OUI sync job registered",
        extra={"hour": settings.OUI_SYNC_HOUR},
    )

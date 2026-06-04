"""APScheduler job for daily IEEE OUI sync."""

import logging

from sqlalchemy import select

from app.config import settings

logger = logging.getLogger(__name__)


async def _get_effective_sync_hour(async_session_factory) -> int:
    """Read DB-configured sync hour, fallback to env (M2)."""
    from app.models.preferences import GlobalSetting

    try:
        async with async_session_factory() as session:
            row = await session.execute(
                select(GlobalSetting).where(
                    GlobalSetting.key == "module.mac_oui.OUI_SYNC_HOUR"
                )
            )
            s = row.scalar_one_or_none()
            if s is not None:
                hour = int(s.value)
                if 0 <= hour <= 23:
                    return hour
    except Exception:
        logger.warning(
            "Could not read OUI_SYNC_HOUR from DB, using env fallback",
            exc_info=True,
        )
    return settings.OUI_SYNC_HOUR


async def register_oui_sync_job(scheduler, async_session_factory) -> None:
    """Register the OUI sync job, using the effective hour from DB (M2).

    Pre-fetches the DB-configured sync hour at startup so the cron trigger
    is immediately correct — no monkey-patching of ``scheduler.start`` or
    private ``_eventloop`` access, no artificial ``asyncio.sleep``.

    Multi-worker note: ``reschedule_job`` in
    ``admin_modules::update_module_settings`` only succeeds for the worker
    that owns the scheduler.  In multi-worker deployments, pin the
    scheduler to a single leader (e.g. ``SCHEDULER_ENABLED=1`` on worker 0);
    other workers will pick up the new hour at next restart via the
    DB read here.
    """
    if not settings.OUI_SYNC_ENABLED:
        logger.info("OUI sync job disabled (OUI_SYNC_ENABLED=False)")
        return

    hour = await _get_effective_sync_hour(async_session_factory)

    @scheduler.scheduled_job(
        "cron",
        hour=hour,
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
        extra={"effective_hour": hour},
    )

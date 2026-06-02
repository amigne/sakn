"""APScheduler job for daily IEEE OUI sync."""

import logging

from sqlalchemy import select

from app.config import settings

logger = logging.getLogger(__name__)


async def _get_effective_sync_hour(async_session_factory) -> int:
    """Read DB-configured sync hour, fallback to env.

    The admin can change `OUI_SYNC_HOUR` via the settings modal; the persisted
    value takes precedence over the environment variable (M2).
    """
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
        logger.warning("Could not read OUI_SYNC_HOUR from DB, using env fallback", exc_info=True)
    return settings.OUI_SYNC_HOUR


def register_oui_sync_job(scheduler, async_session_factory) -> None:
    """Register the OUI sync job on the APScheduler instance, if enabled.

    Note on multi-worker deployments: ``reschedule_job`` in
    ``admin_modules.py::update_module_settings`` may fail silently when the
    API worker is not the scheduler owner.  The effective sync hour is
    re-evaluated at next startup (cold read from DB).  If SAKN is deployed
    with multiple gunicorn workers, the scheduler should be pinned to a
    single leader worker via an env flag (e.g. ``SCHEDULER_ENABLED=1``).
    """

    if not settings.OUI_SYNC_ENABLED:
        logger.info("OUI sync job disabled (OUI_SYNC_ENABLED=False)")
        return

    # M2 — read effective sync hour from DB at registration time.
    # The scheduler is registered synchronously, but the start() call in
    # main.py follows register_oui_sync_job.  We schedule with the env
    # default first and let a follow-up async re-schedule happen if the
    # DB-configured value differs.
    import asyncio

    hour = settings.OUI_SYNC_HOUR

    async def _apply_effective_hour():
        effective = await _get_effective_sync_hour(async_session_factory)
        if effective != settings.OUI_SYNC_HOUR:
            from apscheduler.triggers.cron import CronTrigger

            scheduler.reschedule_job(
                "oui_sync_daily",
                trigger=CronTrigger(hour=effective, minute=0, timezone="UTC"),
            )
            logger.info(
                "oui_sync_job_rescheduled_at_startup",
                extra={"env_hour": settings.OUI_SYNC_HOUR, "db_hour": effective},
            )

    # Register with env default first (cold start), then re-schedule if DB
    # has a different value.
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

    # Schedule the DB re-sync after scheduler.start() has run.
    # We append a small startup task that runs once scheduler is active.
    async def _startup_reschedule():
        # Small delay to ensure scheduler is started
        await asyncio.sleep(2)
        await _apply_effective_hour()

    # Register a one-shot startup task via asyncio
    original_start = scheduler.start

    def _patched_start(*args, **kwargs):
        original_start(*args, **kwargs)
        # Schedule the async task after start
        scheduler._eventloop.call_soon_threadsafe(
            lambda: asyncio.ensure_future(_startup_reschedule())
        )

    scheduler.start = _patched_start

    logger.info(
        "OUI sync job registered",
        extra={"hour": hour, "note": "effective hour may be updated from DB after startup"},
    )

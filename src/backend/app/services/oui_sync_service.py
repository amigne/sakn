import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import httpx
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.mac_oui import MacOui
from app.models.mac_oui_history import MacOuiHistory
from app.models.preferences import GlobalSetting
from app.services.oui_parser import parse_ieee_file

logger = logging.getLogger(__name__)

# HTTPS confirmed functional 2026-05-31 (ADR-013 §2.1)
OUI_SOURCES: tuple[tuple[str, str], ...] = (
    ("MA-L", "https://standards-oui.ieee.org/oui/oui.txt"),
    ("MA-M", "https://standards-oui.ieee.org/oui28/mam.txt"),
    ("MA-S", "https://standards-oui.ieee.org/oui36/oui36.txt"),
)

FAILURE_COUNTER_KEYS: dict[str, str] = {
    "MA-L": "oui_sync_failures_ma_l",
    "MA-M": "oui_sync_failures_ma_m",
    "MA-S": "oui_sync_failures_ma_s",
}

RUNNING_FLAG_KEY = "oui_sync_running"
RUNNING_STARTED_AT_KEY = "oui_sync_started_at"
RUNNING_TTL_SECONDS = 3600  # 1 h, > max sync time

BATCH_SIZE = 100
OUI_MAX_DOWNLOAD_BYTES = 50 * 1024 * 1024  # 50 MB


@dataclass
class SyncReport:
    added: int = 0
    changed: int = 0
    confirmed: int = 0
    files_failed: list[str] = field(default_factory=list)
    started_at: datetime | None = None
    finished_at: datetime | None = None


def classify_change(old_org: str, new_org: str) -> str:
    """3 values only: name_change | address_change | revoked. No reassigned."""
    new_org_norm = new_org.strip()
    if not new_org_norm or new_org_norm == "----" or "revoked" in new_org_norm.lower():
        return "revoked"
    if old_org != new_org:
        return "name_change"
    return "address_change"


class OuiSyncService:
    def __init__(
        self,
        db_session_factory: Any,
        http_client: httpx.AsyncClient | None = None,
        logger_override: logging.Logger | None = None,
    ):
        self._session_factory = db_session_factory
        self._http = http_client
        self._owns_http = http_client is None
        self._log = logger_override or logger

    async def _get_http(self) -> httpx.AsyncClient:
        if self._http is None:
            self._http = httpx.AsyncClient(
                timeout=httpx.Timeout(settings.OUI_DOWNLOAD_TIMEOUT_SECONDS),
                follow_redirects=False,
            )
        return self._http

    async def _cleanup(self) -> None:
        if self._owns_http and self._http is not None:
            await self._http.aclose()
            self._http = None

    async def _get_failure_count(self, session: AsyncSession, oui_type: str) -> int:
        key = FAILURE_COUNTER_KEYS[oui_type]
        row = await session.execute(select(GlobalSetting).where(GlobalSetting.key == key))
        setting = row.scalar_one_or_none()
        return int(setting.value) if setting else 0

    async def _set_failure_count(self, session: AsyncSession, oui_type: str, count: int) -> None:
        key = FAILURE_COUNTER_KEYS[oui_type]
        row = await session.execute(select(GlobalSetting).where(GlobalSetting.key == key))
        setting = row.scalar_one_or_none()
        if setting:
            setting.value = str(count)
        else:
            session.add(GlobalSetting(key=key, value=str(count)))

    async def _is_running(self, session: AsyncSession) -> bool:
        """Check if a sync is currently running, with TTL-based staleness detection."""
        row = await session.execute(
            select(GlobalSetting).where(
                GlobalSetting.key.in_([RUNNING_FLAG_KEY, RUNNING_STARTED_AT_KEY])
            )
        )
        rows = {s.key: s.value for s in row.scalars().all()}
        if rows.get(RUNNING_FLAG_KEY) != "1":
            return False
        started_at_iso = rows.get(RUNNING_STARTED_AT_KEY)
        if not started_at_iso:
            return True  # fail-safe: flag positive without timestamp = consider running
        try:
            started_at = datetime.fromisoformat(started_at_iso)
        except ValueError:
            return True
        if (datetime.now(UTC) - started_at).total_seconds() > RUNNING_TTL_SECONDS:
            self._log.warning(
                "oui_sync_running flag stale (TTL exceeded), ignoring",
                extra={"started_at": started_at_iso},
            )
            return False
        return True

    async def _set_running(self, session: AsyncSession, running: bool) -> None:
        """Set or clear the running flag and started_at timestamp."""
        flag_value = "1" if running else "0"
        started_at = datetime.now(UTC).isoformat() if running else ""
        for key, val in ((RUNNING_FLAG_KEY, flag_value), (RUNNING_STARTED_AT_KEY, started_at)):
            row = await session.execute(select(GlobalSetting).where(GlobalSetting.key == key))
            setting = row.scalar_one_or_none()
            if setting:
                setting.value = val
            else:
                session.add(GlobalSetting(key=key, value=val))

    async def try_acquire_running_lock(self, session: AsyncSession) -> bool:
        """Atomic compare-and-set: returns True if we acquired the lock."""
        result = await session.execute(
            update(GlobalSetting)
            .where(GlobalSetting.key == RUNNING_FLAG_KEY, GlobalSetting.value == "0")
            .values(value="1")
        )
        if result.rowcount == 1:
            await session.execute(
                update(GlobalSetting)
                .where(GlobalSetting.key == RUNNING_STARTED_AT_KEY)
                .values(value=datetime.now(UTC).isoformat())
            )
            await session.commit()
            return True
        # Check TTL on existing flag
        if not await self._is_running(session):
            # Flag is stale, reclaim it
            await session.execute(
                update(GlobalSetting)
                .where(GlobalSetting.key == RUNNING_FLAG_KEY)
                .values(value="1")
            )
            await session.execute(
                update(GlobalSetting)
                .where(GlobalSetting.key == RUNNING_STARTED_AT_KEY)
                .values(value=datetime.now(UTC).isoformat())
            )
            await session.commit()
            return True
        return False

    async def sync_all(self, skip_lock_check: bool = False) -> SyncReport:
        """Run sync for all 3 IEEE files. Set skip_lock_check=True if the caller
        already acquired the lock via try_acquire_running_lock."""
        report = SyncReport(started_at=datetime.now(UTC))
        await self._get_http()

        if not skip_lock_check:
            async with self._session_factory() as session:
                if not await self.try_acquire_running_lock(session):
                    self._log.warning("oui_sync_already_running")
                    report.finished_at = datetime.now(UTC)
                    return report

        try:
            for oui_type, url in OUI_SOURCES:
                try:
                    added, changed, confirmed, failed = await self.sync_one(oui_type, url)
                    if failed:
                        report.files_failed.append(oui_type)
                    report.added += added
                    report.changed += changed
                    report.confirmed += confirmed
                except Exception:
                    self._log.exception("oui_sync_unexpected_error file=%s", oui_type)
                    report.files_failed.append(oui_type)
                    async with self._session_factory() as session:
                        count = await self._get_failure_count(session, oui_type) + 1
                        await self._set_failure_count(session, oui_type, count)
                        await session.commit()
                        if count >= 3:
                            self._log.error(
                                "ALERT_OUI_SYNC_FAILED_3X",
                                extra={"file": oui_type, "consecutive_failures": count},
                            )
        finally:
            async with self._session_factory() as session:
                await self._set_running(session, False)
                await session.commit()
            await self._cleanup()

        report.finished_at = datetime.now(UTC)
        self._log.info(
            "oui_sync_complete",
            extra={
                "added": report.added,
                "changed": report.changed,
                "confirmed": report.confirmed,
                "files_failed": report.files_failed,
            },
        )
        return report

    async def sync_one(self, oui_type: str, url: str) -> tuple[int, int, int, bool]:
        """Download, parse and upsert one IEEE file. Returns (added, changed, confirmed, failed)."""
        http = await self._get_http()

        # Download with streaming + size cap
        try:
            async with http.stream("GET", url) as response:
                if response.status_code != 200:
                    self._log.error(
                        "oui_download_failed",
                        extra={"file": oui_type, "status_code": response.status_code},
                    )
                    await self._handle_failure(oui_type)
                    return 0, 0, 0, True

                content_length = response.headers.get("content-length")
                if content_length and int(content_length) > OUI_MAX_DOWNLOAD_BYTES:
                    self._log.error(
                        "oui_download_too_large",
                        extra={"file": oui_type, "size": content_length},
                    )
                    await self._handle_failure(oui_type)
                    return 0, 0, 0, True

                chunks: list[bytes] = []
                total = 0
                async for chunk in response.aiter_bytes(chunk_size=64 * 1024):
                    total += len(chunk)
                    if total > OUI_MAX_DOWNLOAD_BYTES:
                        self._log.error(
                            "oui_download_exceeded_cap",
                            extra={"file": oui_type, "bytes_read": total},
                        )
                        await self._handle_failure(oui_type)
                        return 0, 0, 0, True
                    chunks.append(chunk)
                raw_bytes = b"".join(chunks)
                try:
                    content = raw_bytes.decode("utf-8")
                except UnicodeDecodeError:
                    self._log.warning(
                        "oui_file_not_utf8_falling_back_to_cp1252",
                        extra={"file": oui_type},
                    )
                    content = raw_bytes.decode("cp1252", errors="replace")
        except httpx.TimeoutException:
            self._log.error("oui_download_timeout", extra={"file": oui_type})
            await self._handle_failure(oui_type)
            return 0, 0, 0, True
        except Exception:
            self._log.exception("oui_download_error", extra={"file": oui_type})
            await self._handle_failure(oui_type)
            return 0, 0, 0, True

        added = 0
        changed = 0
        confirmed = 0
        batch = 0

        async with self._session_factory() as session:
            for entry in parse_ieee_file(content, oui_type):
                row = await session.execute(
                    select(MacOui).where(
                        MacOui.oui == entry.oui, MacOui.oui_type == entry.oui_type
                    )
                )
                existing = row.scalar_one_or_none()

                today = datetime.now(UTC).date()

                if existing is None:
                    session.add(
                        MacOui(
                            oui=entry.oui,
                            oui_type=entry.oui_type,
                            organization=entry.organization,
                            address=entry.address,
                            first_seen=today,
                            last_seen=today,
                        )
                    )
                    added += 1
                elif (
                    existing.organization == entry.organization
                    and existing.address == entry.address
                ):
                    existing.last_seen = today
                    confirmed += 1
                else:
                    change_type = classify_change(
                        existing.organization,
                        entry.organization,
                    )
                    session.add(
                        MacOuiHistory(
                            oui_id=existing.id,
                            oui=entry.oui,
                            previous_organization=existing.organization,
                            new_organization=entry.organization,
                            previous_address=existing.address,
                            new_address=entry.address,
                            change_type=change_type,
                            detected_at=datetime.now(UTC),
                        )
                    )
                    existing.organization = entry.organization
                    existing.address = entry.address
                    existing.last_seen = today
                    changed += 1

                batch += 1
                if batch % BATCH_SIZE == 0:
                    await session.commit()

            await session.commit()

        # Reset failure counter on success
        async with self._session_factory() as session:
            await self._set_failure_count(session, oui_type, 0)
            await session.commit()

        self._log.info(
            "oui_sync_file_complete",
            extra={
                "file": oui_type,
                "added": added,
                "changed": changed,
                "confirmed": confirmed,
            },
        )
        return added, changed, confirmed, False

    async def _handle_failure(self, oui_type: str) -> None:
        """Increment per-file failure counter; emit CRITICAL log at 3 consecutive failures."""
        async with self._session_factory() as session:
            count = await self._get_failure_count(session, oui_type) + 1
            await self._set_failure_count(session, oui_type, count)
            await session.commit()
            if count >= 3:
                self._log.error(
                    "ALERT_OUI_SYNC_FAILED_3X",
                    extra={"file": oui_type, "consecutive_failures": count},
                )

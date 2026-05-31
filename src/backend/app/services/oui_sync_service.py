import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import httpx
from sqlalchemy import select
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

BATCH_SIZE = 100


@dataclass
class SyncReport:
    added: int = 0
    changed: int = 0
    confirmed: int = 0
    files_failed: list[str] = field(default_factory=list)
    started_at: datetime | None = None
    finished_at: datetime | None = None


def classify_change(old_org: str, new_org: str, old_addr: str, new_addr: str) -> str:
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
                follow_redirects=True,
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
        row = await session.execute(
            select(GlobalSetting).where(GlobalSetting.key == RUNNING_FLAG_KEY)
        )
        setting = row.scalar_one_or_none()
        return bool(setting and setting.value == "1")

    async def _set_running(self, session: AsyncSession, running: bool) -> None:
        row = await session.execute(
            select(GlobalSetting).where(GlobalSetting.key == RUNNING_FLAG_KEY)
        )
        setting = row.scalar_one_or_none()
        if setting:
            setting.value = "1" if running else "0"
        else:
            session.add(GlobalSetting(key=RUNNING_FLAG_KEY, value="1" if running else "0"))

    async def sync_all(self) -> SyncReport:
        report = SyncReport(started_at=datetime.now(UTC))
        # Ensure HTTP client is initialized
        await self._get_http()

        async with self._session_factory() as session:
            # Check if already running
            if await self._is_running(session):
                self._log.warning("oui_sync_already_running")
                report.finished_at = datetime.now(UTC)
                return report

            await self._set_running(session, True)
            await session.commit()

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
                    # Increment failure counter
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

        # Download
        try:
            response = await http.get(url)
            if response.status_code != 200:
                self._log.error(
                    "oui_download_failed",
                    extra={"file": oui_type, "status_code": response.status_code},
                )
                await self._handle_failure(oui_type)
                return 0, 0, 0, True
            content = response.text
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
                # Lookup existing
                row = await session.execute(
                    select(MacOui).where(
                        MacOui.oui == entry.oui, MacOui.oui_type == entry.oui_type
                    )
                )
                existing = row.scalar_one_or_none()

                today = datetime.now(UTC).date()

                if existing is None:
                    # New OUI
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
                    # No change — just update last_seen
                    existing.last_seen = today
                    confirmed += 1
                else:
                    # Change detected — insert history row
                    change_type = classify_change(
                        existing.organization,
                        entry.organization,
                        existing.address,
                        entry.address,
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
                    # Update MacOui with new values
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

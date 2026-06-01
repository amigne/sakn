"""MAC OUI lookup service — single-query longest-prefix matching.

Architecture per ADR-013 §6.2 (longest-prefix performance) and
ADR-014 §2.5-2.6 (oui_display format, ambiguity detection).

All database access for the MAC OUI tool is concentrated here.
The service receives validated entries and returns structured lookup rows.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal

from sqlalchemy import func, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.mac_oui import MacOui
from app.models.mac_oui_history import MacOuiHistory
from app.tools.mac_oui_validator import ValidatedEntry

logger = logging.getLogger(__name__)

# History first-page size (Sprint 3 hard-coded; Sprint 5 adds paginated endpoint).
HISTORY_FIRST_PAGE_SIZE = 10


# ---------------------------------------------------------------------------
# Output data classes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LookupResult:
    """A matched OUI row from the database."""

    oui_type: Literal["MA-L", "MA-M", "MA-S"]
    organization: str
    address: str
    first_seen: date
    last_seen: date


@dataclass(frozen=True)
class HistoryEntry:
    """A single historical change record."""

    change_type: str
    previous_organization: str
    new_organization: str
    previous_address: str | None
    new_address: str | None
    detected_at: datetime


@dataclass(frozen=True)
class LookupRow:
    """The complete result for one input entry."""

    input: str  # raw input as received
    oui_display: str  # formatted per ADR-014 §2.5
    result: LookupResult | None
    ambiguous_extends_ma_m: bool
    ambiguous_extends_ma_s: bool
    history: list[HistoryEntry]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _prefix_candidates(entry: ValidatedEntry) -> list[tuple[str, str]]:
    """Build all (oui_prefix, oui_type) candidates for *entry*.

    The order follows longest-prefix-first:
        MA-S (9) → MA-M (7) → MA-L (6)

    For a 24-bit entry the list has exactly 1 candidate.
    """
    n = entry.normalized
    candidates: list[tuple[str, str]] = []

    if entry.bit_size >= 36:  # 36 or 48 → MA-S candidate
        candidates.append((n[:9], "MA-S"))
    if entry.bit_size >= 28:  # 28, 36, 48 → MA-M candidate
        candidates.append((n[:7], "MA-M"))
    # All lengths → MA-L candidate
    candidates.append((n[:6], "MA-L"))

    return candidates


def format_oui_display(normalized: str, oui_type: str | None, bit_size: int) -> str:
    """Format a normalised hex string for display per ADR-014 §2.5.

    ========== ======== ===================
    Type       Bit size Example output
    ========== ======== ===================
    MA-L       24       ``00:11:22``
    MA-M       28       ``00:11:22:3_``
    MA-S       36       ``00:11:22:33:4_``
    MAC (48)   48       ``00:11:22:33:44:55``
    ========== ======== ===================
    """
    if bit_size == 24:
        return f"{normalized[0:2]}:{normalized[2:4]}:{normalized[4:6]}"
    elif bit_size == 28:
        return (
            f"{normalized[0:2]}:{normalized[2:4]}:{normalized[4:6]}:"
            f"{normalized[6]}_"
        )
    elif bit_size == 36:
        return (
            f"{normalized[0:2]}:{normalized[2:4]}:{normalized[4:6]}:"
            f"{normalized[6:8]}:{normalized[8]}_"
        )
    else:  # 48-bit MAC
        return (
            f"{normalized[0:2]}:{normalized[2:4]}:{normalized[4:6]}:"
            f"{normalized[6:8]}:{normalized[8:10]}:{normalized[10:12]}"
        )


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


async def lookup_batch(
    session: AsyncSession,
    entries: list[ValidatedEntry],
) -> list[LookupRow]:
    """Execute a batch MAC OUI lookup with longest-prefix matching.

    Exactly **one** ``SELECT FROM mac_oui`` query is issued regardless of
    batch size (verified by the N+1 event-listener test).

    A **second** batched query detects ambiguous prefixes (MA-M / MA-S
    sharing the same 6-digit prefix as a matched MA-L).  A **third** batched
    query retrieves the first page of history for all matched OUIs.
    """
    if not entries:
        return []

    # ------------------------------------------------------------------
    # Phase 1: build candidate set, single SELECT
    # ------------------------------------------------------------------
    all_candidates: set[tuple[str, str]] = set()
    entry_candidates: dict[int, list[tuple[str, str]]] = {}

    for entry in entries:
        cands = _prefix_candidates(entry)
        entry_candidates[entry.index] = cands
        all_candidates.update(cands)

    # Single batch query: SELECT ... WHERE (oui, oui_type) IN (...)
    stmt = select(MacOui).where(
        tuple_(MacOui.oui, MacOui.oui_type).in_(all_candidates)
    )
    result = await session.execute(stmt)
    db_rows: list[MacOui] = list(result.scalars().all())

    # Index DB rows by (oui, oui_type) for O(1) lookup
    db_index: dict[tuple[str, str], MacOui] = {
        (row.oui, row.oui_type): row for row in db_rows
    }

    # ------------------------------------------------------------------
    # Phase 2: resolve each entry to its best match
    # ------------------------------------------------------------------
    # Per-entry intermediate state (mutable during assembly).
    matched_oui_id: dict[int, str | None] = {}  # entry.index → MacOui.id
    matched_oui_type: dict[int, str | None] = {}  # entry.index → oui_type
    lookup_results: dict[int, LookupResult | None] = {}  # entry.index → result
    oui_displays: dict[int, str] = {}  # entry.index → formatted string
    # Set of 24-bit prefixes that matched MA-L (for ambiguity detection)
    ma_l_24bit_prefixes: set[str] = set()

    for entry in entries:
        best_row: MacOui | None = None
        best_type: str | None = None

        for oui_prefix, oui_type in entry_candidates[entry.index]:
            db_row = db_index.get((oui_prefix, oui_type))
            if db_row is not None:
                best_row = db_row
                best_type = oui_type
                break  # candidates are already in longest-first order

        matched_oui_type[entry.index] = best_type
        matched_oui_id[entry.index] = best_row.id if best_row else None

        if best_row is not None:
            lookup_results[entry.index] = LookupResult(
                oui_type=best_row.oui_type,
                organization=best_row.organization,
                address=best_row.address,
                first_seen=best_row.first_seen,
                last_seen=best_row.last_seen,
            )
            # Track 24-bit MA-L matches for ambiguity check
            if entry.bit_size == 24 and best_type == "MA-L":
                ma_l_24bit_prefixes.add(entry.normalized[:6])
        else:
            lookup_results[entry.index] = None

        oui_displays[entry.index] = format_oui_display(
            entry.normalized,
            best_type,
            entry.bit_size,
        )

    # ------------------------------------------------------------------
    # Phase 3: ambiguity detection (single batch query)
    # ------------------------------------------------------------------
    ambiguous_ma_m: set[str] = set()  # 6-char prefixes with MA-M rows
    ambiguous_ma_s: set[str] = set()  # 6-char prefixes with MA-S rows

    if ma_l_24bit_prefixes:
        amb_stmt = (
            select(
                MacOui.oui_type,
                func.substr(MacOui.oui, 1, 6).label("prefix_24"),
            )
            .where(
                MacOui.oui_type.in_(["MA-M", "MA-S"]),
                func.substr(MacOui.oui, 1, 6).in_(ma_l_24bit_prefixes),
            )
            .distinct()
        )
        amb_result = await session.execute(amb_stmt)

        for oui_type, prefix_24 in amb_result.all():
            if oui_type == "MA-M":
                ambiguous_ma_m.add(prefix_24)
            elif oui_type == "MA-S":
                ambiguous_ma_s.add(prefix_24)

    # ------------------------------------------------------------------
    # Phase 4: history first page (single batch query for all matched OUIs)
    # ------------------------------------------------------------------
    all_matched_ids = [oid for oid in matched_oui_id.values() if oid is not None]
    history_map: dict[str, list[HistoryEntry]] = {}

    if all_matched_ids:
        hist_stmt = (
            select(MacOuiHistory)
            .where(MacOuiHistory.oui_id.in_(all_matched_ids))
            .order_by(MacOuiHistory.detected_at.desc())
        )
        hist_result = await session.execute(hist_stmt)

        for h in hist_result.scalars().all():
            history_map.setdefault(h.oui_id, []).append(
                HistoryEntry(
                    change_type=h.change_type,
                    previous_organization=h.previous_organization,
                    new_organization=h.new_organization,
                    previous_address=h.previous_address,
                    new_address=h.new_address,
                    detected_at=h.detected_at,
                )
            )

    # ------------------------------------------------------------------
    # Assemble final rows
    # ------------------------------------------------------------------
    rows: list[LookupRow] = []
    for entry in entries:
        idx = entry.index
        oid = matched_oui_id.get(idx)
        history = history_map.get(oid, [])[:HISTORY_FIRST_PAGE_SIZE] if oid else []

        # Ambiguity only applies to 24-bit entries — for ≥28-bit entries we
        # already picked the longest prefix, so there is no ambiguity by
        # definition (ADR-014 §4.4.2). The bit_size gate is essential: in a
        # mixed batch where a 24-bit MA-L hit and a longer entry share the
        # same 24-bit prefix, Phase 3 would otherwise mark the longer entry
        # as ambiguous too.
        is_ambiguous_ma_m = (
            entry.bit_size == 24 and entry.normalized[:6] in ambiguous_ma_m
        )
        is_ambiguous_ma_s = (
            entry.bit_size == 24 and entry.normalized[:6] in ambiguous_ma_s
        )

        rows.append(
            LookupRow(
                input=entry.raw,
                oui_display=oui_displays[idx],
                result=lookup_results[idx],
                ambiguous_extends_ma_m=is_ambiguous_ma_m,
                ambiguous_extends_ma_s=is_ambiguous_ma_s,
                history=history,
            )
        )

    return rows

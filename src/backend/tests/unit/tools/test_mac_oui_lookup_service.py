"""Unit tests for mac_oui_lookup_service — longest-prefix lookup, ambiguity, history.

Requires a database session with seeded MacOui / MacOuiHistory rows.
"""

from __future__ import annotations

import pytest
from sqlalchemy import event

from app.tools.mac_oui_lookup_service import (
    format_oui_display,
    lookup_batch,
)
from app.tools.mac_oui_validator import ValidatedEntry

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _v(index: int, raw: str, bit_size: int) -> ValidatedEntry:
    """Shorthand to build a ValidatedEntry for testing."""
    return ValidatedEntry(
        index=index,
        raw=raw,
        normalized=raw.upper().replace(":", "").replace("-", "").replace(".", ""),
        bit_size=bit_size,  # type: ignore[arg-type]
    )


# ---------------------------------------------------------------------------
# format_oui_display
# ---------------------------------------------------------------------------


class TestOuiDisplay:
    def test_oui_display_ma_l(self):
        """Covers AC-MAC-OUI-060 — MA-L display: 00:11:22."""
        assert format_oui_display("001122", "MA-L", 24) == "00:11:22"

    def test_oui_display_ma_m(self):
        """Covers AC-MAC-OUI-061 — MA-M display: 00:11:22:3_."""
        assert format_oui_display("0011223", "MA-M", 28) == "00:11:22:3_"

    def test_oui_display_ma_s(self):
        """Covers AC-MAC-OUI-062 — MA-S display: 00:11:22:33:4_."""
        assert format_oui_display("001122334", "MA-S", 36) == "00:11:22:33:4_"

    def test_oui_display_mac(self):
        """48-bit MAC display: 00:11:22:33:44:55."""
        assert format_oui_display("001122334455", "MA-L", 48) == "00:11:22:33:44:55"


# ---------------------------------------------------------------------------
# lookup_batch — basic lookups
# ---------------------------------------------------------------------------


class TestLookupBasic:
    pytestmark = pytest.mark.asyncio

    async def test_lookup_ma_l_hit(self, db_session):
        """Covers AC-MAC-OUI-041 — MA-L hit returns organisation."""
        from tests.fixtures.mac_oui_seed import seed_mac_oui_test_data

        await seed_mac_oui_test_data(db_session)

        entries = [_v(1, "001122", 24)]
        rows = await lookup_batch(db_session, entries)

        assert len(rows) == 1
        assert rows[0].result is not None
        assert rows[0].result.oui_type == "MA-L"
        assert rows[0].result.organization == "Cisco Systems, Inc."

    async def test_lookup_ma_m_hit(self, db_session):
        """Covers AC-MAC-OUI-042 — MA-M hit."""
        from tests.fixtures.mac_oui_seed import seed_mac_oui_test_data

        await seed_mac_oui_test_data(db_session)

        entries = [_v(1, "8C1F640", 28)]
        rows = await lookup_batch(db_session, entries)

        assert len(rows) == 1
        assert rows[0].result is not None
        assert rows[0].result.oui_type == "MA-M"
        assert rows[0].result.organization == "Acme Corp"

    async def test_lookup_ma_s_hit(self, db_session):
        """Covers AC-MAC-OUI-043 — MA-S hit."""
        from tests.fixtures.mac_oui_seed import seed_mac_oui_test_data

        await seed_mac_oui_test_data(db_session)

        entries = [_v(1, "8C1F64100", 36)]
        rows = await lookup_batch(db_session, entries)

        assert len(rows) == 1
        assert rows[0].result is not None
        assert rows[0].result.oui_type == "MA-S"
        assert rows[0].result.organization == "Acme Corp (MA-S)"

    async def test_lookup_unknown(self, db_session):
        """Covers AC-MAC-OUI-046 — unknown OUI → result=None."""
        from tests.fixtures.mac_oui_seed import seed_mac_oui_test_data

        await seed_mac_oui_test_data(db_session)

        entries = [_v(1, "FFEEDD", 24)]
        rows = await lookup_batch(db_session, entries)

        assert len(rows) == 1
        assert rows[0].result is None


# ---------------------------------------------------------------------------
# lookup_batch — longest prefix
# ---------------------------------------------------------------------------


class TestLongestPrefix:
    pytestmark = pytest.mark.asyncio

    async def test_longest_prefix_wins_mac_to_ma_m(self, db_session):
        """Covers AC-MAC-OUI-044 — MAC matches MA-L AND MA-M → MA-M wins."""
        from tests.fixtures.mac_oui_seed import seed_mac_oui_test_data

        await seed_mac_oui_test_data(db_session)

        # 8C1F64000000 (12 digits):
        #   - 8C1F64 = IEEE Reg Auth (MA-L)
        #   - 8C1F640 = Acme Corp (MA-M)
        # Longest prefix wins → MA-M (Acme Corp)
        entries = [_v(1, "8C1F64000000", 48)]
        rows = await lookup_batch(db_session, entries)

        assert len(rows) == 1
        assert rows[0].result is not None
        assert rows[0].result.oui_type == "MA-M"
        assert rows[0].result.organization == "Acme Corp"

    async def test_longest_prefix_wins_mac_to_ma_s(self, db_session):
        """Covers AC-MAC-OUI-045 — MAC matches all three → MA-S wins."""
        from tests.fixtures.mac_oui_seed import seed_mac_oui_test_data

        await seed_mac_oui_test_data(db_session)

        # 8C1F64100FFF (12 digits):
        #   - 8C1F64 = IEEE Reg Auth (MA-L)
        #   - 8C1F641 = OtherCorp (MA-M)
        #   - 8C1F64100 = Acme Corp (MA-S)
        # Longest prefix wins → MA-S
        entries = [_v(1, "8C1F64100FFF", 48)]
        rows = await lookup_batch(db_session, entries)

        assert len(rows) == 1
        assert rows[0].result is not None
        assert rows[0].result.oui_type == "MA-S"
        assert rows[0].result.organization == "Acme Corp (MA-S)"

    async def test_ma_m_fallback_to_ma_l(self, db_session):
        """28-bit entry with no MA-M match falls back to MA-L."""
        from tests.fixtures.mac_oui_seed import seed_mac_oui_test_data

        await seed_mac_oui_test_data(db_session)

        # 0011223 → no MA-M match, falls back to 001122 (Cisco MA-L)
        entries = [_v(1, "0011223", 28)]
        rows = await lookup_batch(db_session, entries)

        assert len(rows) == 1
        assert rows[0].result is not None
        assert rows[0].result.oui_type == "MA-L"
        assert rows[0].result.organization == "Cisco Systems, Inc."


# ---------------------------------------------------------------------------
# lookup_batch — ambiguity
# ---------------------------------------------------------------------------


class TestAmbiguity:
    pytestmark = pytest.mark.asyncio

    async def test_ambiguous_partial_oui(self, db_session):
        """Covers AC-MAC-OUI-047 — 24-bit OUI with MA-M extensions → ambiguous."""
        from tests.fixtures.mac_oui_seed import seed_mac_oui_test_data

        await seed_mac_oui_test_data(db_session)

        # 8C1F64 = IEEE Reg Auth (MA-L), but MA-M rows 8C1F640 and 8C1F641 exist
        entries = [_v(1, "8C1F64", 24)]
        rows = await lookup_batch(db_session, entries)

        assert len(rows) == 1
        assert rows[0].result is not None
        assert rows[0].result.oui_type == "MA-L"
        assert rows[0].result.organization == "IEEE Registration Authority"
        assert rows[0].ambiguous_extends_ma_m is True

    async def test_unambiguous_oui(self, db_session):
        """24-bit OUI with no MA-M/MA-S extensions → not ambiguous."""
        from tests.fixtures.mac_oui_seed import seed_mac_oui_test_data

        await seed_mac_oui_test_data(db_session)

        # 001122 = Cisco MA-L, no MA-M/MA-S rows with this prefix
        entries = [_v(1, "001122", 24)]
        rows = await lookup_batch(db_session, entries)

        assert len(rows) == 1
        assert rows[0].ambiguous_extends_ma_m is False
        assert rows[0].ambiguous_extends_ma_s is False

    async def test_non_24bit_not_ambiguous(self, db_session):
        """28-bit, 36-bit, 48-bit entries are never flagged ambiguous."""
        from tests.fixtures.mac_oui_seed import seed_mac_oui_test_data

        await seed_mac_oui_test_data(db_session)

        entries = [
            _v(1, "8C1F640", 28),
            _v(2, "8C1F64100", 36),
            _v(3, "8C1F64100000", 48),
        ]
        rows = await lookup_batch(db_session, entries)

        for row in rows:
            assert row.ambiguous_extends_ma_m is False
            assert row.ambiguous_extends_ma_s is False

    async def test_mixed_batch_only_24bit_gets_ambiguous_flag(self, db_session):
        """Regression — in a mixed batch where a 24-bit MA-L hit and a longer
        entry share the same 24-bit prefix, only the 24-bit entry must be
        flagged ambiguous. Per ADR-014 §4.4.2 the ≥28-bit entry has already
        resolved to its longest prefix and carries no ambiguity.
        """
        from tests.fixtures.mac_oui_seed import seed_mac_oui_test_data

        await seed_mac_oui_test_data(db_session)

        # 8C1F64 = IEEE Reg Auth (MA-L) AND has MA-M extensions 8C1F640/8C1F641
        # AND a MA-S extension 8C1F64100. So the 24-bit entry is ambiguous.
        # The 28-bit entry 8C1F640 resolves directly to MA-M (Acme Corp)
        # and must NOT inherit any ambiguity flag.
        entries = [
            _v(1, "8C1F64", 24),    # → MA-L hit, ambiguous_extends_ma_m/s = True
            _v(2, "8C1F640", 28),   # → MA-M hit, ambiguous_extends_* must be False
        ]
        rows = await lookup_batch(db_session, entries)

        # 24-bit entry: confirmed ambiguous on both MA-M and MA-S
        assert rows[0].result is not None
        assert rows[0].result.oui_type == "MA-L"
        assert rows[0].ambiguous_extends_ma_m is True
        assert rows[0].ambiguous_extends_ma_s is True

        # 28-bit entry: resolved to MA-M, never ambiguous
        assert rows[1].result is not None
        assert rows[1].result.oui_type == "MA-M"
        assert rows[1].ambiguous_extends_ma_m is False
        assert rows[1].ambiguous_extends_ma_s is False


# ---------------------------------------------------------------------------
# lookup_batch — history
# ---------------------------------------------------------------------------


class TestHistory:
    pytestmark = pytest.mark.asyncio

    async def test_history_first_page_returned(self, db_session):
        """History returned with up to HISTORY_FIRST_PAGE_SIZE entries, DESC order."""
        from tests.fixtures.mac_oui_seed import seed_mac_oui_test_data

        await seed_mac_oui_test_data(db_session)

        entries = [_v(1, "AABBCC", 24)]
        rows = await lookup_batch(db_session, entries)

        assert len(rows) == 1
        assert rows[0].result is not None
        history = rows[0].history
        assert len(history) == 3  # 3 seeded entries
        # Order: detected_at DESC (most recent first)
        assert history[0].detected_at > history[1].detected_at
        assert history[1].detected_at > history[2].detected_at

    async def test_no_history_returns_empty_list(self, db_session):
        """Covers AC-MAC-OUI-063 — OUI without history → history=[]."""
        from tests.fixtures.mac_oui_seed import seed_mac_oui_test_data

        await seed_mac_oui_test_data(db_session)

        entries = [_v(1, "001122", 24)]  # Cisco has no history
        rows = await lookup_batch(db_session, entries)

        assert len(rows) == 1
        assert rows[0].history == []

    async def test_unknown_oui_has_empty_history(self, db_session):
        """Unknown OUI → result=None, history=[]."""
        from tests.fixtures.mac_oui_seed import seed_mac_oui_test_data

        await seed_mac_oui_test_data(db_session)

        entries = [_v(1, "FFEEDD", 24)]
        rows = await lookup_batch(db_session, entries)

        assert len(rows) == 1
        assert rows[0].result is None
        assert rows[0].history == []


# ---------------------------------------------------------------------------
# lookup_batch — N+1 prevention
# ---------------------------------------------------------------------------


class TestNPlusOne:
    pytestmark = pytest.mark.asyncio

    async def test_single_select_no_n_plus_1(self, db_session):
        """Covers AC-MAC-OUI-048 — only 1 SELECT FROM mac_oui per call."""
        from tests.fixtures.mac_oui_seed import seed_mac_oui_test_data

        await seed_mac_oui_test_data(db_session)

        select_count = 0
        bind = db_session.get_bind()
        # get_bind() may return AsyncEngine or Engine depending on setup
        sync_engine = getattr(bind, "sync_engine", bind)

        @event.listens_for(sync_engine, "after_cursor_execute")
        def _count_selects(conn, cursor, statement, parameters, context, executemany):
            nonlocal select_count
            stmt_str = str(statement)
            # Count main lookup query; exclude ambiguity query (Phase 3)
            if (
                "FROM mac_oui" in stmt_str
                and "SELECT" in stmt_str.upper()
                and "substr" not in stmt_str.lower()
            ):
                select_count += 1

        entries = [_v(i, f"{i:06X}", 24) for i in range(10)]
        await lookup_batch(db_session, entries)

        assert select_count == 1, f"Expected 1 SELECT FROM mac_oui, got {select_count}"

    async def test_empty_entries_no_query(self, db_session):
        """Empty entries list → no DB query."""
        from tests.fixtures.mac_oui_seed import seed_mac_oui_test_data

        await seed_mac_oui_test_data(db_session)

        select_count = 0
        bind = db_session.get_bind()
        sync_engine = getattr(bind, "sync_engine", bind)

        @event.listens_for(sync_engine, "after_cursor_execute")
        def _count_selects(conn, cursor, statement, parameters, context, executemany):
            nonlocal select_count
            if "FROM mac_oui" in str(statement):
                select_count += 1

        rows = await lookup_batch(db_session, [])
        assert rows == []
        assert select_count == 0


# ---------------------------------------------------------------------------
# lookup_batch — oui_display in results
# ---------------------------------------------------------------------------


class TestOuiDisplayInResults:
    pytestmark = pytest.mark.asyncio

    async def test_mac_display_48bit(self, db_session):
        """48-bit MAC has full colon-pair display."""
        from tests.fixtures.mac_oui_seed import seed_mac_oui_test_data

        await seed_mac_oui_test_data(db_session)

        entries = [_v(1, "001122334455", 48)]
        rows = await lookup_batch(db_session, entries)

        assert rows[0].oui_display == "00:11:22:33:44:55"

    async def test_ma_m_display_28bit(self, db_session):
        """28-bit OUI has underscore wildcard."""
        from tests.fixtures.mac_oui_seed import seed_mac_oui_test_data

        await seed_mac_oui_test_data(db_session)

        entries = [_v(1, "8C1F640", 28)]
        rows = await lookup_batch(db_session, entries)

        assert rows[0].oui_display == "8C:1F:64:0_"

    async def test_ma_s_display_36bit(self, db_session):
        """36-bit OUI has underscore wildcard after 9th digit."""
        from tests.fixtures.mac_oui_seed import seed_mac_oui_test_data

        await seed_mac_oui_test_data(db_session)

        entries = [_v(1, "8C1F64100", 36)]
        rows = await lookup_batch(db_session, entries)

        assert rows[0].oui_display == "8C:1F:64:10:0_"

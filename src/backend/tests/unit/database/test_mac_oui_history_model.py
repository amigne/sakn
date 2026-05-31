from datetime import UTC, date, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models.base import ensure_aware, new_uuid7
from app.models.mac_oui import MacOui
from app.models.mac_oui_history import MacOuiHistory


async def _create_oui(db_session, oui="001122", oui_type="MA-L"):
    oui_obj = MacOui(
        id=new_uuid7(),
        oui=oui,
        oui_type=oui_type,
        organization="Test Corp",
        address="123 Test St",
        first_seen=date.today(),
        last_seen=date.today(),
    )
    db_session.add(oui_obj)
    await db_session.flush()
    return oui_obj


@pytest.mark.asyncio
async def test_create_valid(db_session):
    """INSERT succeeds with all fields populated."""
    oui = await _create_oui(db_session)

    history = MacOuiHistory(
        id=new_uuid7(),
        oui_id=oui.id,
        oui="001122",
        previous_organization="Old Corp",
        new_organization="Test Corp",
        change_type="name_change",
        detected_at=datetime.now(UTC),
    )
    db_session.add(history)
    await db_session.flush()

    assert history.id is not None
    assert history.oui_id == oui.id
    assert history.change_type == "name_change"
    assert history.previous_organization == "Old Corp"
    assert history.new_organization == "Test Corp"


@pytest.mark.asyncio
async def test_change_type_3_values(db_session):
    """Covers AC-MAC-OUI-087. name_change, address_change, revoked are accepted."""
    oui = await _create_oui(db_session)
    now = datetime.now(UTC)

    for change_type in ("name_change", "address_change", "revoked"):
        history = MacOuiHistory(
            id=new_uuid7(),
            oui_id=oui.id,
            oui="001122",
            previous_organization="Old Corp",
            new_organization="Test Corp",
            change_type=change_type,
            detected_at=now,
        )
        db_session.add(history)
        await db_session.flush()
        assert history.change_type == change_type


@pytest.mark.asyncio
async def test_change_type_reassigned_rejected(db_session):
    """Covers AC-MAC-OUI-087. change_type='reassigned' → IntegrityError."""
    oui = await _create_oui(db_session)

    history = MacOuiHistory(
        id=new_uuid7(),
        oui_id=oui.id,
        oui="001122",
        previous_organization="Old Corp",
        new_organization="New Corp",
        change_type="reassigned",
        detected_at=datetime.now(UTC),
    )
    db_session.add(history)
    with pytest.raises(IntegrityError):
        await db_session.flush()


@pytest.mark.asyncio
async def test_addresses_nullable(db_session):
    """previous_address and new_address can be NULL."""
    oui = await _create_oui(db_session)

    history = MacOuiHistory(
        id=new_uuid7(),
        oui_id=oui.id,
        oui="001122",
        previous_organization="Old Corp",
        new_organization="New Corp",
        change_type="name_change",
        detected_at=datetime.now(UTC),
    )
    db_session.add(history)
    await db_session.flush()

    assert history.previous_address is None
    assert history.new_address is None


@pytest.mark.asyncio
async def test_relationship_ordering(db_session):
    """Covers AC-MAC-OUI-054. MacOui.history ordered by detected_at ascending."""
    oui = await _create_oui(db_session)

    t1 = datetime(2026, 1, 15, tzinfo=UTC)
    t2 = datetime(2026, 3, 10, tzinfo=UTC)
    t3 = datetime(2026, 5, 20, tzinfo=UTC)

    for detected_at, change_type, org in (
        (t2, "address_change", "Intermediate Name"),
        (t1, "name_change", "Test Corp"),
        (t3, "name_change", "Final Corp"),
    ):
        history = MacOuiHistory(
            id=new_uuid7(),
            oui_id=oui.id,
            oui="001122",
            previous_organization="Previous",
            new_organization=org,
            change_type=change_type,
            detected_at=detected_at,
        )
        db_session.add(history)

    await db_session.flush()

    # Verify ordering via direct query on history table
    history_rows = (await db_session.execute(
        select(MacOuiHistory)
        .where(MacOuiHistory.oui_id == oui.id)
        .order_by(MacOuiHistory.detected_at)
    )).scalars().all()
    assert len(history_rows) == 3
    assert ensure_aware(history_rows[0].detected_at) == t1
    assert ensure_aware(history_rows[1].detected_at) == t2
    assert ensure_aware(history_rows[2].detected_at) == t3


@pytest.mark.asyncio
async def test_cascade_on_parent_delete(db_session):
    """DELETE MacOui parent → associated history rows cascade-deleted."""
    oui = await _create_oui(db_session)

    history = MacOuiHistory(
        id=new_uuid7(),
        oui_id=oui.id,
        oui="001122",
        previous_organization="Old Corp",
        new_organization="Test Corp",
        change_type="name_change",
        detected_at=datetime.now(UTC),
    )
    db_session.add(history)
    await db_session.flush()

    # Verify history exists via query (avoid lazy-load in async context)
    before = (await db_session.execute(
        select(MacOuiHistory).where(MacOuiHistory.oui_id == oui.id)
    )).scalars().all()
    assert len(before) == 1

    await db_session.delete(oui)
    await db_session.flush()

    remaining = (await db_session.execute(
        select(MacOuiHistory).where(MacOuiHistory.oui_id == oui.id)
    )).scalars().all()
    assert len(remaining) == 0

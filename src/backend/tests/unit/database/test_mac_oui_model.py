from datetime import UTC, date, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models.base import new_uuid7
from app.models.mac_oui import MacOui
from app.models.mac_oui_history import MacOuiHistory


@pytest.mark.asyncio
async def test_create_valid(db_session):
    """INSERT succeeds with id, created_at, updated_at populated."""
    oui = MacOui(
        id=new_uuid7(),
        oui="001122",
        oui_type="MA-L",
        organization="Test Corp",
        address="123 Test St",
        first_seen=date.today(),
        last_seen=date.today(),
    )
    db_session.add(oui)
    await db_session.flush()

    assert oui.id is not None
    assert oui.oui == "001122"
    assert oui.oui_type == "MA-L"
    assert oui.created_at is not None
    assert oui.updated_at is not None
    assert oui.first_seen == date.today()


@pytest.mark.asyncio
async def test_unique_oui_oui_type(db_session):
    """Covers AC-MAC-OUI-088. Same (oui, oui_type) twice → IntegrityError."""
    oui1 = MacOui(
        id=new_uuid7(),
        oui="001122",
        oui_type="MA-L",
        organization="Test Corp",
        address="123 Test St",
        first_seen=date.today(),
        last_seen=date.today(),
    )
    db_session.add(oui1)
    await db_session.flush()

    oui2 = MacOui(
        id=new_uuid7(),
        oui="001122",
        oui_type="MA-L",
        organization="Another Corp",
        address="456 Other St",
        first_seen=date.today(),
        last_seen=date.today(),
    )
    db_session.add(oui2)
    with pytest.raises(IntegrityError):
        await db_session.flush()


@pytest.mark.asyncio
async def test_allows_same_oui_different_type(db_session):
    """Covers AC-MAC-OUI-088. Same oui with different oui_type → both succeed."""
    oui_ma_l = MacOui(
        id=new_uuid7(),
        oui="001122",
        oui_type="MA-L",
        organization="IEEE Registration Authority",
        address="Pool block",
        first_seen=date.today(),
        last_seen=date.today(),
    )
    db_session.add(oui_ma_l)
    await db_session.flush()

    oui_ma_m = MacOui(
        id=new_uuid7(),
        oui="001122",
        oui_type="MA-M",
        organization="Acme Corp",
        address="123 Acme Way",
        first_seen=date.today(),
        last_seen=date.today(),
    )
    db_session.add(oui_ma_m)
    await db_session.flush()

    assert oui_ma_l.oui == oui_ma_m.oui == "001122"
    assert oui_ma_l.oui_type == "MA-L"
    assert oui_ma_m.oui_type == "MA-M"


@pytest.mark.asyncio
async def test_invalid_oui_type(db_session):
    """INSERT with oui_type='MA-X' → IntegrityError (CHECK constraint)."""
    oui = MacOui(
        id=new_uuid7(),
        oui="001122",
        oui_type="MA-X",
        organization="Test Corp",
        address="123 Test St",
        first_seen=date.today(),
        last_seen=date.today(),
    )
    db_session.add(oui)
    with pytest.raises(IntegrityError):
        await db_session.flush()


@pytest.mark.asyncio
async def test_created_updated_auto(db_session):
    """created_at and updated_at are auto-populated on insert."""
    oui = MacOui(
        id=new_uuid7(),
        oui="001122",
        oui_type="MA-L",
        organization="Test Corp",
        address="123 Test St",
        first_seen=date.today(),
        last_seen=date.today(),
    )
    db_session.add(oui)
    await db_session.flush()

    assert oui.created_at is not None
    assert oui.updated_at is not None
    assert abs((oui.created_at - datetime.now(UTC)).total_seconds()) < 5
    assert abs((oui.created_at - oui.updated_at).total_seconds()) < 1


@pytest.mark.asyncio
async def test_updated_at_changes_on_update(db_session):
    """updated_at changes when a field is modified."""
    oui = MacOui(
        id=new_uuid7(),
        oui="001122",
        oui_type="MA-L",
        organization="Test Corp",
        address="123 Test St",
        first_seen=date.today(),
        last_seen=date.today(),
    )
    db_session.add(oui)
    await db_session.flush()

    original_updated_at = oui.updated_at
    oui.organization = "New Corp Name"
    await db_session.flush()

    assert oui.updated_at > original_updated_at


@pytest.mark.asyncio
async def test_cascade_history_on_delete(db_session):
    """DELETE MacOui → associated MacOuiHistory rows cascade-deleted."""
    oui = MacOui(
        id=new_uuid7(),
        oui="001122",
        oui_type="MA-L",
        organization="Test Corp",
        address="123 Test St",
        first_seen=date.today(),
        last_seen=date.today(),
    )
    db_session.add(oui)
    await db_session.flush()

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

    # History should be cascade-deleted
    remaining = (await db_session.execute(
        select(MacOuiHistory).where(MacOuiHistory.oui_id == oui.id)
    )).scalars().all()
    assert len(remaining) == 0

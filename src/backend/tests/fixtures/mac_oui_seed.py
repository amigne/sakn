"""Seed utility for MAC OUI test data.

Provides idempotent insertion helpers for MacOui and MacOuiHistory rows
used by the lookup service and endpoint integration tests.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import new_uuid7
from app.models.mac_oui import MacOui
from app.models.mac_oui_history import MacOuiHistory


async def seed_mac_oui_test_data(db: AsyncSession) -> dict[str, str]:
    """Insert the standard MAC OUI test dataset.

    Returns a dict mapping logical names to MacOui.id values for
    cross-referencing in tests.

    Data inserted:
    - Cisco MA-L (001122)
    - IEEE Reg Auth MA-L (8C1F64)
    - Acme MA-M (8C1F640) — extends IEEE Reg Auth
    - OtherCorp MA-M (8C1F641) — extends IEEE Reg Auth
    - Acme MA-S (8C1F64100) — extends OtherCorp MA-M
    - VLANCorp MA-L (AABBCC) — with 3 history entries
    """
    ids: dict[str, str] = {}

    # MA-L: Cisco
    cisco = MacOui(
        id=new_uuid7(),
        oui="001122",
        oui_type="MA-L",
        organization="Cisco Systems, Inc.",
        address="170 West Tasman Drive, San Jose CA 95134",
        first_seen=date(2024, 1, 15),
        last_seen=date(2026, 5, 31),
    )
    db.add(cisco)
    ids["cisco_ma_l"] = cisco.id

    # MA-L: IEEE Registration Authority (pool block)
    ieee_reg = MacOui(
        id=new_uuid7(),
        oui="8C1F64",
        oui_type="MA-L",
        organization="IEEE Registration Authority",
        address="445 Hoes Lane, Piscataway NJ 08854",
        first_seen=date(2023, 6, 1),
        last_seen=date(2026, 5, 31),
    )
    db.add(ieee_reg)
    ids["ieee_reg_ma_l"] = ieee_reg.id

    # MA-M: Acme Corp under 8C1F64
    acme_mam = MacOui(
        id=new_uuid7(),
        oui="8C1F640",
        oui_type="MA-M",
        organization="Acme Corp",
        address="100 Main St, Springfield",
        first_seen=date(2025, 1, 10),
        last_seen=date(2026, 5, 31),
    )
    db.add(acme_mam)
    ids["acme_ma_m"] = acme_mam.id

    # MA-M: OtherCorp under 8C1F641
    other_mam = MacOui(
        id=new_uuid7(),
        oui="8C1F641",
        oui_type="MA-M",
        organization="OtherCorp",
        address="200 Side St, Shelbyville",
        first_seen=date(2025, 3, 15),
        last_seen=date(2026, 5, 31),
    )
    db.add(other_mam)
    ids["other_ma_m"] = other_mam.id

    # MA-S: Acme under 8C1F6410
    acme_mas = MacOui(
        id=new_uuid7(),
        oui="8C1F64100",
        oui_type="MA-S",
        organization="Acme Corp (MA-S)",
        address="100 Main St, Springfield",
        first_seen=date(2025, 6, 1),
        last_seen=date(2026, 5, 31),
    )
    db.add(acme_mas)
    ids["acme_ma_s"] = acme_mas.id

    # MA-L: VLANCorp with history
    vlancorp = MacOui(
        id=new_uuid7(),
        oui="AABBCC",
        oui_type="MA-L",
        organization="VLANCorp",
        address="300 Tech Park, Austin TX 78701",
        first_seen=date(2024, 6, 1),
        last_seen=date(2026, 5, 20),
    )
    db.add(vlancorp)
    ids["vlancorp_ma_l"] = vlancorp.id

    await db.flush()

    # History entries for VLANCorp
    dt1 = datetime(2025, 1, 15, tzinfo=timezone.utc)
    dt2 = datetime(2025, 6, 10, tzinfo=timezone.utc)
    dt3 = datetime(2026, 3, 5, tzinfo=timezone.utc)

    db.add_all([
        MacOuiHistory(
            id=new_uuid7(),
            oui_id=vlancorp.id,
            oui="AABBCC",
            previous_organization="VLANCorp LLC",
            new_organization="VLANCorp Inc.",
            previous_address="300 Tech Park, Austin TX 78701",
            new_address="300 Tech Park, Austin TX 78701",
            change_type="name_change",
            detected_at=dt1,
        ),
        MacOuiHistory(
            id=new_uuid7(),
            oui_id=vlancorp.id,
            oui="AABBCC",
            previous_organization="VLANCorp Inc.",
            new_organization="VLANCorp Inc.",
            previous_address="300 Tech Park, Austin TX 78701",
            new_address="400 New Address, Austin TX 78702",
            change_type="address_change",
            detected_at=dt2,
        ),
        MacOuiHistory(
            id=new_uuid7(),
            oui_id=vlancorp.id,
            oui="AABBCC",
            previous_organization="VLANCorp Inc.",
            new_organization="VLANCorp",
            previous_address="400 New Address, Austin TX 78702",
            new_address="300 Tech Park, Austin TX 78701",
            change_type="name_change",
            detected_at=dt3,
        ),
    ])

    await db.flush()
    return ids

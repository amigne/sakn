import pathlib

from app.services.oui_parser import ParsedOuiEntry, parse_ieee_file

FIXTURES = pathlib.Path(__file__).parent.parent.parent / "fixtures" / "ieee"


def _read_fixture(name: str) -> str:
    return (FIXTURES / name).read_text()


def test_parse_ma_l_nominal():
    """Parse MA-L sample file — correct count and OUI lengths (6 digits)."""
    content = _read_fixture("oui-sample.txt")
    entries = list(parse_ieee_file(content, "MA-L"))
    assert len(entries) == 17
    for e in entries:
        assert len(e.oui) == 6
        assert e.oui_type == "MA-L"
        assert e.oui == e.oui.upper()
        assert all(c in "0123456789ABCDEF" for c in e.oui)


def test_parse_ma_m_nominal():
    """MA-M: OUI length 7 digits."""
    content = _read_fixture("mam-sample.txt")
    entries = list(parse_ieee_file(content, "MA-M"))
    assert len(entries) == 5
    for e in entries:
        assert len(e.oui) == 7
        assert e.oui_type == "MA-M"


def test_parse_ma_s_nominal():
    """MA-S: OUI length 9 digits."""
    content = _read_fixture("oui36-sample.txt")
    entries = list(parse_ieee_file(content, "MA-S"))
    assert len(entries) == 5
    for e in entries:
        assert len(e.oui) == 9
        assert e.oui_type == "MA-S"


def test_multiline_address_joined():
    """Address spanning multiple lines → reconstructed with ', '."""
    content = _read_fixture("oui-sample.txt")
    entries = list(parse_ieee_file(content, "MA-L"))
    # 00-00-03 has 3 address lines: "M/S 105", "Palo Alto, CA 94303", "US"
    e03 = next(e for e in entries if e.oui == "000003")
    assert "M/S 105" in e03.address
    assert "Palo Alto, CA 94303" in e03.address
    assert "US" in e03.address
    assert ", " in e03.address


def test_malformed_line_skipped():
    """A line without (hex) in the middle of the file → next entry still parsed."""
    content = "\n".join([
        "00-00-01   (hex)\t\tTest Corp",
        "Some garbage line without hex marker",
        "00-00-02   (hex)\t\tAnother Corp",
    ])
    entries = list(parse_ieee_file(content, "MA-L"))
    assert len(entries) == 2
    assert entries[0].oui == "000001"
    assert entries[1].oui == "000002"


def test_bom_tolerated():
    """BOM at start of file → no crash."""
    content = "﻿00-00-01   (hex)\t\tTest Corp"
    entries = list(parse_ieee_file(content, "MA-L"))
    assert len(entries) == 1
    assert entries[0].oui == "000001"


def test_empty_file():
    """Empty file → empty iterator."""
    entries = list(parse_ieee_file("", "MA-L"))
    assert len(entries) == 0


def test_revoked_keyword_preserved():
    """An entry with 'revoked' in org → returned as-is (classification is in the service, not parser).
    Covers AC-MAC-OUI-087 (parser returns raw text, service classifies)."""
    content = _read_fixture("oui-sample.txt")
    entries = list(parse_ieee_file(content, "MA-L"))
    # 00-00-09 has organization "----"
    e09 = next(e for e in entries if e.oui == "000009")
    assert e09.organization == "----"

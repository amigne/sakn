import logging
from dataclasses import dataclass
from typing import Iterator, Literal

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ParsedOuiEntry:
    oui: str  # bare hex uppercase; length 6 (MA-L), 7 (MA-M), 9 (MA-S)
    organization: str
    address: str  # multiline joined with ", "
    oui_type: Literal["MA-L", "MA-M", "MA-S"]


def parse_ieee_file(
    content: str, oui_type: Literal["MA-L", "MA-M", "MA-S"]
) -> Iterator[ParsedOuiEntry]:
    """Parse an IEEE OUI file content. Pure function — no I/O, no DB."""
    # Strip BOM if present
    if content.startswith("﻿"):
        content = content[1:]

    lines = content.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]

        if "(hex)" not in line:
            i += 1
            continue

        # Parse the hex prefix and organization from the (hex) line
        try:
            hex_part, org_part = line.split("(hex)", 1)
        except ValueError:
            logger.warning("oui_parser_malformed_line: %s", line[:80])
            i += 1
            continue

        # Extract OUI: the hex prefix before (hex), convert hyphens to bare hex uppercase
        hex_tokens = hex_part.strip().split()
        if not hex_tokens:
            logger.warning("oui_parser_malformed_line: %s", line[:80])
            i += 1
            continue

        oui_raw = hex_tokens[0].strip().upper()
        oui = oui_raw.replace("-", "")

        # Validate OUI length
        expected_len = {"MA-L": 6, "MA-M": 7, "MA-S": 9}[oui_type]
        if len(oui) != expected_len:
            logger.warning(
                "oui_parser_malformed_line oui=%s expected_len=%d line=%s",
                oui,
                expected_len,
                line[:80],
            )
            i += 1
            continue

        # Organization is everything after (hex), tab-trimmed
        organization = org_part.strip()

        # Collect address lines (tab-indented lines following the (hex) line)
        address_parts: list[str] = []
        i += 1
        while i < len(lines):
            next_line = lines[i]
            # Address lines are indented (tab) and contain printable content, no (hex)
            if next_line.startswith("\t") and next_line.strip() and "(hex)" not in next_line:
                addr_line = next_line.strip()
                if addr_line:
                    address_parts.append(addr_line)
                    i += 1
                    continue
            # Stop collecting
            break

        address = ", ".join(address_parts) if address_parts else ""

        yield ParsedOuiEntry(
            oui=oui,
            organization=organization,
            address=address,
            oui_type=oui_type,
        )

    return

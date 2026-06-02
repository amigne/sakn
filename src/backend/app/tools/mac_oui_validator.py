"""Zero-trust validation and sanitisation for MAC OUI lookup inputs.

Receives a list of raw strings, validates each against strict hex format,
returns validated entries ready for DB lookup and sanitised rejected entries.

Architecture per ADR-014 §2.7: the backend never does regex extraction on
user text. It receives already-normalised bare hex strings and re-validates
in zero-trust mode. Invalid entries produce 200 OK with rejected[] — never 422.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

# Only regex acceptable on the backend side: bounded, anchored, fixed length range.
# No alternation, no backtracking, no ReDoS surface.
_HEX_STRIP_RE = re.compile(r"[:.\-]")
_HEX_ONLY_RE = re.compile(r"^[0-9A-Fa-f]+$")
_SANITIZE_RE = re.compile(r"[^0-9a-fA-F:.\-]")

VALID_LENGTHS = frozenset({6, 7, 9, 12})

# Mapping of hex-digit length → IEEE bit size.
_BIT_SIZE: dict[int, Literal[24, 28, 36, 48]] = {
    6: 24,
    7: 28,
    9: 36,
    12: 48,
}


@dataclass(frozen=True)
class ValidatedEntry:
    """An entry that passed zero-trust validation, ready for DB lookup."""

    index: int  # 1-based position in the received list
    raw: str  # as received (for result mapping)
    normalized: str  # uppercase, stripped of separators, length ∈ {6, 7, 9, 12}
    bit_size: Literal[24, 28, 36, 48]


@dataclass(frozen=True)
class RejectedEntry:
    """An entry that failed validation, with a sanitised sample for echo."""

    index: int  # 1-based position in the received list
    sample: str  # sanitised: max 20 chars, non-safe chars replaced by '?'
    reason: Literal["invalid_format", "invalid_length", "non_hex_characters"]


def sanitize_sample(s: str, max_len: int = 20) -> str:
    """Truncate to *max_len* and replace characters outside [0-9a-fA-F:.-] with '?'.

    This is the single choke-point for all user-controlled content echoed back
    in ``rejected[].sample``.  No HTML/JS metacharacters survive.
    """
    truncated = s[:max_len]
    return _SANITIZE_RE.sub("?", truncated)


def validate_batch(
    ouis: list[str],
) -> tuple[list[ValidatedEntry], list[RejectedEntry]]:
    """Validate and normalise a batch of raw OUI/MAC strings.

    Batch-size enforcement is the caller's responsibility (performed in
    the tool layer before invoking this function).

    Args:
        ouis: Raw input strings (may contain separators ``:``, ``-``, ``.``).

    Returns:
        A tuple of ``(validated, rejected)``.  The caller assembles both into
        the 200 OK response.
    """
    validated: list[ValidatedEntry] = []
    rejected: list[RejectedEntry] = []

    for idx, raw in enumerate(ouis, start=1):
        if not isinstance(raw, str):
            rejected.append(
                RejectedEntry(
                    index=idx,
                    sample=sanitize_sample(str(raw)),
                    reason="invalid_format",
                )
            )
            continue

        # Step 1: strip allowed separators
        stripped = _HEX_STRIP_RE.sub("", raw)

        # Step 2: empty after stripping → invalid_format
        if not stripped:
            rejected.append(
                RejectedEntry(
                    index=idx,
                    sample=sanitize_sample(raw),
                    reason="invalid_format",
                )
            )
            continue

        # Step 3: check for non-hex characters BEFORE length check so that
        #         "001G" returns non_hex_characters, not invalid_length.
        if not _HEX_ONLY_RE.match(stripped):
            rejected.append(
                RejectedEntry(
                    index=idx,
                    sample=sanitize_sample(raw),
                    reason="non_hex_characters",
                )
            )
            continue

        # Step 4: hex-valid → validate length.
        normalized = stripped.upper()
        length = len(normalized)
        if length not in VALID_LENGTHS:
            rejected.append(
                RejectedEntry(
                    index=idx,
                    sample=sanitize_sample(raw),
                    reason="invalid_length",
                )
            )
            continue

        # Step 5: valid → produce entry
        validated.append(
            ValidatedEntry(
                index=idx,
                raw=raw,
                normalized=normalized,
                bit_size=_BIT_SIZE[length],
            )
        )

    return validated, rejected

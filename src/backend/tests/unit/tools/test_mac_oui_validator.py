"""Unit tests for mac_oui_validator — zero-trust validation and sanitisation."""

from __future__ import annotations

from app.tools.mac_oui_validator import (
    sanitize_sample,
    validate_batch,
)

# ---------------------------------------------------------------------------
# sanitize_sample
# ---------------------------------------------------------------------------


class TestSanitizeSample:
    def test_no_op_on_safe_chars(self):
        """Safe chars pass through unchanged."""
        assert sanitize_sample("00:11:22.33-44") == "00:11:22.33-44"

    def test_truncates_to_max_len(self):
        """Covers AC-MAC-OUI-038 — echo length cap at 20 chars."""
        long_input = "A" * 200
        assert len(sanitize_sample(long_input)) == 20
        assert sanitize_sample(long_input) == "A" * 20

    def test_charset_filter_replaces_unsafe(self):
        """Covers AC-MAC-OUI-039 — chars outside [0-9a-fA-F:.-] → '?'."""
        # 'e' and 'c' survive because they are valid hex chars [a-f].
        # 't', 's', 'r', 'i', 'p', '<', '>' are replaced by '?'.
        result = sanitize_sample("test<script>")
        # Verify no HTML metacharacters survive
        for char in ("<", ">"):
            assert char not in result
        # Verify hex chars that ARE in [a-f] survive
        assert "e" in result
        assert "c" in result
        # Verify non-hex chars are replaced
        assert result[0] == "?"  # 't' → '?'
        assert len(result) <= 20

    def test_xss_payload_sanitized(self):
        """Covers AC-MAC-OUI-037 — XSS payload rendered harmless."""
        result = sanitize_sample("<script>alert(1)</script>")
        # No HTML/JS metacharacters survive
        for char in ("<", ">", "(", ")", ";", '"', "'"):
            assert char not in result, f"Character '{char}' survived sanitisation: {result!r}"
        # Should be 20 chars of '?'
        assert len(result) <= 20

    def test_default_max_len_20(self):
        """Default max_len is 20."""
        assert len(sanitize_sample("A" * 30)) == 20

    def test_custom_max_len(self):
        """max_len parameter is honoured."""
        assert len(sanitize_sample("A" * 50, max_len=10)) == 10


# ---------------------------------------------------------------------------
# validate_batch — normalisation
# ---------------------------------------------------------------------------


class TestValidateNormalisation:
    def test_normalize_with_colon(self):
        """Covers AC-MAC-OUI-021 — strip colon separators."""
        validated, rejected = validate_batch(["00:11:22"])
        assert len(validated) == 1
        assert len(rejected) == 0
        assert validated[0].normalized == "001122"

    def test_normalize_with_hyphen(self):
        """Hyphen separators stripped."""
        validated, _ = validate_batch(["00-11-22"])
        assert validated[0].normalized == "001122"

    def test_normalize_with_dot(self):
        """Dot separators stripped."""
        validated, _ = validate_batch(["0011.22"])
        assert validated[0].normalized == "001122"

    def test_normalize_bare_hex(self):
        """Bare hex passes through unchanged."""
        validated, _ = validate_batch(["001122"])
        assert validated[0].normalized == "001122"

    def test_normalize_uppercase(self):
        """Covers AC-MAC-OUI-022 — lowercase → uppercase."""
        validated, _ = validate_batch(["abcdef"])
        assert validated[0].normalized == "ABCDEF"

    def test_normalize_mixed_separators(self):
        """Mixed separators in same input."""
        validated, _ = validate_batch(["00:11-22.33:44:55"])
        assert validated[0].normalized == "001122334455"


# ---------------------------------------------------------------------------
# validate_batch — length acceptance
# ---------------------------------------------------------------------------


class TestValidateLengthAcceptance:
    def test_length_6_valid(self):
        """24-bit OUI (6 hex digits) accepted."""
        validated, _ = validate_batch(["001122"])
        assert len(validated) == 1
        assert validated[0].bit_size == 24

    def test_length_7_valid(self):
        """28-bit OUI (7 hex digits) accepted."""
        validated, _ = validate_batch(["0011223"])
        assert len(validated) == 1
        assert validated[0].bit_size == 28

    def test_length_9_valid(self):
        """36-bit OUI (9 hex digits) accepted."""
        validated, _ = validate_batch(["001122334"])
        assert len(validated) == 1
        assert validated[0].bit_size == 36

    def test_length_12_valid(self):
        """48-bit MAC (12 hex digits) accepted."""
        validated, _ = validate_batch(["001122334455"])
        assert len(validated) == 1
        assert validated[0].bit_size == 48


# ---------------------------------------------------------------------------
# validate_batch — rejection
# ---------------------------------------------------------------------------


class TestValidateRejection:
    def test_length_8_rejected(self):
        """Covers AC-MAC-OUI-033 — 8 digits → invalid_length."""
        _, rejected = validate_batch(["deadbeef"])
        assert len(rejected) == 1
        assert rejected[0].reason == "invalid_length"
        # sanitize_sample preserves case — lowercase input stays lowercase
        assert rejected[0].sample == "deadbeef"

    def test_length_10_rejected(self):
        """10 digits rejected."""
        _, rejected = validate_batch(["0011223344"])
        assert len(rejected) == 1
        assert rejected[0].reason == "invalid_length"

    def test_length_11_rejected(self):
        """11 digits rejected."""
        _, rejected = validate_batch(["00112233445"])
        assert len(rejected) == 1
        assert rejected[0].reason == "invalid_length"

    def test_non_hex_rejected(self):
        """Covers AC-MAC-OUI-034 — non-hex char → non_hex_characters."""
        _, rejected = validate_batch(["001G22"])
        assert len(rejected) == 1
        assert rejected[0].reason == "non_hex_characters"
        # 'G' is outside [0-9a-fA-F] → replaced by '?' in sanitised sample
        assert rejected[0].sample == "001?22"

    def test_empty_string_rejected(self):
        """Empty string → invalid_format."""
        _, rejected = validate_batch([""])
        assert len(rejected) == 1
        assert rejected[0].reason == "invalid_format"

    def test_too_short_rejected(self):
        """Covers #344 — 5 hex-valid chars → invalid_length (not invalid_format)."""
        _, rejected = validate_batch(["00112"])
        assert len(rejected) == 1
        assert rejected[0].reason == "invalid_length"

    def test_hex_valid_too_long_rejected(self):
        """Covers #344 — 16 hex-valid chars → invalid_length (not invalid_format)."""
        _, rejected = validate_batch(["0011223344556677"])
        assert len(rejected) == 1
        assert rejected[0].reason == "invalid_length"

    def test_too_long_rejected(self):
        """Covers #386 — strings > MAX_INPUT_LENGTH (64) are rejected."""
        too_long = "0" * 65
        _, rejected = validate_batch([too_long])
        assert len(rejected) == 1
        assert rejected[0].reason == "too_long"
        assert len(rejected[0].sample) <= 20

    def test_length_64_accepted(self):
        """Covers #386 — strings at exactly MAX_INPUT_LENGTH are accepted."""
        # A 64-char hex-valid string won't pass length validation (only
        # 6/7/9/12 are valid), but it should NOT be rejected as too_long.
        # It should be rejected as invalid_length.
        at_cap = "0" * 64
        _, rejected = validate_batch([at_cap])
        assert len(rejected) == 1
        assert rejected[0].reason == "invalid_length", (
            f"Expected invalid_length, got {rejected[0].reason}"
        )

    def test_non_string_rejected(self):
        """Non-string item → invalid_format."""
        _, rejected = validate_batch([12345])  # type: ignore[list-item]
        assert len(rejected) == 1
        assert rejected[0].reason == "invalid_format"

    def test_xss_payload_rejected(self):
        """Covers AC-MAC-OUI-037 — XSS payload rejected with sanitised sample."""
        _, rejected = validate_batch(["<script>alert(1)</script>"])
        assert len(rejected) == 1
        sample = rejected[0].sample
        for char in ("<", ">", "(", ")", ";", '"', "'"):
            assert char not in sample, f"Character '{char}' survived in sample: {sample!r}"

    def test_echo_length_capped_at_20(self):
        """Covers AC-MAC-OUI-038 — long input → sample capped at 20 chars."""
        long_input = "A" * 200
        _, rejected = validate_batch([long_input])
        assert len(rejected[0].sample) <= 20


# ---------------------------------------------------------------------------
# validate_batch — edge cases
# ---------------------------------------------------------------------------


class TestValidateEdgeCases:
    def test_empty_list_returns_empty(self):
        """Empty list → empty validated and rejected."""
        validated, rejected = validate_batch([])
        assert len(validated) == 0
        assert len(rejected) == 0

    def test_index_is_1_based(self):
        """RejectedEntry.index is 1-based."""
        # Use hex-valid first entry so only the second is rejected
        _, rejected = validate_batch(["001122", "bad!!"])
        assert len(rejected) == 1
        assert rejected[0].index == 2

    def test_all_valid_large_batch(self):
        """Large batch of valid entries all pass."""
        ouis = [f"{i:06X}" for i in range(100)]
        validated, rejected = validate_batch(ouis)
        assert len(validated) == 100
        assert len(rejected) == 0

    def test_mixed_valid_and_invalid(self):
        """Mix of valid and invalid entries."""
        ouis = ["001122", "deadbeef", "0011223", "001G22"]
        validated, rejected = validate_batch(ouis)
        assert len(validated) == 2  # 001122, 0011223
        assert len(rejected) == 2  # deadbeef (len 8), 001G22 (non-hex)

    def test_raw_value_preserved(self):
        """ValidatedEntry.raw preserves the original input."""
        validated, _ = validate_batch(["00:11:22"])
        assert validated[0].raw == "00:11:22"
        assert validated[0].normalized == "001122"

    def test_charset_filter_on_rejected(self):
        """Covers AC-MAC-OUI-039 — rejected entries have sanitised samples."""
        _, rejected = validate_batch(["hello\nworld"])
        assert len(rejected) == 1
        # '\n' is not in the safe charset → replaced by '?'
        assert "\n" not in rejected[0].sample
        assert "?" in rejected[0].sample

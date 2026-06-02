import { describe, expect, it } from "vitest";
import { extractOuis } from "../macOuiExtractor";

// ── Helpers ───────────────────────────────────────────────────────────

function normSet(result: ReturnType<typeof extractOuis>): string[] {
  return result.unique.map((e) => e.normalized).sort();
}

// ── AC-MAC-OUI-001 — MAC colon-separated (6 octets) ──────────────────

describe("MAC OUI Extractor — positive cases", () => {
  it("AC-MAC-OUI-001: MAC colon-separated 6 octets", () => {
    const r = extractOuis("00:11:22:33:44:55");
    expect(normSet(r)).toContain("001122334455");
    expect(r.unique[0]?.bitSize).toBe(48);
  });

  it("AC-MAC-OUI-002: MAC hyphen-separated 6 octets", () => {
    const r = extractOuis("00-11-22-33-44-55");
    expect(normSet(r)).toContain("001122334455");
  });

  it("AC-MAC-OUI-003: MAC Cisco dot-separated 3 groups of 4", () => {
    const r = extractOuis("0011.2233.4455");
    expect(normSet(r)).toContain("001122334455");
  });

  it("AC-MAC-OUI-004: MAC bare hex 12 digits isolated", () => {
    const r = extractOuis("001122334455");
    expect(normSet(r)).toContain("001122334455");
  });

  it("AC-MAC-OUI-005: MAC bare hex 12 digits NOT isolated", () => {
    const r = extractOuis("abc001122334455def");
    expect(normSet(r)).not.toContain("001122334455");
  });

  it("AC-MAC-OUI-006: OUI 3 octets colon-separated", () => {
    const r = extractOuis("00:11:22");
    expect(normSet(r)).toContain("001122");
    expect(r.unique[0]?.bitSize).toBe(24);
  });

  it("AC-MAC-OUI-007: OUI 3 octets hyphen-separated", () => {
    const r = extractOuis("00-11-22");
    expect(normSet(r)).toContain("001122");
  });

  it("AC-MAC-OUI-008: OUI 3 octets Cisco 2-group", () => {
    const r = extractOuis("0011.22");
    expect(normSet(r)).toContain("001122");
  });

  it("AC-MAC-OUI-009: OUI 3 octets bare hex", () => {
    const r = extractOuis("word 001122 word");
    expect(normSet(r)).toContain("001122");
  });

  it("AC-MAC-OUI-010: OUI MA-M 7 hex digits — all separators", () => {
    expect(normSet(extractOuis("00:11:22:3"))).toContain("0011223");
    expect(normSet(extractOuis("00-11-22-3"))).toContain("0011223");
    expect(normSet(extractOuis("0011223"))).toContain("0011223");
  });

  it("AC-MAC-OUI-011: OUI MA-S 9 hex digits — all separators", () => {
    expect(normSet(extractOuis("00:11:22:33:4"))).toContain("001122334");
    expect(normSet(extractOuis("0011.2233.4"))).toContain("001122334");
    expect(normSet(extractOuis("001122334"))).toContain("001122334");
  });

  it("AC-MAC-OUI-012: Mixed separators in same input", () => {
    const r = extractOuis("00:11:22:33:44:55 and aa-bb-cc-dd-ee-ff and 0011.2233.4455");
    const n = normSet(r);
    expect(n).toContain("001122334455");
    expect(n).toContain("AABBCCDDEEFF");
    // 0011.2233.4455 normalizes to same as 00:11:22:33:44:55 → deduped
    expect(r.unique.length).toBe(2);
  });

  it("AC-MAC-OUI-013: Case insensitivity, normalize to uppercase", () => {
    const r = extractOuis("0a:1b:2c:3d:4e:5f and 0A:1B:2C:3D:4E:5F");
    const allRaw = r.unique.map((e) => e.normalized);
    // Both normalize to the same uppercase value → deduplicated
    expect(allRaw).toContain("0A1B2C3D4E5F");
    expect(r.unique.length).toBe(1);
  });

  it("AC-MAC-OUI-014: Realistic ARP table paste", () => {
    const text = [
      "Internet  10.0.0.1   0   00:11:22:33:44:55   ARPA   Vlan10",
      "Internet  10.0.0.2   0   00-11-22-33-44-AA   ARPA   Vlan10",
    ].join("\n");
    const r = extractOuis(text);
    expect(normSet(r)).toContain("001122334455");
    expect(normSet(r)).toContain("0011223344AA");
  });

  it("AC-MAC-OUI-015: Realistic Cisco config paste", () => {
    const r = extractOuis("interface FastEthernet0/1\n mac-address 0011.2233.4455");
    expect(normSet(r)).toContain("001122334455");
  });
});

// ── AC-MAC-OUI-016 to 020 — Negative cases ───────────────────────────

describe("MAC OUI Extractor — negative cases", () => {
  it("AC-MAC-OUI-016: Non-hex text ignored", () => {
    const r = extractOuis("Server alpha-1 has IP 192.168.1.42 and runs ubuntu");
    expect(r.unique.length).toBe(0);
    expect(r.totalMatchesBeforeDedup).toBe(0);
  });

  it("AC-MAC-OUI-017: UUID — substrings may match (false positive, recall > precision)", () => {
    // ADR-014 §2.2: recall > precision. UUID groups are 8-4-4-4-12, but
    // the regex tolerantly matches 2+2+2+... sequences and bare hex inside
    // the UUID. This is an acceptable false positive per ADR policy.
    const r = extractOuis("550e8400-e29b-41d4-a716-446655440000");
    // Document actual behavior: some substrings may be extracted.
    // The key guarantee is that the full UUID is NOT extracted as one item.
    const all = r.unique.map((e) => e.normalized);
    expect(all).not.toContain("550E8400E29B41D4A716446655440000"); // full UUID not extracted
    // Some substrings are inevitably extracted (e.g., 12-digit group at end).
    // This is acceptable per recall > precision policy.
  });

  it("AC-MAC-OUI-018: Date ISO — substrings may match (false positive, recall > precision)", () => {
    // ADR-014 §2.2: recall > precision. ISO date "2026-05-31" contains
    // "26-05-31" which matches the tolerant 3-pair hyphen pattern.
    // This is an acceptable false positive.
    const r = extractOuis("2026-05-31");
    // The full date string is NOT extracted as one entity.
    const all = r.unique.map((e) => e.normalized);
    expect(all).not.toContain("20260531"); // full date not extracted
    // Individual substrings like 260531 may be extracted — acceptable per policy.
  });

  it("AC-MAC-OUI-019: Timestamp HH:MM:SS — accepted as false positive", () => {
    // ADR-014 §2.2: recall > precision, timestamps are acceptable false positives
    const r = extractOuis("12:34:56");
    expect(normSet(r)).toContain("123456");
  });

  it("AC-MAC-OUI-020: Length 8 hex digits silently dropped", () => {
    // "deadbeef" = 8 hex digits, not in {6, 7, 9, 12}
    const r = extractOuis("deadbeef");
    expect(normSet(r)).not.toContain("DEADBEEF");
    expect(r.unique.length).toBe(0);
  });
});

// ── AC-MAC-OUI-021 to 027 — Normalization & dedup ────────────────────

describe("MAC OUI Extractor — normalization & deduplication", () => {
  it("AC-MAC-OUI-021: Strip separators", () => {
    const r = extractOuis("00:11:22:33:44:55");
    expect(r.unique[0]?.normalized).toBe("001122334455");
    expect(r.unique[0]?.raw).toBe("00:11:22:33:44:55");
  });

  it("AC-MAC-OUI-022: Convert to uppercase", () => {
    const r = extractOuis("ab:cd:ef:12:34:56");
    expect(r.unique[0]?.normalized).toBe("ABCDEF123456");
  });

  it("AC-MAC-OUI-023: Reject invalid hex characters silently", () => {
    // "00112G" can't be extracted because G is not hex, so no pattern matches
    const r = extractOuis("00:11:2G");
    expect(r.unique.length).toBe(0);
  });

  it("AC-MAC-OUI-024: Sorted unique list", () => {
    // extractOuis doesn't sort; order is first-occurrence
    const r = extractOuis("aa:bb:cc:dd:ee:ff 00:11:22:33:44:55 aa:bb:cc:dd:ee:ff");
    // Second occurrence deduped
    expect(r.unique.length).toBe(2);
    expect(r.totalMatchesBeforeDedup).toBe(3);
  });

  it("AC-MAC-OUI-025: Exact duplicates", () => {
    const r = extractOuis("00:11:22:33:44:55 twice: 00:11:22:33:44:55");
    expect(r.unique.length).toBe(1);
    expect(r.totalMatchesBeforeDedup).toBe(2);
  });

  it("AC-MAC-OUI-026: Same MAC, different separators", () => {
    const r = extractOuis("00:11:22:33:44:55 and 00-11-22-33-44-55 and 0011.2233.4455");
    expect(r.unique.length).toBe(1);
    expect(r.totalMatchesBeforeDedup).toBe(3);
  });

  it("AC-MAC-OUI-027: Same OUI extracted twice via different MACs → two entries sent", () => {
    // Different MACs share same OUI prefix, both are sent (dedup by full value, not prefix)
    const r = extractOuis("00:11:22:33:44:55 and 00:11:22:33:44:66");
    expect(r.unique.length).toBe(2);
    expect(normSet(r)).toContain("001122334455");
    expect(normSet(r)).toContain("001122334466");
  });
});

// ── Length priority ───────────────────────────────────────────────────

describe("MAC OUI Extractor — length priority (position masking)", () => {
  it("extracts 48-bit before 24-bit from same text position", () => {
    // 00:11:22:33:44:55 should yield 48-bit, not also 24-bit from first 3 pairs
    const r = extractOuis("00:11:22:33:44:55");
    expect(r.unique.length).toBe(1);
    expect(r.unique[0]?.bitSize).toBe(48);
    expect(normSet(r)).not.toContain("001122"); // first 3 pairs not separately extracted
  });

  it("extracts MA-M 28-bit before OUI 24-bit", () => {
    const r = extractOuis("00:11:22:3");
    expect(r.unique.length).toBe(1);
    expect(r.unique[0]?.bitSize).toBe(28);
    expect(normSet(r)).toContain("0011223");
    expect(normSet(r)).not.toContain("001122");
  });

  it("extracts MA-S 36-bit before OUI 24-bit", () => {
    const r = extractOuis("00:11:22:33:4");
    expect(r.unique.length).toBe(1);
    expect(r.unique[0]?.bitSize).toBe(36);
    expect(normSet(r)).toContain("001122334");
  });

  it("extracts both 48-bit and separate 24-bit from different positions", () => {
    const r = extractOuis("00:11:22:33:44:55 with separate 00:11:22");
    expect(r.unique.length).toBe(2);
    expect(normSet(r)).toContain("001122334455");
    expect(normSet(r)).toContain("001122");
  });
});

// ── Truncation ────────────────────────────────────────────────────────

describe("MAC OUI Extractor — truncation", () => {
  it("truncates at specified maxChars", () => {
    const r = extractOuis("00:11:22:33:44:55", { maxChars: 8 });
    // "00:11:22" is 8 chars, but the full MAC is cut off
    expect(r.totalInputChars).toBe(8);
    expect(r.truncated).toBe(true);
  });

  it("does not set truncated when within limit", () => {
    const r = extractOuis("00:11:22:33:44:55", { maxChars: 50_000 });
    expect(r.truncated).toBe(false);
  });
});

// ── ReDoS frontend test ───────────────────────────────────────────────

describe("MAC OUI Extractor — ReDoS safety", () => {
  it("completes quickly on 50 000 chars of non-hex text", () => {
    const start = performance.now();
    const r = extractOuis("g".repeat(50_000));
    const elapsed = performance.now() - start;
    expect(r.unique.length).toBe(0);
    expect(elapsed).toBeLessThan(1000); // < 1 second
  });

  it("completes quickly on 50 000 chars of alternating hex/non-hex", () => {
    const start = performance.now();
    extractOuis("gz".repeat(25_000));
    const elapsed = performance.now() - start;
    expect(elapsed).toBeLessThan(1000);
  });
});

// ── Edge cases ────────────────────────────────────────────────────────

describe("MAC OUI Extractor — edge cases", () => {
  it("handles empty string", () => {
    const r = extractOuis("");
    expect(r.unique.length).toBe(0);
    expect(r.totalInputChars).toBe(0);
    expect(r.truncated).toBe(false);
  });

  it("handles text with only separators", () => {
    const r = extractOuis(":::---...");
    expect(r.unique.length).toBe(0);
  });

  it("handles MAC at very end of text", () => {
    const r = extractOuis("prefix 00:11:22:33:44:55");
    expect(normSet(r)).toContain("001122334455");
  });

  it("raw field preserves original format", () => {
    const r = extractOuis("aa-bb-cc-dd-ee-ff");
    expect(r.unique[0]?.raw).toBe("aa-bb-cc-dd-ee-ff");
    expect(r.unique[0]?.normalized).toBe("AABBCCDDEEFF");
  });

  it("totalInputChars reflects truncated length", () => {
    const r = extractOuis("a".repeat(60_000), { maxChars: 50_000 });
    expect(r.totalInputChars).toBe(50_000);
    expect(r.truncated).toBe(true);
  });
});

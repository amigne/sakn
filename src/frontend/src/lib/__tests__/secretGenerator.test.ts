/**
 * Tests for `lib/secretGenerator.ts` — Sprint 2 core crypto library.
 *
 * Covers:
 *   - Password: charset selection, rejection sampling, bounds, errors
 *   - Token:    base64url encoding, no padding, bounds
 *   - Hex:      lowercase hex, even output, bounds
 *   - Entropy:  bit calculation per mode
 *   - Strength: threshold classification
 *   - CSPRNG:   guarantee no Math.random usage
 *   - Edge cases from functional-spec.md §3.7.4
 */

import { describe, expect, it, vi } from "vitest";
import {
  classifyStrength,
  entropyBits,
  generateHex,
  generatePassword,
  generateToken,
  SecretGeneratorError,
} from "@/lib/secretGenerator";

// ═══════════════════════════════════════════════════════════════════════
// Helpers
// ═══════════════════════════════════════════════════════════════════════

const ITERATIONS = 100;

/** All printable ASCII, for quick sanity checks. */
const PRINTABLE = /^[\x20-\x7e]+$/;

/** Base64url alphabet: A-Z a-z 0-9 - _ */
const BASE64URL_RE = /^[A-Za-z0-9_-]+$/;

/** Lowercase hex: 0-9 a-f */
const HEX_RE = /^[0-9a-f]+$/;

/** Check that every char in `secret` appears in `charset`. */
function allCharsIn(secret: string, charset: string): boolean {
  const set = new Set(charset);
  return [...secret].every((ch) => set.has(ch));
}

// ═══════════════════════════════════════════════════════════════════════
// Password
// ═══════════════════════════════════════════════════════════════════════

describe("generatePassword", () => {
  // ── Defaults ──────────────────────────────────────────────────────

  it("AC-SEC-001: default options produce a 20-char password", () => {
    const result = generatePassword();
    expect(result.secret).toHaveLength(20);
    expect(result.actualLength).toBe(20);
    expect(result.bits).toBeGreaterThan(0);
    expect(result.strength).toBeDefined();
  });

  it("AC-SEC-002: default charset includes uppercase, lowercase, digits, symbols", () => {
    // Generate many passwords and verify all four sets appear across them
    let hasUpper = false;
    let hasLower = false;
    let hasDigit = false;
    let hasSymbol = false;

    for (let i = 0; i < ITERATIONS; i++) {
      const { secret } = generatePassword();
      if (/[A-Z]/.test(secret)) hasUpper = true;
      if (/[a-z]/.test(secret)) hasLower = true;
      if (/[0-9]/.test(secret)) hasDigit = true;
      if (/[!@#$%^&*()\-_=+[\]{};:,.<>?]/.test(secret)) hasSymbol = true;
    }

    expect(hasUpper).toBe(true);
    expect(hasLower).toBe(true);
    expect(hasDigit).toBe(true);
    expect(hasSymbol).toBe(true);
  });

  // ── Length bounds ─────────────────────────────────────────────────

  it("AC-SEC-003: length clamps to minimum 8", () => {
    const result = generatePassword({ length: 1 });
    expect(result.secret).toHaveLength(8);
    expect(result.actualLength).toBe(8);
  });

  it("AC-SEC-004: length clamps to maximum 128", () => {
    const result = generatePassword({ length: 999 });
    expect(result.secret).toHaveLength(128);
    expect(result.actualLength).toBe(128);
  });

  it("AC-SEC-005: length 8 is accepted", () => {
    const result = generatePassword({ length: 8 });
    expect(result.secret).toHaveLength(8);
  });

  it("AC-SEC-006: length 128 is accepted", () => {
    const result = generatePassword({ length: 128 });
    expect(result.secret).toHaveLength(128);
  });

  // ── Charset isolation ─────────────────────────────────────────────

  it("AC-SEC-007: uppercase-only produces only A-Z", () => {
    for (let i = 0; i < ITERATIONS; i++) {
      const { secret } = generatePassword({
        length: 64,
        uppercase: true,
        lowercase: false,
        digits: false,
        symbols: false,
      });
      expect(secret).toMatch(/^[A-Z]+$/);
    }
  });

  it("AC-SEC-008: lowercase-only produces only a-z", () => {
    for (let i = 0; i < ITERATIONS; i++) {
      const { secret } = generatePassword({
        length: 64,
        uppercase: false,
        lowercase: true,
        digits: false,
        symbols: false,
      });
      expect(secret).toMatch(/^[a-z]+$/);
    }
  });

  it("AC-SEC-009: digits-only produces only 0-9", () => {
    for (let i = 0; i < ITERATIONS; i++) {
      const { secret } = generatePassword({
        length: 64,
        uppercase: false,
        lowercase: false,
        digits: true,
        symbols: false,
      });
      expect(secret).toMatch(/^[0-9]+$/);
    }
  });

  it("AC-SEC-010: symbols-only produces only allowed symbols", () => {
    const symbolSet = "!@#$%^&*()-_=+[]{};:,.<>?";
    for (let i = 0; i < ITERATIONS; i++) {
      const { secret } = generatePassword({
        length: 64,
        uppercase: false,
        lowercase: false,
        digits: false,
        symbols: true,
      });
      expect(allCharsIn(secret, symbolSet)).toBe(true);
    }
  });

  // ── Error: no charset ─────────────────────────────────────────────

  it("AC-SEC-011: throws no_charset_selected when all charsets are false", () => {
    expect(() =>
      generatePassword({
        uppercase: false,
        lowercase: false,
        digits: false,
        symbols: false,
      }),
    ).toThrow(SecretGeneratorError);

    try {
      generatePassword({
        uppercase: false,
        lowercase: false,
        digits: false,
        symbols: false,
      });
    } catch (err) {
      expect(err).toBeInstanceOf(SecretGeneratorError);
      expect((err as SecretGeneratorError).code).toBe("no_charset_selected");
    }
  });

  // ── CSPRNG ────────────────────────────────────────────────────────

  it("AC-SEC-012: uses crypto.getRandomValues, never Math.random", () => {
    const spy = vi.spyOn(Math, "random").mockImplementation(() => {
      throw new Error("Math.random() should never be called");
    });

    try {
      // All three modes should work without Math.random
      const pw = generatePassword();
      expect(pw.secret).toBeTruthy();

      const tk = generateToken();
      expect(tk.secret).toBeTruthy();

      const hx = generateHex();
      expect(hx.secret).toBeTruthy();
    } finally {
      spy.mockRestore();
    }
  });

  it("AC-SEC-013: each call produces different output (randomness)", () => {
    const results = new Set<string>();
    for (let i = 0; i < 50; i++) {
      results.add(generatePassword().secret);
    }
    // All 50 should be unique (probability of collision with 86^20 space
    // is effectively zero).
    expect(results.size).toBe(50);
  });

  // ── Printability ──────────────────────────────────────────────────

  it("AC-SEC-014: password contains only printable ASCII characters", () => {
    for (let i = 0; i < ITERATIONS; i++) {
      const { secret } = generatePassword();
      expect(secret).toMatch(PRINTABLE);
    }
  });

  // ── Edge case: 8 chars digits only → weak (spec §3.7.4) ─────────

  it("AC-SEC-015: 8-digit password is ~26 bits → weak", () => {
    const result = generatePassword({
      length: 8,
      uppercase: false,
      lowercase: false,
      digits: true,
      symbols: false,
    });
    expect(result.actualLength).toBe(8);
    // entropy = 8 * log2(10) ≈ 26.58 bits
    expect(result.bits).toBeCloseTo(8 * Math.log2(10), 0);
    expect(result.strength).toBe("weak");
  });

  // ── Edge case: 128 chars all sets → very strong (spec §3.7.4) ──

  it("AC-SEC-016: 128-char all-sets password is ~832 bits → very_strong", () => {
    const result = generatePassword({ length: 128 });
    expect(result.actualLength).toBe(128);
    // charset = 26+26+10+25 = 87 chars, entropy ≈ 128 * log2(87)
    expect(result.strength).toBe("very_strong");
  });
});

// ═══════════════════════════════════════════════════════════════════════
// Token
// ═══════════════════════════════════════════════════════════════════════

describe("generateToken", () => {
  // ── Defaults ──────────────────────────────────────────────────────

  it("AC-SEC-020: default produces a 43-char token", () => {
    const result = generateToken();
    expect(result.secret).toHaveLength(43);
    expect(result.actualLength).toBe(43);
    expect(result.bits).toBe(43 * 6); // 258
  });

  // ── Length bounds ─────────────────────────────────────────────────

  it("AC-SEC-021: clamps to minimum 16", () => {
    const result = generateToken(1);
    expect(result.secret).toHaveLength(16);
    expect(result.actualLength).toBe(16);
  });

  it("AC-SEC-022: clamps to maximum 256", () => {
    const result = generateToken(999);
    expect(result.secret).toHaveLength(256);
    expect(result.actualLength).toBe(256);
  });

  it("AC-SEC-023: accepts length 16", () => {
    const result = generateToken(16);
    expect(result.secret).toHaveLength(16);
  });

  it("AC-SEC-024: accepts length 256", () => {
    const result = generateToken(256);
    expect(result.secret).toHaveLength(256);
  });

  // ── Base64url alphabet ────────────────────────────────────────────

  it("AC-SEC-025: token contains only base64url characters [A-Za-z0-9_-]", () => {
    for (let i = 0; i < ITERATIONS; i++) {
      const { secret } = generateToken();
      expect(secret).toMatch(BASE64URL_RE);
    }
  });

  it("AC-SEC-026: token never contains = padding", () => {
    for (let i = 0; i < ITERATIONS; i++) {
      const { secret } = generateToken();
      expect(secret).not.toContain("=");
    }
  });

  it("AC-SEC-027: token never contains + or / (standard base64, not base64url)", () => {
    for (let i = 0; i < ITERATIONS; i++) {
      const { secret } = generateToken();
      expect(secret).not.toContain("+");
      expect(secret).not.toContain("/");
    }
  });

  // ── Entropy ───────────────────────────────────────────────────────

  it("AC-SEC-028: token bits = length × 6", () => {
    const lengths = [16, 43, 128, 256];
    for (const len of lengths) {
      const result = generateToken(len);
      expect(result.bits).toBe(len * 6);
    }
  });

  // ── Strength ──────────────────────────────────────────────────────

  it("AC-SEC-029: 43-char token (258 bits) → very_strong (spec §3.7.4)", () => {
    const result = generateToken(43);
    expect(result.bits).toBe(258);
    expect(result.strength).toBe("very_strong");
  });

  it("AC-SEC-030: 16-char token (96 bits) → fair", () => {
    const result = generateToken(16);
    expect(result.bits).toBe(96);
    expect(result.strength).toBe("fair");
  });

  // ── Randomness ────────────────────────────────────────────────────

  it("AC-SEC-031: each call produces different output", () => {
    const results = new Set<string>();
    for (let i = 0; i < 50; i++) {
      results.add(generateToken().secret);
    }
    expect(results.size).toBe(50);
  });
});

// ═══════════════════════════════════════════════════════════════════════
// Hex
// ═══════════════════════════════════════════════════════════════════════

describe("generateHex", () => {
  // ── Defaults ──────────────────────────────────────────────────────

  it("AC-SEC-040: default produces a 64-char hex string", () => {
    const result = generateHex();
    expect(result.secret).toHaveLength(64);
    expect(result.actualLength).toBe(64);
    expect(result.bits).toBe(64 * 4); // 256
  });

  // ── Length bounds ─────────────────────────────────────────────────

  it("AC-SEC-041: clamps to minimum 16", () => {
    const result = generateHex(1);
    expect(result.secret).toHaveLength(16);
  });

  it("AC-SEC-042: clamps to maximum 512", () => {
    const result = generateHex(999);
    expect(result.secret).toHaveLength(512);
  });

  it("AC-SEC-043: accepts length 16", () => {
    const result = generateHex(16);
    expect(result.secret).toHaveLength(16);
  });

  it("AC-SEC-044: accepts length 512", () => {
    const result = generateHex(512);
    expect(result.secret).toHaveLength(512);
  });

  // ── Even length ───────────────────────────────────────────────────

  it("AC-SEC-045: output length is always even", () => {
    for (let i = 0; i < ITERATIONS; i++) {
      const { secret, actualLength } = generateHex();
      expect(actualLength % 2).toBe(0);
      expect(secret.length % 2).toBe(0);
    }
  });

  it("AC-SEC-046: odd requested length is rounded up to even", () => {
    const result = generateHex(17);
    expect(result.actualLength).toBe(18);
    expect(result.secret).toHaveLength(18);
  });

  it("AC-SEC-047: odd length 65 → 66 (rounded up)", () => {
    const result = generateHex(65);
    expect(result.actualLength).toBe(66);
    expect(result.secret).toHaveLength(66);
  });

  // ── Hex alphabet ──────────────────────────────────────────────────

  it("AC-SEC-048: hex contains only lowercase hex chars [0-9a-f]", () => {
    for (let i = 0; i < ITERATIONS; i++) {
      const { secret } = generateHex();
      expect(secret).toMatch(HEX_RE);
    }
  });

  it("AC-SEC-049: hex never contains uppercase A-F", () => {
    for (let i = 0; i < ITERATIONS; i++) {
      const { secret } = generateHex();
      expect(secret).not.toMatch(/[A-F]/);
    }
  });

  // ── Entropy ───────────────────────────────────────────────────────

  it("AC-SEC-050: hex bits = actualLength × 4", () => {
    const lengths = [16, 64, 256, 512];
    for (const len of lengths) {
      const result = generateHex(len);
      expect(result.bits).toBe(result.actualLength * 4);
    }
  });

  // ── Strength / edge case (spec §3.7.4) ────────────────────────────

  it("AC-SEC-051: 64-char hex (256 bits) → very_strong (spec §3.7.4)", () => {
    const result = generateHex(64);
    expect(result.bits).toBe(256);
    expect(result.strength).toBe("very_strong");
  });

  // ── Randomness ────────────────────────────────────────────────────

  it("AC-SEC-052: each call produces different output", () => {
    const results = new Set<string>();
    for (let i = 0; i < 50; i++) {
      results.add(generateHex().secret);
    }
    expect(results.size).toBe(50);
  });
});

// ═══════════════════════════════════════════════════════════════════════
// Entropy calculation
// ═══════════════════════════════════════════════════════════════════════

describe("entropyBits", () => {
  it("AC-SEC-060: password entropy = length × log2(charsetSize)", () => {
    // Uppercase only: 26 chars, log2(26) ≈ 4.7004
    const bits = entropyBits("password", 20, 26);
    expect(bits).toBeCloseTo(20 * Math.log2(26), 4);
  });

  it("AC-SEC-061: password with all 4 sets: 87 chars", () => {
    const bits = entropyBits("password", 128, 87);
    expect(bits).toBeCloseTo(128 * Math.log2(87), 4);
  });

  it("AC-SEC-062: password with charsetSize 0 returns 0", () => {
    expect(entropyBits("password", 20, 0)).toBe(0);
  });

  it("AC-SEC-063: password with undefined charsetSize returns 0", () => {
    expect(entropyBits("password", 20)).toBe(0);
  });

  it("AC-SEC-064: token entropy = length × 6", () => {
    expect(entropyBits("token", 43)).toBe(258);
    expect(entropyBits("token", 16)).toBe(96);
    expect(entropyBits("token", 256)).toBe(1536);
  });

  it("AC-SEC-065: hex entropy = length × 4", () => {
    expect(entropyBits("hex", 64)).toBe(256);
    expect(entropyBits("hex", 16)).toBe(64);
    expect(entropyBits("hex", 512)).toBe(2048);
  });
});

// ═══════════════════════════════════════════════════════════════════════
// Strength classification
// ═══════════════════════════════════════════════════════════════════════

describe("classifyStrength", () => {
  it("AC-SEC-070: < 64 bits → weak", () => {
    expect(classifyStrength(0)).toBe("weak");
    expect(classifyStrength(26.58)).toBe("weak");
    expect(classifyStrength(63)).toBe("weak");
    expect(classifyStrength(63.99)).toBe("weak");
  });

  it("AC-SEC-071: 64–127 bits → fair", () => {
    expect(classifyStrength(64)).toBe("fair");
    expect(classifyStrength(96)).toBe("fair");
    expect(classifyStrength(127)).toBe("fair");
    expect(classifyStrength(127.99)).toBe("fair");
  });

  it("AC-SEC-072: 128–255 bits → strong", () => {
    expect(classifyStrength(128)).toBe("strong");
    expect(classifyStrength(200)).toBe("strong");
    expect(classifyStrength(255)).toBe("strong");
    expect(classifyStrength(255.99)).toBe("strong");
  });

  it("AC-SEC-073: ≥ 256 bits → very_strong", () => {
    expect(classifyStrength(256)).toBe("very_strong");
    expect(classifyStrength(258)).toBe("very_strong");
    expect(classifyStrength(832)).toBe("very_strong");
    expect(classifyStrength(2048)).toBe("very_strong");
  });
});

// ═══════════════════════════════════════════════════════════════════════
// Statistical uniformity (anti-bias) — password mode
// ═══════════════════════════════════════════════════════════════════════

describe("Statistical uniformity", () => {
  it("AC-SEC-080: digits-only password has roughly uniform digit distribution", () => {
    const SAMPLE_COUNT = 10_000;
    const LENGTH = 64;
    const DIGIT_COUNT = 10;

    // Count occurrences of each digit across all samples.
    const counts = new Map<string, number>();
    for (let i = 0; i < SAMPLE_COUNT; i++) {
      const { secret } = generatePassword({
        length: LENGTH,
        uppercase: false,
        lowercase: false,
        digits: true,
        symbols: false,
      });
      for (const ch of secret) {
        counts.set(ch, (counts.get(ch) ?? 0) + 1);
      }
    }

    // Total characters = SAMPLE_COUNT * LENGTH = 640,000
    // Expected per digit = 64,000
    // With 640k draws, a ±15% tolerance should never flake for a true RNG.
    const totalChars = SAMPLE_COUNT * LENGTH;
    const expected = totalChars / DIGIT_COUNT;
    const tolerance = 0.15; // ±15%

    for (const digit of "0123456789") {
      const count = counts.get(digit) ?? 0;
      const deviation = Math.abs(count - expected) / expected;
      expect(deviation).toBeLessThan(tolerance);
    }
  });

  it("AC-SEC-081: single-char-class password covers all chars in its set", () => {
    // With a large enough sample, every character in the set should appear.
    const SAMPLE_COUNT = 500;
    const LENGTH = 128;

    // Test uppercase only: all 26 letters must appear
    const seen = new Set<string>();
    for (let i = 0; i < SAMPLE_COUNT; i++) {
      const { secret } = generatePassword({
        length: LENGTH,
        uppercase: true,
        lowercase: false,
        digits: false,
        symbols: false,
      });
      for (const ch of secret) seen.add(ch);
    }
    expect(seen.size).toBe(26);
  });
});

// ═══════════════════════════════════════════════════════════════════════
// Result shape
// ═══════════════════════════════════════════════════════════════════════

describe("Result contract", () => {
  it("AC-SEC-090: all results have secret, actualLength, bits, strength", () => {
    const pw = generatePassword();
    expect(pw).toHaveProperty("secret");
    expect(pw).toHaveProperty("actualLength");
    expect(pw).toHaveProperty("bits");
    expect(pw).toHaveProperty("strength");
    expect(typeof pw.secret).toBe("string");
    expect(typeof pw.actualLength).toBe("number");
    expect(typeof pw.bits).toBe("number");
    expect(["weak", "fair", "strong", "very_strong"]).toContain(pw.strength);

    const tk = generateToken();
    expect(tk).toHaveProperty("secret");
    expect(tk).toHaveProperty("actualLength");
    expect(tk).toHaveProperty("bits");
    expect(tk).toHaveProperty("strength");

    const hx = generateHex();
    expect(hx).toHaveProperty("secret");
    expect(hx).toHaveProperty("actualLength");
    expect(hx).toHaveProperty("bits");
    expect(hx).toHaveProperty("strength");
  });

  it("AC-SEC-091: actualLength matches secret.length", () => {
    for (let i = 0; i < ITERATIONS; i++) {
      const pw = generatePassword();
      expect(pw.actualLength).toBe(pw.secret.length);

      const tk = generateToken();
      expect(tk.actualLength).toBe(tk.secret.length);

      const hx = generateHex();
      expect(hx.actualLength).toBe(hx.secret.length);
    }
  });

  it("AC-SEC-092: bits is a positive finite number", () => {
    const pw = generatePassword();
    expect(Number.isFinite(pw.bits)).toBe(true);
    expect(pw.bits).toBeGreaterThan(0);

    const tk = generateToken();
    expect(Number.isFinite(tk.bits)).toBe(true);
    expect(tk.bits).toBeGreaterThan(0);

    const hx = generateHex();
    expect(Number.isFinite(hx.bits)).toBe(true);
    expect(hx.bits).toBeGreaterThan(0);
  });
});

// ═══════════════════════════════════════════════════════════════════════
// Token: exact byte-count vs output-length relationship
// ═══════════════════════════════════════════════════════════════════════

describe("Token byte-count / output-length invariant", () => {
  it("AC-SEC-100: ceil(length*6/8) bytes always produce ≥ length base64url chars", () => {
    // Verify for every length in the valid range that the encoding invariant
    // holds: the encoded string before trimming is at least `length` chars.
    for (let len = 16; len <= 256; len++) {
      const byteCount = Math.ceil((len * 6) / 8);
      // The number of base64url chars produced:
      //   - each full triple (3 bytes) → 4 chars
      //   - 2 remaining bytes → 3 chars
      //   - 1 remaining byte  → 2 chars
      const fullTriples = Math.floor(byteCount / 3);
      const remainder = byteCount % 3;
      const encodedLen = fullTriples * 4 + (remainder === 1 ? 2 : remainder === 2 ? 3 : 0);
      expect(encodedLen).toBeGreaterThanOrEqual(len);
    }
  });
});

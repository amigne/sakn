/**
 * Secret Generator — pure TypeScript cryptographic library.
 *
 * Generates cryptographically secure secrets directly in the browser using the
 * Web Crypto API (`crypto.getRandomValues`). No external dependencies.
 * No DOM/React code — pure logic (Sprint 2 of implementation plan).
 *
 * Three generation modes:
 *   - Password:  character-based with configurable charsets, rejection sampling
 *   - Token:     base64url (RFC 4648 §5), no padding
 *   - Hex:       lowercase hexadecimal
 *
 * Functional spec: docs/specs/functional-spec.md §3.7
 */

import type { SecretGeneratorMode, SecretGeneratorPasswordParams, SecretGeneratorResult, Strength } from "@/types/tool";

// ═══════════════════════════════════════════════════════════════════════
// Constants
// ═══════════════════════════════════════════════════════════════════════

/** Uppercase letters A-Z (26 chars). */
const UPPERCASE = "ABCDEFGHIJKLMNOPQRSTUVWXYZ";

/** Lowercase letters a-z (26 chars). */
const LOWERCASE = "abcdefghijklmnopqrstuvwxyz";

/** Decimal digits 0-9 (10 chars). */
const DIGITS = "0123456789";

/**
 * Password-legal symbol set (25 chars).
 *
 * Frozen per functional spec §3.7 — the exact set is a design constant,
 * not a user-configurable option.  These symbols are widely accepted by
 * web services and avoid shell meta-characters that cause copy-paste issues.
 */
const SYMBOLS = "!@#$%^&*()-_=+[]{};:,.<>?";

/** Base64url alphabet per RFC 4648 §5 (64 chars). */
const BASE64URL = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_";

/** Lowercase hexadecimal alphabet (16 chars). */
const HEX_ALPHABET = "0123456789abcdef";

// ═══════════════════════════════════════════════════════════════════════
// Bounds
// ═══════════════════════════════════════════════════════════════════════

const PASSWORD_LENGTH_MIN = 8;
const PASSWORD_LENGTH_MAX = 128;
const PASSWORD_LENGTH_DEFAULT = 20;

const TOKEN_LENGTH_MIN = 16;
const TOKEN_LENGTH_MAX = 256;
const TOKEN_LENGTH_DEFAULT = 43;

const HEX_LENGTH_MIN = 16;
const HEX_LENGTH_MAX = 512;
const HEX_LENGTH_DEFAULT = 64;

// ═══════════════════════════════════════════════════════════════════════
// Strength thresholds (entropy in bits)
// ═══════════════════════════════════════════════════════════════════════

/** Below 64 bits → weak (e.g. 8-digit PIN ≈ 26 bits). */
const STRENGTH_WEAK_MAX = 64;

/** 64–127 bits → fair. */
const STRENGTH_FAIR_MAX = 128;

/** 128–255 bits → strong. */
const STRENGTH_STRONG_MAX = 256;

// ═══════════════════════════════════════════════════════════════════════
// Error types
// ═══════════════════════════════════════════════════════════════════════

/** Typed error thrown by secret-generator functions. */
export class SecretGeneratorError extends Error {
  /** Machine-readable error code. */
  public readonly code: string;

  constructor(message: string, code: string) {
    super(message);
    this.name = "SecretGeneratorError";
    this.code = code;
  }
}

// ═══════════════════════════════════════════════════════════════════════
// CSPRNG helpers
// ═══════════════════════════════════════════════════════════════════════

/**
 * Fill `bytes` with cryptographically secure random values.
 *
 * Thin wrapper around `crypto.getRandomValues` for testability:
 * tests can spy on this single entry-point to assert CSPRNG usage.
 */
function fillRandomBytes(bytes: Uint8Array): void {
  crypto.getRandomValues(bytes);
}

/**
 * Return a `Uint8Array` of `count` cryptographically secure random bytes.
 */
function getRandomBytes(count: number): Uint8Array {
  const bytes = new Uint8Array(count);
  fillRandomBytes(bytes);
  return bytes;
}

// ═══════════════════════════════════════════════════════════════════════
// Rejection sampling
// ═══════════════════════════════════════════════════════════════════════

/**
 * Build `count` characters by rejection-sampling from `charset`.
 *
 * Rejection sampling guarantees **uniform** distribution over the charset
 * (anti-modulo-bias).  Byte values >= the largest multiple of `charsetSize`
 * ≤ 255 are discarded and re-rolled.
 *
 * @param charset  The set of allowed characters (no duplicates).
 * @param count    Number of characters to generate.
 * @returns        A string of exactly `count` characters drawn uniformly
 *                 from `charset`.
 */
function rejectionSample(charset: string, count: number): string {
  const charsetSize = charset.length;
  // Largest byte value that keeps the modulo uniform:
  //   maxValid = ⌊256 / charsetSize⌋ × charsetSize
  const maxValid = Math.floor(256 / charsetSize) * charsetSize;

  const chars: string[] = new Array(count);
  let filled = 0;

  while (filled < count) {
    // Fetch a generous batch — 2× the remaining need covers the expected
    // rejection rate (worst case ~50 % for a 129-char charset, which we
    // never reach).
    const batchSize = Math.max(16, (count - filled) * 2);
    const bytes = getRandomBytes(batchSize);

    for (let i = 0; i < bytes.length && filled < count; i++) {
      const byte = bytes[i]!;
      if (byte < maxValid) {
        chars[filled] = charset[byte % charsetSize]!;
        filled++;
      }
    }
  }

  return chars.join("");
}

// ═══════════════════════════════════════════════════════════════════════
// Encoders
// ═══════════════════════════════════════════════════════════════════════

/**
 * Encode `bytes` to **base64url** (RFC 4648 §5) **without** `=` padding.
 *
 * @param bytes        Random bytes to encode.
 * @param targetLength Trim the output to exactly this many characters.
 * @returns            Base64url-encoded string of length `targetLength`.
 */
function encodeBase64Url(bytes: Uint8Array, targetLength: number): string {
  let result = "";

  for (let i = 0; i < bytes.length; i += 3) {
    const remaining = bytes.length - i;
    const b0 = bytes[i]!;
    const b1 = remaining > 1 ? bytes[i + 1]! : 0;
    const b2 = remaining > 2 ? bytes[i + 2]! : 0;
    const triple = (b0 << 16) | (b1 << 8) | b2;

    result += BASE64URL[(triple >> 18) & 0x3f];
    result += BASE64URL[(triple >> 12) & 0x3f];
    if (remaining > 1) result += BASE64URL[(triple >> 6) & 0x3f];
    if (remaining > 2) result += BASE64URL[triple & 0x3f];
  }

  return result.slice(0, targetLength);
}

/**
 * Encode `bytes` to **lowercase hexadecimal**.
 *
 * Each byte → 2 hex characters.  The output length is always even.
 */
function encodeHex(bytes: Uint8Array): string {
  let result = "";
  for (let i = 0; i < bytes.length; i++) {
    const byte = bytes[i]!;
    result += HEX_ALPHABET[(byte >> 4) & 0xf];
    result += HEX_ALPHABET[byte & 0xf];
  }
  return result;
}

// ═══════════════════════════════════════════════════════════════════════
// Entropy & strength
// ═══════════════════════════════════════════════════════════════════════

/**
 * Compute the entropy in bits for a generated secret.
 *
 * | Mode       | Formula                  |
 * |------------|--------------------------|
 * | `password` | `length × log2(charset)` |
 * | `token`    | `length × 6`             |
 * | `hex`      | `length × 4`             |
 *
 * @param mode       The generation mode.
 * @param length     The **actual** output length in characters.
 * @param charsetSize For `password` mode: the total charset size
 *                    (sum of enabled sets).
 * @returns          Entropy in bits (finite positive number).
 */
export function entropyBits(mode: SecretGeneratorMode, length: number, charsetSize?: number): number {
  switch (mode) {
    case "password":
      // charsetSize is required for password mode
      if (charsetSize === undefined || charsetSize <= 0) {
        return 0;
      }
      return length * Math.log2(charsetSize);
    case "token":
      return length * 6;
    case "hex":
      return length * 4;
  }
}

/**
 * Classify password/token/hex strength from entropy in bits.
 *
 * Thresholds (aligned with functional spec §3.7.4 edge cases):
 *   - `< 64 bits`  → `"weak"`
 *   - `64–127`     → `"fair"`
 *   - `128–255`    → `"strong"`
 *   - `≥ 256 bits` → `"very_strong"`
 */
export function classifyStrength(bits: number): Strength {
  if (bits < STRENGTH_WEAK_MAX) return "weak";
  if (bits < STRENGTH_FAIR_MAX) return "fair";
  if (bits < STRENGTH_STRONG_MAX) return "strong";
  return "very_strong";
}

/**
 * Convenience: compute both entropy bits and strength classification.
 */
function computeBitsAndStrength(
  mode: SecretGeneratorMode,
  length: number,
  charsetSize?: number,
): { bits: number; strength: Strength } {
  const bits = entropyBits(mode, length, charsetSize);
  const strength = classifyStrength(bits);
  return { bits, strength };
}

// ═══════════════════════════════════════════════════════════════════════
// Public API — Password
// ═══════════════════════════════════════════════════════════════════════

/**
 * Build the effective charset from the user's boolean toggles.
 *
 * @throws {SecretGeneratorError} `no_charset_selected` if all toggles are
 *         `false`.
 */
function buildCharset(opts: SecretGeneratorPasswordParams): string {
  const parts: string[] = [];
  if (opts.uppercase) parts.push(UPPERCASE);
  if (opts.lowercase) parts.push(LOWERCASE);
  if (opts.digits) parts.push(DIGITS);
  if (opts.symbols) parts.push(SYMBOLS);

  if (parts.length === 0) {
    throw new SecretGeneratorError(
      "At least one character set must be enabled (uppercase, lowercase, digits, symbols).",
      "no_charset_selected",
    );
  }

  return parts.join("");
}

/**
 * Generate a cryptographically secure password.
 *
 * Uses rejection sampling over the Web Crypto API for uniform character
 * distribution (no modulo bias).
 *
 * @param opts.uppercase  Include A-Z (default `true`).
 * @param opts.lowercase  Include a-z (default `true`).
 * @param opts.digits     Include 0-9 (default `true`).
 * @param opts.symbols    Include `!@#$%^&*()-_=+[]{};:,.<>?` (default `true`).
 * @param opts.length     Output length in characters (8–128, default 20).
 * @returns               The generated password with metadata.
 * @throws {SecretGeneratorError} `no_charset_selected` if no charset enabled.
 */
export function generatePassword(opts: Partial<SecretGeneratorPasswordParams> = {}): SecretGeneratorResult {
  const length = Math.max(PASSWORD_LENGTH_MIN, Math.min(PASSWORD_LENGTH_MAX, opts.length ?? PASSWORD_LENGTH_DEFAULT));

  const fullOpts: SecretGeneratorPasswordParams = {
    mode: "password",
    length,
    uppercase: opts.uppercase ?? true,
    lowercase: opts.lowercase ?? true,
    digits: opts.digits ?? true,
    symbols: opts.symbols ?? true,
  };

  const charset = buildCharset(fullOpts);
  const secret = rejectionSample(charset, length);
  const { bits, strength } = computeBitsAndStrength("password", length, charset.length);

  return { secret, actualLength: length, bits, strength };
}

// ═══════════════════════════════════════════════════════════════════════
// Public API — Token
// ═══════════════════════════════════════════════════════════════════════

/**
 * Generate a cryptographically secure URL-safe token.
 *
 * Equivalent to Python `secrets.token_urlsafe(ceil(length * 6 / 8))`
 * trimmed to `length` characters.
 *
 * Encoding: base64url (RFC 4648 §5) using `-` and `_`, **no** `=` padding.
 * Each character encodes 6 bits of entropy.
 *
 * @param length  Output length in characters (16–256, default 43).
 * @returns       The generated token with metadata.
 */
export function generateToken(length?: number): SecretGeneratorResult {
  const actualLength = Math.max(TOKEN_LENGTH_MIN, Math.min(TOKEN_LENGTH_MAX, length ?? TOKEN_LENGTH_DEFAULT));

  // We need ceil(actualLength * 6 / 8) random bytes to guarantee at least
  // `actualLength` base64url characters.
  const byteCount = Math.ceil((actualLength * 6) / 8);
  const bytes = getRandomBytes(byteCount);
  const secret = encodeBase64Url(bytes, actualLength);

  const { bits, strength } = computeBitsAndStrength("token", actualLength);

  return { secret, actualLength, bits, strength };
}

// ═══════════════════════════════════════════════════════════════════════
// Public API — Hex
// ═══════════════════════════════════════════════════════════════════════

/**
 * Generate a cryptographically secure hexadecimal secret.
 *
 * Equivalent to `openssl rand -hex ceil(length / 2)` trimmed/padded to an
 * even length.
 *
 * Encoding: lowercase hex `[0-9a-f]`.  Each character encodes 4 bits of
 * entropy.  Output length is always even (odd inputs are rounded up).
 *
 * @param length  Output length in characters (16–512, default 64).
 * @returns       The generated hex secret with metadata.
 */
export function generateHex(length?: number): SecretGeneratorResult {
  const requested = Math.max(HEX_LENGTH_MIN, Math.min(HEX_LENGTH_MAX, length ?? HEX_LENGTH_DEFAULT));

  // Round up to even — each byte produces 2 hex characters.
  const actualLength = requested % 2 === 0 ? requested : requested + 1;

  const byteCount = Math.ceil(actualLength / 2);
  const bytes = getRandomBytes(byteCount);
  const secret = encodeHex(bytes);

  // Secret length should always be `actualLength` (even).
  // If we got 1 character more due to odd byteCount rounding, slice it.
  const trimmed = secret.length > actualLength ? secret.slice(0, actualLength) : secret;

  const { bits, strength } = computeBitsAndStrength("hex", actualLength);

  return { secret: trimmed, actualLength, bits, strength };
}

// ═══════════════════════════════════════════════════════════════════════
// Convenience: strength display helper
// ═══════════════════════════════════════════════════════════════════════

/**
 * Return a human-readable strength label for the given bit count.
 *
 * Thin re-export of {@link classifyStrength} — useful for components that
 * only have a bit count and no result object.
 */
export { classifyStrength as strength };

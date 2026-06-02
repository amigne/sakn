/**
 * MAC / OUI extraction frontend (ADR-014 §3).
 *
 * Policy: recall > precision (ADR-014 §2.2).
 * Strategy: apply regexes in descending length order (48 → 36 → 28 → 24 bits),
 * consume matched positions so shorter patterns don't re-match inside longer ones.
 */

export interface ExtractedOui {
  /** The raw substring as it appeared in the input text. */
  raw: string;
  /** Bare hex uppercase, length ∈ {6, 7, 9, 12}. */
  normalized: string;
  /** IEEE bit-size corresponding to the hex-digit count. */
  bitSize: 24 | 28 | 36 | 48;
}

export interface ExtractionResult {
  /** Deduplicated OUI entries (by .normalized). */
  unique: ExtractedOui[];
  /** Total matches found before deduplication. */
  totalMatchesBeforeDedup: number;
  /** Number of characters actually processed (min(text.length, maxChars)). */
  totalInputChars: number;
  /** Whether the input was truncated. */
  truncated: boolean;
}

// ── Patterns ordered by descending bit-size ──────────────────────────

interface PatternSpec {
  re: RegExp;
  bitSize: 24 | 28 | 36 | 48;
}

function buildPatterns(): PatternSpec[] {
  return [
    // ── 48-bit (MAC complète) ──────────────────────────────────────
    { re: /(?:[0-9A-Fa-f]{2}[:.-]){5}[0-9A-Fa-f]{2}/g, bitSize: 48 },
    { re: /(?:[0-9A-Fa-f]{4}\.){2}[0-9A-Fa-f]{4}/g, bitSize: 48 },
    { re: /\b[0-9A-Fa-f]{12}\b/g, bitSize: 48 },

    // ── 36-bit (MA-S) ──────────────────────────────────────────────
    { re: /(?:[0-9A-Fa-f]{2}[:.-]){3}[0-9A-Fa-f]{2}[:.-][0-9A-Fa-f]/g, bitSize: 36 },
    { re: /(?:[0-9A-Fa-f]{4}\.)[0-9A-Fa-f]{4}\.[0-9A-Fa-f]/g, bitSize: 36 },
    { re: /\b[0-9A-Fa-f]{9}\b/g, bitSize: 36 },

    // ── 28-bit (MA-M) ──────────────────────────────────────────────
    { re: /(?:[0-9A-Fa-f]{2}[:.-]){2}[0-9A-Fa-f]{2}[:.-][0-9A-Fa-f]/g, bitSize: 28 },
    { re: /\b[0-9A-Fa-f]{7}\b/g, bitSize: 28 },

    // ── 24-bit (OUI 3 octets) ──────────────────────────────────────
    { re: /(?:[0-9A-Fa-f]{2}[:.-]){2}[0-9A-Fa-f]{2}/g, bitSize: 24 },
    { re: /[0-9A-Fa-f]{4}\.[0-9A-Fa-f]{2}/g, bitSize: 24 },
    { re: /\b[0-9A-Fa-f]{6}\b/g, bitSize: 24 },
  ];
}

// ── Helpers ──────────────────────────────────────────────────────────

const SEP = /[:.-]/g;
const HEX_ONLY = /^[0-9A-F]+$/;

function normalize(raw: string): string | null {
  const stripped = raw.replace(SEP, "").toUpperCase();
  if (!HEX_ONLY.test(stripped)) return null;
  if (![6, 7, 9, 12].includes(stripped.length)) return null;
  return stripped;
}

// ── Main export ──────────────────────────────────────────────────────

export function extractOuis(
  text: string,
  opts?: { maxChars?: number },
): ExtractionResult {
  const maxChars = opts?.maxChars ?? 50_000;
  const truncated = text.length > maxChars;
  const input = truncated ? text.slice(0, maxChars) : text;

  // Position mask: once a character index is consumed, shorter patterns
  // cannot match across it (prevents truncating a 48-bit MAC to 24-bit).
  const consumed = new Array<boolean>(input.length);
  let consumedCount = 0;

  function isConsumed(start: number, end: number): boolean {
    for (let i = start; i < end; i++) {
      if (consumed[i]) return true;
    }
    return false;
  }

  function markConsumed(start: number, end: number): void {
    for (let i = start; i < end; i++) {
      if (!consumed[i]) {
        consumed[i] = true;
        consumedCount++;
      }
    }
  }

  const results: ExtractedOui[] = [];
  const patterns = buildPatterns();

  for (const { re, bitSize } of patterns) {
    // Reset lastIndex for the global regex.
    re.lastIndex = 0;
    let match: RegExpExecArray | null;
    while ((match = re.exec(input)) !== null) {
      const start = match.index;
      const end = start + match[0].length;

      if (isConsumed(start, end)) continue;

      const norm = normalize(match[0]);
      if (norm === null) continue;

      markConsumed(start, end);
      results.push({ raw: match[0], normalized: norm, bitSize });
    }
  }

  // Deduplicate by normalized value (first occurrence wins).
  const seen = new Set<string>();
  const unique: ExtractedOui[] = [];
  for (const r of results) {
    if (!seen.has(r.normalized)) {
      seen.add(r.normalized);
      unique.push(r);
    }
  }

  return {
    unique,
    totalMatchesBeforeDedup: results.length,
    totalInputChars: input.length,
    truncated,
  };
}

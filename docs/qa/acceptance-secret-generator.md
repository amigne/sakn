# Acceptance Criteria — Secret Generator

> **Version:** 1.0
> **Status:** Draft — Sprint 0
> **Date:** 2026-06-05
> **Module:** Secret Generator (`secret_generator`)
> **References:** `functional-spec.md` §3.7, `spec-tool-secret-generator.md`, `ui-spec.md` SCR-28, ADR-017

---

## 1. Backend Contract (Sprint 1)

### AC-SECRET-001 — Tool registered in `/tools` response

**Given** the backend is running
**When** `GET /tools` is called
**Then** the response includes an entry with `"name": "secret_generator"`, `"backend": false`, `"category": "security"`, and all parameters defined in `spec-tool-secret-generator.md` §2.1

### AC-SECRET-002 — `backend: false` field present

**Given** the `/tools` response includes `secret_generator`
**When** the JSON is inspected
**Then** `"backend": false` is present. All other tools have `"backend": true`.

### AC-SECRET-003 — `POST /tools/secret_generator/execute` returns 405

**Given** the tool `secret_generator` has `backend: false`
**When** `POST /api/v1/tools/secret_generator/execute` is called
**Then** the response is HTTP 405 with error code `TOOL_IS_FRONTEND_ONLY`

### AC-SECRET-004 — Seed creates `ToolModule` row

**Given** the application boots for the first time after deployment
**When** the seed runs
**Then** a `ToolModule` row exists with `name="secret_generator"`, `enabled=True`

### AC-SECRET-005 — Seed creates `RoleToolPermission` rows

**Given** the application boots
**When** the seed runs
**Then** `RoleToolPermission` rows exist for `(visitor, secret_generator)`, `(authenticated, secret_generator)`, and `(administrator, secret_generator)`, all with `allowed=True`

### AC-SECRET-006 — Admin can disable the tool globally

**Given** an admin sets `ToolModule.enabled=false` for `secret_generator`
**When** any user requests `/tools`
**Then** `secret_generator` is absent from the response. Direct navigation to `/secret-generator` shows "Tool not available."

### AC-SECRET-007 — Admin can revoke per-role permission

**Given** an admin toggles off the `visitor` permission for `secret_generator`
**When** a visitor requests `/tools`
**Then** `secret_generator` is absent from the response

### AC-SECRET-008 — Tool removed from sidebar when disabled

**Given** a user's effective permission for `secret_generator` is `false`
**When** the sidebar renders
**Then** "Secret Generator" is absent from the sidebar (consistent with existing tool gating, `ui-spec.md` §4.3)

### AC-SECRET-009 — No migration required

**Given** the `secret_generator` deployment
**When** Alembic runs `alembic upgrade head`
**Then** no new migration is generated (no schema change needed — `ToolModule` table is reused)

---

## 2. Password Mode (Sprint 3+)

### AC-SECRET-010 — Default parameters

**Given** the user opens the Secret Generator for the first time
**When** the page renders
**Then** the Password tab is active, length = 20, all four character set toggles are ON. A 20-character password is displayed.

### AC-SECRET-011 — Generation with all character sets

**Given** Password mode, length = 20, uppercase ON, lowercase ON, digits ON, symbols ON
**When** a secret is generated
**Then** the output is exactly 20 characters and contains characters from at least 2 of the 4 sets (statistically nearly certain; test over 100 generations, all must pass)

### AC-SECRET-012 — Generation with single character set

**Given** Password mode, length = 32, only digits ON
**When** a secret is generated
**Then** the output is exactly 32 characters, all digits (0-9)

### AC-SECRET-013 — Last character set toggle protected

**Given** Password mode, only digits ON (all others OFF)
**When** the user attempts to toggle digits OFF
**Then** the toggle snaps back to ON. A tooltip or inline message explains "At least one character set must be selected." (i18n `tools.secret_generator.no_charset_selected`)

### AC-SECRET-014 — Length bounds enforced (8–128)

**Given** Password mode
**When** the user sets length via slider or number input
**Then** values < 8 are clamped to 8. Values > 128 are clamped to 128. The slider and number input stay synchronized.

### AC-SECRET-015 — Uniform distribution (no modulo bias)

**Given** Password mode, only digits ON (charset size = 10), length = 1
**When** 10 000 secrets are generated
**Then** each digit (0-9) appears with frequency 9%–11% (chi-squared test, p > 0.01). This confirms rejection sampling eliminates modulo bias — with naive `byte % 10`, digits 0-5 would appear ~30% more often than 6-9.

### AC-SECRET-016 — Entropy: length = 8, digits only → weak

**Given** Password mode, length = 8, only digits ON
**When** the secret is generated
**Then** the strength indicator shows "Weak" (red), and the entropy line shows `"8 caractères (~26 bits)"` (entropy = 8 × log2(10) ≈ 26.6, displayed as 26)

### AC-SECRET-017 — Entropy: length = 128, all sets → very strong

**Given** Password mode, length = 128, all 4 sets ON (charset size ≈ 94)
**When** the secret is generated
**Then** the strength indicator shows "Very Strong" (green), entropy ≈ 128 × log2(94) ≈ 838 bits

### AC-SECRET-018 — Charset composition

**Given** Password mode, uppercase ON, lowercase ON, digits ON, symbols ON
**When** a secret is generated
**Then** the charset used is exactly: A-Z (26) + a-z (26) + 0-9 (10) + `!#$%&'()*+,-./:;<=>?@[\]^_`{|}~` (32) = 94 characters. Space and other whitespace are excluded.

---

## 3. Token Mode (Sprint 3+)

### AC-SECRET-019 — Default token

**Given** the user switches to Token mode
**When** the page updates
**Then** length = 43 is pre-filled. A 43-character base64url token is displayed (characters limited to `A-Z a-z 0-9 - _`).

### AC-SECRET-020 — Base64url alphabet confirmed

**Given** Token mode, length = 256
**When** 100 tokens are generated
**Then** all characters in all tokens belong to the set `[A-Za-z0-9_-]`. No `+`, `/`, or `=` appear.

### AC-SECRET-021 — Length matches request

**Given** Token mode, length = 43
**When** a token is generated
**Then** the output is exactly 43 characters

### AC-SECRET-022 — Entropy: 43 chars → 258 bits

**Given** Token mode, length = 43
**When** the token is generated
**Then** the entropy line displays `"43 caractères (258 bits)"` (43 × 6 = 258)

### AC-SECRET-023 — Output trimmed to exactly the requested length

**Given** Token mode, length = 43
**When** the token is generated (33 random bytes → 44 base64url chars → trimmed to 43)
**Then** the output is exactly 43 characters and the displayed length equals the requested length. `ceil(length * 6 / 8)` bytes always yield ≥ `length` base64url chars, so the output is never shorter than requested (entropy = `length × 6`).

### AC-SECRET-024 — Length bounds enforced (16–256)

**Given** Token mode
**When** the user sets length
**Then** values < 16 are clamped to 16. Values > 256 are clamped to 256.

---

## 4. Hex Mode (Sprint 3+)

### AC-SECRET-025 — Default hex secret

**Given** the user switches to Hex mode
**When** the page updates
**Then** length = 64 is pre-filled. A 64-character lowercase hex secret is displayed.

### AC-SECRET-026 — Output always even

**Given** Hex mode, length = 17 (odd)
**When** a secret is generated
**Then** the output is 18 characters (ceil(17/2) = 9 bytes → 18 hex chars). The displayed length is 18.

### AC-SECRET-027 — Output always lowercase

**Given** Hex mode, length = 64
**When** 100 secrets are generated
**Then** all characters are in `[0-9a-f]`. No uppercase hex digits (`A-F`) appear.

### AC-SECRET-028 — Entropy: 64 chars → 256 bits

**Given** Hex mode, length = 64
**When** the secret is generated
**Then** the entropy line displays `"64 caractères (256 bits)"` (64 × 4 = 256)

### AC-SECRET-029 — Length bounds enforced (16–512)

**Given** Hex mode
**When** the user sets length
**Then** values < 16 are clamped to 16. Values > 512 are clamped to 512.

---

## 5. CSPRNG (Sprint 2+)

### AC-SECRET-030 — Uses `crypto.getRandomValues()`

**Given** the Secret Generator tool is loaded
**When** any generation function is called
**Then** `crypto.getRandomValues()` (or `crypto.subtle`) is the sole source of randomness. `Math.random()` is never called. (Verify by code review: grep for `Math.random` in the secret generator source files — must be zero hits.)

### AC-SECRET-031 — CSPRNG unavailable → error state

**Given** a browser that lacks `crypto.getRandomValues` (hypothetical — all modern browsers support it)
**When** the tool attempts to generate
**Then** an error message is displayed: "Your browser does not support secure random number generation." The tool is unusable.

---

## 6. Strength Indicator (Sprint 3+)

### AC-SECRET-032 — Weak: < 64 bits

**Given** Password mode, length = 8, only digits ON → entropy ≈ 26 bits
**When** the strength is computed
**Then** the indicator shows "Weak" (red), icon ⚠️

### AC-SECRET-033 — Fair: 64–127 bits

**Given** Password mode, length = 12, only lowercase ON → entropy = 12 × log2(26) ≈ 56 bits (weak). Length = 14, only lowercase → entropy = 14 × log2(26) ≈ 66 bits (fair)
**When** the strength is computed for 66 bits
**Then** the indicator shows "Fair" (orange), icon 🔶

### AC-SECRET-034 — Strong: 128–255 bits

**Given** Password mode, length = 20, all sets ON → entropy = 20 × log2(94) ≈ 131 bits
**When** the strength is computed
**Then** the indicator shows "Strong" (blue), icon 🔵

### AC-SECRET-035 — Very Strong: ≥ 256 bits

**Given** Password mode, length = 40, all sets ON → entropy ≈ 262 bits
**When** the strength is computed
**Then** the indicator shows "Very Strong" (green), icon 🟢

---

## 7. Clipboard (Sprint 3+)

### AC-SECRET-036 — Copy to clipboard works

**Given** the Clipboard API is available and a secret is displayed
**When** the user clicks "Copy"
**Then** `navigator.clipboard.writeText()` is called with the secret. The button shows "Copied!" (i18n `tools.secret_generator.copied`) for 2 seconds, then reverts to "Copy."

### AC-SECRET-037 — Auto-clear after 30 seconds (best-effort)

**Given** the user clicks "Copy" and does NOT paste within 30 seconds
**When** 30 seconds elapse
**Then** the application *attempts* to clear the clipboard (set to empty string) and the auto-clear countdown (30 → 0) is shown.
**Note**: clearing is **best-effort**. Writing/reading the clipboard 30 s after the Copy click happens without a user gesture (transient activation), which Firefox and Safari block and Chrome may gate behind a permission. Where the browser blocks it, the clear silently no-ops (no error surfaced). The countdown UI and the auto-clear notice (§5.5.4) inform the user regardless. PASS = the clear is attempted and succeeds in a Chromium secure context with clipboard permission; degradation on other browsers is expected, not a FAIL.

### AC-SECRET-038 — Auto-clear preserves unrelated content

**Given** the clipboard contains "original content" before the user clicks Copy
**When** the auto-clear timer fires
**Then** the clipboard is only cleared if it still contains the generated secret. If the user pasted and overwrote the clipboard, the new content is preserved.

### AC-SECRET-039 — Timer resets on new Copy

**Given** the user clicks "Copy" and the 30 s countdown reaches 10 s
**When** the user clicks "Copy" again (same or regenerated secret)
**Then** the countdown resets to 30 s

### AC-SECRET-040 — Clipboard unavailable → button hidden

**Given** `navigator.clipboard?.writeText` is `undefined` (old browser, HTTP origin)
**When** the page renders
**Then** the "Copy" button is not rendered. The hint `tools.secret_generator.clipboard_unavailable` is displayed. The secret field uses `user-select: all` for manual selection.

### AC-SECRET-041 — Secret field is selectable

**Given** any mode, any secret
**When** the user interacts with the secret display field
**Then** the text is selectable (not `user-select: none`). Triple-click selects the entire secret.

---

## 8. Regenerate (Sprint 3+)

### AC-SECRET-042 — Regenerate produces a different secret

**Given** Password mode, default parameters
**When** the user clicks "Regenerate" 10 times
**Then** at least 9 of the 10 secrets are different (statistical: collision probability is astronomically low for 256-bit space; one duplicate in 10 is acceptable as a test flake, retry).

### AC-SECRET-043 — Regenerate preserves parameters

**Given** the user changes length to 32, disables symbols
**When** the user clicks "Regenerate"
**Then** the new secret respects length = 32 and has no symbols. Parameters are unchanged.

### AC-SECRET-044 — Parameter change regenerates automatically

**Given** any mode
**When** the user changes a parameter (length slider, toggle, mode tab)
**Then** a new secret is generated immediately (no "Start" button). Debounce slider input by 150 ms to avoid generating on every intermediate value.

---

## 9. Degraded States (Sprint 3+)

### AC-SECRET-045 — JavaScript disabled

**Given** JavaScript is disabled in the browser
**When** the user navigates to `/secret-generator`
**Then** a `<noscript>` fallback message is displayed: `tools.secret_generator.js_disabled`. The sidebar may render (if SSR) but the tool area is the noscript message.

### AC-SECRET-046 — No character set selected (UI bypass)

**Given** an attacker bypasses the UI to set all toggles to OFF (e.g., via browser console)
**When** the generation function is called
**Then** no secret is generated. The secret field displays `tools.secret_generator.no_charset_selected`.

---

## 10. Mode Switching (Sprint 3+)

### AC-SECRET-047 — Switch Password → Token preserves length

**Given** Password mode, length = 20
**When** the user switches to Token mode
**Then** the Token length slider resets to its default (43). Parameters are not shared between modes.

### AC-SECRET-048 — Switch Token → Hex

**Given** Token mode
**When** the user switches to Hex mode
**Then** the hex-specific slider (16–512) is displayed. A 64-character hex secret is generated.

### AC-SECRET-049 — Tab keyboard navigation

**Given** focus is on the Password tab
**When** the user presses Arrow Right
**Then** focus moves to the Token tab. Arrow Right again → Hex. Arrow Left → Token. The active tab follows focus (activation on focus, not on Enter/Space — consistent with ARIA tabs pattern with automatic activation).

---

## 11. Accessibility (Sprint 3+)

### AC-SECRET-050 — All controls have labels

**Given** the Secret Generator page
**When** inspected with a screen reader
**Then** every parameter control (slider, number input, toggle) has an associated `<label>` element

### AC-SECRET-051 — Result announced to screen readers

**Given** a screen reader is active
**When** a new secret is generated (parameter change or Regenerate click)
**Then** the result area's `aria-live="polite"` region announces: "Secret generated: [strength level], [N] characters, [X] bits of entropy."

### AC-SECRET-052 — Focus order is logical

**Given** the Secret Generator page (desktop)
**When** the user presses Tab repeatedly
**Then** the focus order is: Mode tabs → Parameters (top to bottom) → Regenerate → Copy (if available). No focus trap.

### AC-SECRET-053 — Visible focus ring

**Given** any interactive element on the page
**When** the element receives keyboard focus
**Then** a visible focus ring (2px offset, high contrast) is displayed

---

## 12. Responsive (Sprint 3+)

### AC-SECRET-054 — Desktop layout (≥ 1024px)

**Given** a viewport width of 1200px
**When** the page renders
**Then** the layout is multi-column: tabs + parameters + result. The sidebar is expanded.

### AC-SECRET-055 — Mobile layout (< 768px)

**Given** a viewport width of 375px
**When** the page renders
**Then** the layout is single-column stacked: tabs → parameters → result. All touch targets (toggles, buttons) are ≥ 44×44px.

### AC-SECRET-056 — Long secret scrolls horizontally

**Given** Token mode, length = 256
**When** the secret is displayed on mobile
**Then** the secret field has `overflow-x: auto` — the page itself does not require horizontal scroll.

---

## 13. i18n (Sprint 3+)

### AC-SECRET-057 — French locale

**Given** the user's locale is `fr`
**When** the Secret Generator page renders
**Then** all labels, messages, and the strength indicator are in French

### AC-SECRET-058 — English locale

**Given** the user's locale is `en`
**When** the Secret Generator page renders
**Then** all labels, messages, and the strength indicator are in English

### AC-SECRET-059 — All i18n keys present

**Given** the keys listed in `spec-tool-secret-generator.md` §6 and `spec-api-contract.md` §10.3
**When** the i18n key audit runs
**Then** all `tools.secret_generator.*` and `errors.tool_is_frontend_only` keys exist in both `fr.json` and `en.json`

---

## 14. Security (Sprint 4 — QA)

### AC-SECRET-060 — No secret transmitted to backend

**Given** the Secret Generator tool is used
**When** monitoring network requests during generation, Copy, and Regenerate
**Then** no `POST /api/v1/tools/secret_generator/execute` is called. The only API calls are `GET /tools` (on page load) and `GET /api/v1/auth/me` (session check). (Verify via DevTools Network tab.)

### AC-SECRET-061 — No secret logged to console

**Given** the Secret Generator is used
**When** checking the browser console
**Then** no `console.log` or `console.debug` call outputs the generated secret. (Verify by code review — search for `console.log` in the secret generator source files.)

### AC-SECRET-062 — CSPRNG source is `crypto.getRandomValues`

**Given** the secret generator source code
**When** searching for randomness sources
**Then** `Math.random()` is absent. `crypto.getRandomValues` is present.

### AC-SECRET-063 — No backend endpoint for execution

**Given** the route registration
**When** `POST /api/v1/tools/secret_generator/execute` is called
**Then** the response is 405 (verified in AC-SECRET-003). No subprocess is spawned, no file is written.

---

## 15. Cross-References

| Source | Sections |
|---|---|
| `functional-spec.md` | §3.7 (Secret Generator) |
| `spec-tool-secret-generator.md` | Full technical specification |
| `ui-spec.md` | SCR-28, §5.5, §12.3–12.4 |
| `spec-api-contract.md` | §6 (Tools), §10.3 (i18n keys) |
| `docs/adr/ADR-017-frontend-only-tool-pattern.md` | Architectural decision |
| `docs/security/review-secret-generator.md` | Security review |

---

## 16. Test Status

| Sprint | Scope | ACs |
|---|---|---|
| Sprint 1 (Backend Contract) | AC-SECRET-001 → 009 | Pending |
| Sprint 2 (Lib + algorithms) | AC-SECRET-010 → 031 (unit tests) | Pending |
| Sprint 3 (UI + E2E) | AC-SECRET-032 → 059 | Pending |
| Sprint 4 (QA + hardening) | AC-SECRET-060 → 063 + regression | Pending |

# Implementation Plan — Secret Generator

> **Version:** 1.0
> **Status:** Draft — Sprint 0
> **Date:** 2026-06-05
> **Module:** Secret Generator (`secret_generator`)
> **Integration Branch:** `dev0.2.0-secretgen`
> **References:** `functional-spec.md` §3.7, `spec-tool-secret-generator.md`, `ui-spec.md` SCR-28, ADR-017

---

## 1. Sprint Breakdown

| Sprint | Focus | Duration | Deliverables |
|---|---|---|---|
| Sprint 0 | Documentation | — | This document + UI spec + Tech spec + ADR-017 + AC + Security review |
| Sprint 1 | Backend Contract | 1–2 days | `ToolDefinition.backend`, `SecretGeneratorTool`, 405 guard, seed, `/tools` response |
| Sprint 2 | Client Library | 2–3 days | CSPRNG wrapper, password/token/hex generators, entropy calculator, strength classifier |
| Sprint 3 | UI + Integration | 3–4 days | React page, mode tabs, sliders/toggles, secret display, Copy/Regenerate, i18n |
| Sprint 4 | QA + Hardening | 2–3 days | E2E tests, accessibility audit, security validation, clipboard edge cases, cross-browser |

---

## 2. Sprint 1 — Backend Contract

**Goal**: The `secret_generator` tool appears in `GET /tools` with `backend: false`. Admin can manage it. The execute endpoint returns 405.

### Files Touched

| File | Change |
|---|---|
| `src/backend/app/tools/base.py` | Add `backend: bool = True` to `ToolDefinition`. Serialize in `to_api_definition()`. |
| `src/backend/app/tools/secret_generator.py` | **New**: `SecretGeneratorTool` class. `get_definition()` only. No `execute()`. |
| `src/backend/app/main.py` | Import + `registry.register(SecretGeneratorTool())`. Seed handled automatically. |
| `src/backend/app/api/api_v1.py` (or execute route) | Guard: check `tool.get_definition().backend`. If `False`, return 405. |
| `tests/unit/test_secret_generator_tool.py` | **New**: test `/tools` includes secret_generator with `backend: false`, test 405 on execute, test seed creates rows. |
| `tests/unit/test_tool_definition_backend_field.py` | **New** (or extend existing): test `backend` defaults to `True`, test serialization. |

### Acceptance Criteria Validated

AC-SECRET-001 through AC-SECRET-009.

### Definition of Done

- [ ] `GET /tools` returns `secret_generator` with `"backend": false`
- [ ] `POST /api/v1/tools/secret_generator/execute` returns 405 with `TOOL_IS_FRONTEND_ONLY`
- [ ] `ToolModule` row created on boot
- [ ] `RoleToolPermission` rows for all 3 roles with `allowed=True`
- [ ] Admin can enable/disable and toggle per-role permissions
- [ ] All unit tests pass
- [ ] No migration generated (`alembic revision --autogenerate` produces empty)

---

## 3. Sprint 2 — Client Library

**Goal**: Pure TypeScript library with no React dependency. Generates secrets, computes entropy, classifies strength. Fully unit-tested.

### Files Touched

| File | Change |
|---|---|
| `src/frontend/src/lib/crypto/random.ts` | **New**: `getRandomBytes(n)` wrapper around `crypto.getRandomValues` |
| `src/frontend/src/lib/crypto/password.ts` | **New**: `generatePassword(length, charsets)` with rejection sampling |
| `src/frontend/src/lib/crypto/token.ts` | **New**: `generateToken(length)` — base64url (RFC 4648 §5), no padding |
| `src/frontend/src/lib/crypto/hex.ts` | **New**: `generateHex(length)` — lowercase hex |
| `src/frontend/src/lib/crypto/entropy.ts` | **New**: `computeEntropy(length, charsetSize)`, `classifyStrength(bits)` |
| `src/frontend/src/lib/crypto/index.ts` | **New**: barrel export |
| `tests/unit/frontend/crypto/password.test.ts` | **New**: distribution (chi-squared), length, charset, rejection sampling |
| `tests/unit/frontend/crypto/token.test.ts` | **New**: alphabet, length, alignment, entropy |
| `tests/unit/frontend/crypto/hex.test.ts` | **New**: alphabet (lowercase only), evenness, entropy |
| `tests/unit/frontend/crypto/entropy.test.ts` | **New**: thresholds, edge cases |

### Algorithms (Tested in Isolation)

- **Rejection sampling** (password): `while (byte >= max_valid) { byte = getRandomBytes(1)[0] }`. Tested with chi-squared on 10 000 samples.
- **Base64url** (token): `btoa` + `replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')`. Must match Python `base64.urlsafe_b64encode(bytes).rstrip(b'=').decode()`.
- **Hex encode** (hex): `Array.from(bytes).map(b => b.toString(16).padStart(2, '0')).join('')`. Must match Python `bytes.hex()`.
- **Entropy**: `bits = length * Math.log2(charsetSize)`, rounded to integer.
- **Strength**: thresholds at 64, 128, 256 bits.

### Definition of Done

- [ ] All 4 generator functions produce correct output (cross-validated against Python equivalents)
- [ ] Chi-squared test passes for password distribution (p > 0.01)
- [ ] No `Math.random()` in any file
- [ ] 100% branch coverage on crypto library
- [ ] Library has zero React or DOM imports (pure TypeScript)

---

## 4. Sprint 3 — UI + Integration

**Goal**: React page at `/secret-generator` with full interactivity, i18n, responsive design, and accessibility.

### Files Touched

| File | Change |
|---|---|
| `src/frontend/src/pages/tools/SecretGeneratorPage.tsx` | **New**: page component |
| `src/frontend/src/components/tools/secret-generator/ModeTabs.tsx` | **New**: tab component (ARIA tabs pattern) |
| `src/frontend/src/components/tools/secret-generator/PasswordParams.tsx` | **New**: slider + 4 toggles |
| `src/frontend/src/components/tools/secret-generator/TokenParams.tsx` | **New**: slider |
| `src/frontend/src/components/tools/secret-generator/HexParams.tsx` | **New**: slider |
| `src/frontend/src/components/tools/secret-generator/SecretDisplay.tsx` | **New**: read-only field + Copy + Regenerate |
| `src/frontend/src/components/tools/secret-generator/StrengthIndicator.tsx` | **New**: badge + entropy line |
| `src/frontend/src/components/tools/secret-generator/ClipboardNotice.tsx` | **New**: auto-clear countdown or unavailable notice |
| `src/frontend/src/app/router.tsx` | Add `/secret-generator` route pointing to `SecretGeneratorPage` |
| `src/frontend/src/app/sidebar.tsx` | The tool already appears via `/tools`; no hardcoding needed if sidebar is tool-driven |
| `src/frontend/public/locales/fr.json` | Add all `tools.secret_generator.*` keys |
| `src/frontend/public/locales/en.json` | Add all `tools.secret_generator.*` keys |
| `src/frontend/src/hooks/useClipboard.ts` | **New** (or extend existing): `copyToClipboard` with 30 s auto-clear timer |

### Component Tree

```
SecretGeneratorPage
├── ModeTabs (radio group, ARIA tabs)
├── PasswordParams (conditional)
│   ├── Slider (length, 8–128)
│   ├── Toggle (uppercase)
│   ├── Toggle (lowercase)
│   ├── Toggle (digits)
│   └── Toggle (symbols)
├── TokenParams (conditional)
│   └── Slider (length, 16–256)
├── HexParams (conditional)
│   └── Slider (length, 16–512)
├── SecretDisplay
│   ├── <output> (read-only, monospace, aria-live)
│   ├── StrengthIndicator
│   │   ├── Icon + Label (color-coded)
│   │   └── Entropy ("N caractères (X bits)")
│   ├── CopyButton (conditional on clipboard availability)
│   └── RegenerateButton
└── ClipboardNotice (auto-clear countdown or unavailable message)
```

### States

| State | Trigger | Display |
|---|---|---|
| **Default** | Page load, Password mode | 20-char password, all toggles ON, strength displayed |
| **Loading** | N/A — no backend call. Instant generation. | No spinner needed. |
| **Generation** | Parameter change or Regenerate click | Brief pulse animation on secret field (disabled if `prefers-reduced-motion`) |
| **Copied** | Copy click | "Copied!" toast, 2 s → revert to "Copy" |
| **Clipboard unavailable** | `navigator.clipboard` absent | Copy button hidden, manual selection hint |
| **JS disabled** | `<noscript>` | Fallback message |
| **No charset** | All toggles OFF (UI prevents) | Error message in secret field |
| **Error** | CSPRNG unavailable (hypothetical) | Error banner |

### Definition of Done

- [ ] Page renders at `/secret-generator` on desktop and mobile
- [ ] Mode switching works (tabs + keyboard navigation)
- [ ] Parameter changes regenerate secrets immediately (debounced slider)
- [ ] Copy works and auto-clears after 30 s
- [ ] Regenerate produces a different secret
- [ ] Strength indicator updates correctly
- [ ] All i18n keys present in `fr.json` and `en.json`
- [ ] Responsive: 3 layouts (desktop, tablet, mobile)
- [ ] Accessibility: labels, focus order, `aria-live` announcements
- [ ] Existing sidebar correctly shows/hides the tool based on `/tools` response

---

## 5. Sprint 4 — QA + Hardening

**Goal**: End-to-end tests, accessibility audit, cross-browser testing, security validation.

### Files Touched

| File | Change |
|---|---|
| `tests/e2e/secret-generator.spec.ts` | **New**: Playwright tests covering all ACs from Sprint 3 |
| `tests/e2e/secret-generator-security.spec.ts` | **New**: network monitoring (no execute call), clipboard, console log assertions |
| `tests/unit/backend/test_secret_generator_405.py` | Extend: edge cases (OPTIONS, GET on execute endpoint) |

### E2E Test Scenarios (Playwright)

1. **Password mode happy path**: default params → verify 20 chars, all 4 sets represented, strength shown.
2. **Token mode happy path**: switch to Token → verify 43 chars, base64url alphabet, 258 bits.
3. **Hex mode happy path**: switch to Hex → verify 64 chars, lowercase hex, 256 bits.
4. **Parameter change regenerates**: change length → new secret within 200 ms.
5. **Regenerate**: click 5 times → 5 different secrets.
6. **Copy + auto-clear**: click Copy → paste into a test input → verify match. Wait 30 s → paste again → clipboard is empty.
7. **Clipboard unavailable**: mock `navigator.clipboard = undefined` → Copy hidden, hint visible.
8. **Last toggle protected**: turn off 3 toggles, attempt to turn off the 4th → snaps back.
9. **Mode switch resets params**: Password (length 20) → Token (default 43) → Password (back to 20).
10. **No backend call**: monitor network → no `POST .../execute` during any interaction.
11. **A11y audit**: keyboard navigation through all controls, screen reader announces secret.
12. **Responsive**: viewports 375px, 768px, 1200px → correct layout at each.

### Definition of Done

- [ ] All Playwright tests pass (Chromium, Firefox, WebKit)
- [ ] Network monitoring confirms zero `POST .../execute` calls
- [ ] Console log verification confirms no secret leakage
- [ ] Accessibility audit: keyboard + screen reader
- [ ] Cross-browser visual parity (Chromium, Firefox, Safari)
- [ ] All ACs (001–063) verifiable by automated test or manual QA checklist

---

## 6. Ordering & Dependencies

```
Sprint 0 (docs)
    │
    ▼
Sprint 1 (backend contract)
    │
    ├──▶ Sprint 2 (lib) ──▶ Sprint 3 (UI) ──▶ Sprint 4 (QA)
    │
    └──▶ No dependency: Sprint 2 can start in parallel with Sprint 1 review
```

- **Sprint 1** must complete first: the `/tools` response and 405 guard are prerequisites for frontend integration (Sprint 3).
- **Sprint 2** can start in parallel with Sprint 1 review: the crypto library is pure TypeScript with no backend dependency. Its tests run in isolation (Vitest + jsdom).
- **Sprint 3** depends on Sprint 1 (to test against real `/tools` response) and Sprint 2 (to import the library).
- **Sprint 4** depends on Sprint 3 (to have a working UI to test).

---

## 7. Files Summary

| Sprint | New Files | Modified Files |
|---|---|---|
| Sprint 1 | 3 (`secret_generator.py`, 2 test files) | 2 (`base.py`, `main.py`) |
| Sprint 2 | 7 (lib + 4 test files) | 0 |
| Sprint 3 | 11 (page, 5 components, 1 hook, 2 locale files, router, sidebar?) | 2–3 (router, sidebar, i18n audit) |
| Sprint 4 | 2 (e2e test files) | 0–1 (unit test extension) |
| **Total** | **23** | **4–6** |

No new dependencies. No migrations.

---

## 8. References

- `functional-spec.md` §3.7 — Functional requirements
- `docs/specs/technical/spec-tool-secret-generator.md` — Technical specification
- `docs/specs/ui-spec.md` SCR-28, §5.5, §12.3–12.4 — UI specification
- `docs/adr/ADR-017-frontend-only-tool-pattern.md` — Architectural decision
- `docs/qa/acceptance-secret-generator.md` — Acceptance criteria
- `docs/security/review-secret-generator.md` — Security review

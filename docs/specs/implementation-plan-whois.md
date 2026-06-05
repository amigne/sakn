# Implementation Plan — WHOIS Lookup Tool

> **Version:** 1.0
> **Status:** Draft — Sprint 0 (spec consolidation)
> **Date:** 2026-06-05
> **Module:** WHOIS Lookup (`whois`)
> **Issue:** #446
> **References:** `functional-spec.md` §3.6, `spec-tool-whois.md`, `ui-spec.md` SCR-27 §5.5, ADR-018, `docs/security/review-whois.md`, `docs/qa/acceptance-whois.md`

---

## 1. Sprint Overview

| Sprint | Scope | Duration (est.) | Dependencies |
|---|---|---|---|
| **Sprint 1** | Backend contract + RDAP/WHOIS execution | 3–4 days | None (new tool, no migration) |
| **Sprint 2** | WHOIS parsing, hardening, timeouts | 2–3 days | Sprint 1 |
| **Sprint 3** | Frontend UI (`/whois` page) | 2–3 days | Sprint 1 (API contract stable) |
| **Sprint 4** | QA, security verification, E2E | 1–2 days | Sprints 1–3 |

Total estimated: **8–12 days** (one developer, sequential). With parallel frontend/backend work: **6–8 days**.

---

## 2. Sprint 1 — Backend Contract + RDAP/WHOIS Execution

### 2.1 Goal

`WhoisLookupTool` registered, seeded, and executing RDAP queries with WHOIS fallback. SSRF protection integrated. All backend ACs passing (AC-WHOIS-001 → 011, 020 → 025, 030 → 034, 040 → 042, 050 → 059, 060 → 064, 070 → 073, 080 → 081).

### 2.2 Files Touched

| File | Change | Owner |
|---|---|---|
| `src/backend/app/tools/whois.py` | **New**: `WhoisLookupTool` class with `get_definition()`, `validate_params()`, `execute()`, RDAP client, WHOIS client, `sanitize_whois_target()`, response parsing stubs | Backend |
| `src/backend/app/main.py` | Add `from app.tools.whois import WhoisLookupTool` + `registry.register(WhoisLookupTool())` (~3 lines) | Backend |
| `src/backend/app/config.py` | Add `WHOIS_RDAP_CONNECT_TIMEOUT`, `WHOIS_RDAP_READ_TIMEOUT`, `WHOIS_WHOIS_CONNECT_TIMEOUT`, `WHOIS_WHOIS_READ_TIMEOUT`, `WHOIS_MAX_RESPONSE_BYTES` settings (~10 lines) | Backend |

### 2.3 Implementation Order

1. **`whois.py` skeleton**: `WhoisLookupTool` class, `get_definition()`, `validate_params()` → verify `GET /tools` includes `whois`.
2. **SSRF integration**: `execute()` → validate `target` via `filter_target()` → return `TARGET_NOT_ALLOWED` if blocked. Same for `server` if provided.
3. **RDAP client**: `_execute_rdap()` → IANA bootstrap → authoritative query → JSON parse → map to result fields. Return `protocol: "rdap"`.
4. **WHOIS client**: `_execute_whois()` → IANA reference query (if no custom server) → TCP connect → send query → read response → return `protocol: "whois"` + `raw_text`.
5. **Fallback logic**: `execute()` → try RDAP → if RDAP fails (404/no RDAP/connection error/timeout) → fall back to WHOIS.
6. **Custom server shortcut**: if `server` param provided → skip RDAP, go directly to `_execute_whois()` with the custom server.
7. **Timeout enforcement**: `asyncio.wait_for()` on each phase with configurable timeouts. Overall `asyncio.wait_for(execute_inner(), 60)`.
8. **Error mapping**: RDAP 404 → `not_found`. Connection/timeout errors → `WHOIS_CONNECTION_FAILED`. No IANA entry → `WHOIS_UNSUPPORTED_TLD`.
9. **Seed verification**: Boot the app → verify `ToolModule` and `RoleToolPermission` rows created. Boot again → verify idempotent (no duplicate rows).

### 2.4 Tests

| Test | Scope | ACs Covered |
|---|---|---|
| `test_whois_tool_definition` | Unit: `get_definition()` returns correct params | 001 |
| `test_whois_seed` | Integration: seed creates ToolModule + permissions | 002, 003 |
| `test_whois_admin_disable` | Integration: admin toggle removes from `/tools` | 004 |
| `test_whois_admin_permission` | Integration: role permission toggle | 005 |
| `test_whois_no_migration` | Integration: `alembic check` — no new migration | 007 |
| `test_whois_target_required` | Unit: missing `target` → 422 | 009 |
| `test_whois_target_max_length` | Unit: `target` > 255 chars → 422 | 010 |
| `test_whois_rdap_domain_success` | Integration: `example.com` → RDAP success with structured data | 020, 022 |
| `test_whois_rdap_ip_success` | Integration: `8.8.8.8` → RDAP success | 021 |
| `test_whois_rdap_not_found` | Integration: non-existent domain → `not_found` | 023 |
| `test_whois_rdap_gdpr_redaction` | Integration: GDPR domain → contact fields null | 024 |
| `test_whois_iana_bootstrap` | Unit: mock IANA response → correct server URL extracted | 025 |
| `test_whois_fallback_triggered` | Unit: mock RDAP failure → WHOIS called | 030 |
| `test_whois_iana_reference_query` | Unit: mock IANA WHOIS response → correct TLD server extracted | 032 |
| `test_whois_response_truncation` | Unit: mock large response → truncated flag | 034 |
| `test_whois_custom_server_skips_rdap` | Unit: `server` provided → RDAP not called | 040 |
| `test_whois_custom_server_unreachable` | Unit: mock connection refused → 502 | 042 |
| `test_whois_ssrf_private_target_ip` | Unit: `127.0.0.1` → `TARGET_NOT_ALLOWED` | 050 |
| `test_whois_ssrf_private_target_hostname` | Unit: `localhost` → `TARGET_NOT_ALLOWED` | 051 |
| `test_whois_ssrf_rfc1918_target` | Unit: `192.168.1.1` → `TARGET_NOT_ALLOWED` | 052 |
| `test_whois_ssrf_private_server` | Unit: `server=127.0.0.1` → `TARGET_NOT_ALLOWED` | 053 |
| `test_whois_ssrf_internal_hostname_server` | Unit: `server=metadata.google.internal` → blocked | 054 |
| `test_whois_ssrf_docker_bridge` | Unit: `172.17.0.2` → `TARGET_NOT_ALLOWED` | 055, 056 |
| `test_whois_ssrf_ipv6_loopback` | Unit: `::1` → `TARGET_NOT_ALLOWED` | 058 |
| `test_whois_ssrf_ipv6_ula` | Unit: `fd00::1` → `TARGET_NOT_ALLOWED` | 059 |
| `test_whois_unsupported_tld` | Unit: mock IANA bootstrap 404 → `WHOIS_UNSUPPORTED_TLD` | 060 |
| `test_whois_rdap_connect_timeout` | Unit: mock connect timeout → fallback to WHOIS | 061 |
| `test_whois_whois_connect_timeout` | Unit: mock connect timeout → 502 | 062 |
| `test_whois_execution_deadline` | Unit: mock slow responses → cancelled at 60s | 064 |
| `test_whois_protocol_injection` | Unit: `target=example.com\r\nQUIT\r\n` → sanitized | 065 |
| `test_whois_no_new_dependencies` | Integration: `uv pip list` diff → no additions | 080 |
| `test_whois_no_subprocess` | Code review: grep for `subprocess` → zero hits | 081 |

**Total: ~30 tests** (primarily unit tests with mocked network calls; 5–6 integration tests against real RDAP/WHOIS servers).

### 2.5 Definition of Done

- [ ] `WhoisLookupTool` class exists in `app/tools/whois.py`
- [ ] Registered in `main.py` (seed creates DB rows)
- [ ] `GET /tools` includes `whois` with correct parameters
- [ ] RDAP query succeeds for `example.com` (real integration test)
- [ ] RDAP query succeeds for `8.8.8.8` (real integration test)
- [ ] WHOIS fallback works for a TLD without RDAP
- [ ] Custom `server` parameter bypasses RDAP
- [ ] SSRF filter applied to `target`, `server`, and RDAP redirect targets
- [ ] All timeouts enforced (connect + read for both protocols)
- [ ] Response size cap enforced for WHOIS TCP reads
- [ ] `WHOIS_UNSUPPORTED_TLD` returned for undiscoverable TLDs
- [ ] `WHOIS_CONNECTION_FAILED` returned for connection failures
- [ ] Domain not found returns `success: false` with `not_found: true`
- [ ] All ~30 tests pass (unit + integration)
- [ ] No new migration generated (`alembic check`)
- [ ] No new PyPI dependencies (`uv pip list` diff)
- [ ] Backend ruff → all checks passed
- [ ] Backend pytest (full suite from `src/backend/`) → all passed (note: CI doesn't run pytest; full suite must pass including new WHOIS tests)

---

## 3. Sprint 2 — WHOIS Parsing, Hardening, Timeouts

### 3.1 Goal

Best-effort WHOIS text parsing, RDAP redirect validation, truncation handling, timeout edge cases, error message refinement. All remaining backend ACs passing.

### 3.2 Files Touched

| File | Change | Owner |
|---|---|---|
| `src/backend/app/tools/whois.py` | Add `_parse_whois_text()`, `_parse_rdap_json()`, `_validate_redirect()`, `TargetSanitizer` | Backend |
| `src/backend/tests/test_whois_parsing.py` | **New**: Unit tests for WHOIS text parser (various registry formats) | Backend |
| `src/backend/tests/test_whois_redirect.py` | **New**: Unit tests for RDAP redirect validation | Backend |

### 3.3 Implementation Order

1. **WHOIS text parser**: `_parse_whois_text(raw: str) -> dict` — regex-based extraction of domain, registrar, dates, statuses, nameservers. Handle thin registries (missing contact data). Handle multiple status lines. Handle date format variations (ISO 8601, `DD-Mon-YYYY`, `Month DD, YYYY`).
2. **RDAP redirect validation**: `_validate_redirect(url: str) -> bool` — extract hostname, resolve, `filter_target()`, return True if safe to follow.
3. **Truncation handling**: byte counter in WHOIS read loop, compare against `settings.WHOIS_MAX_RESPONSE_BYTES`, set `truncated: true` and close connection when exceeded.
4. **Target sanitizer**: `sanitize_whois_target(target: str) -> str` — strip `\r`, `\n`, control chars < 0x20. Reject empty result.
5. **Refine RDAP JSON parser**: handle edge cases (missing `events`, missing `entities`, nested `vcardArray` variations, multi-valued fields).

### 3.4 Tests

| Test | Scope | ACs Covered |
|---|---|---|
| `test_parse_whois_verisign` | Unit: Verisign `.com` WHOIS format → structured fields | 033 |
| `test_parse_whois_arin` | Unit: ARIN IP WHOIS format → structured fields | — |
| `test_parse_whois_ripe` | Unit: RIPE IP WHOIS format → structured fields | — |
| `test_parse_whois_thin_registry` | Unit: Thin registry → null contacts, populated statuses | 033 |
| `test_parse_whois_no_dates` | Unit: Response without date fields → null dates | — |
| `test_parse_whois_multiple_statuses` | Unit: Response with 5+ status lines → all extracted | — |
| `test_parse_whois_empty_response` | Unit: Empty response → all fields null, raw_text populated | — |
| `test_rdap_redirect_validation_public` | Unit: Redirect to public IP → allowed | 057 |
| `test_rdap_redirect_validation_private` | Unit: Redirect to `10.0.0.1` → blocked | 057 |
| `test_rdap_redirect_loop` | Unit: 4 redirects → 4th blocked | 067 |
| `test_target_sanitizer_strips_crlf` | Unit: `example.com\r\nQUIT\r\n` → `example.com` | 065 |
| `test_target_sanitizer_empty_result` | Unit: `\r\n` → ValueError | 066 |
| `test_whois_truncation` | Unit: 3 MiB mock response, 2 MiB cap → truncated at 2 MiB | 034 |

### 3.5 Definition of Done

- [ ] WHOIS parser handles ≥ 3 registry formats (Verisign, ARIN, RIPE)
- [ ] RDAP redirect validation re-checks `filter_target()` before following
- [ ] Response size cap triggers at configured byte limit
- [ ] Target sanitizer prevents WHOIS protocol injection
- [ ] All parsing edge cases covered by unit tests (~12 tests)
- [ ] Backend tests pass (full suite)

---

## 4. Sprint 3 — Frontend UI

### 4.1 Goal

Fully functional `/whois` page: parameters panel, result display (RDAP and WHOIS), error states, loading state, copy button, responsive layout, i18n, a11y. All UI ACs passing (AC-WHOIS-100 → 111, 120 → 122, 130 → 134).

### 4.2 Files Touched

| File | Change | Owner |
|---|---|---|
| `src/frontend/src/app/whois/page.tsx` | **New**: WHOIS page component (server component wrapper) | Frontend |
| `src/frontend/src/components/tools/whois/WhoisForm.tsx` | **New**: Parameters form (Target, Advanced toggle, WHOIS Server, Start, Reset) | Frontend |
| `src/frontend/src/components/tools/whois/WhoisOutput.tsx` | **New**: Result display (protocol badge, structured fields, raw text, Copy) | Frontend |
| `src/frontend/src/components/tools/whois/WhoisLoading.tsx` | **New**: Loading state with elapsed time and protocol attempt indicator | Frontend |
| `src/frontend/src/components/tools/whois/WhoisError.tsx` | **New**: Error banners for all error states | Frontend |
| `src/frontend/src/hooks/useWhois.ts` | **New**: Hook for `POST /tools/whois/execute` with loading/error/result state | Frontend |
| `src/frontend/src/locales/en/tools.json` | Verify all 24 `tools.whois.*` keys exist | Frontend |
| `src/frontend/src/locales/fr/tools.json` | Verify all 24 `tools.whois.*` keys exist | Frontend |

### 4.3 Implementation Order

1. **WHOIS hook** (`useWhois.ts`): `executeWhois(target, server?)` → `POST /api/v1/tools/whois/execute` → returns `{data, error, loading}`.
2. **WHOIS form** (`WhoisForm.tsx`): Target input (required), Advanced toggle (collapsed), WHOIS Server input (optional), Start button, Reset button. Enter triggers Start. Disabled during loading.
3. **WHOIS output** (`WhoisOutput.tsx`): Protocol badge, structured fields (label: value, null fields hidden or `[REDACTED]`), raw text block (collapsible, monospace, scrollable), Copy button.
4. **WHOIS loading** (`WhoisLoading.tsx`): Spinner + "Looking up..." + elapsed time + protocol attempt indicator ("Trying RDAP…" → "Falling back to WHOIS…").
5. **WHOIS error** (`WhoisError.tsx`): Error banners for `TARGET_NOT_ALLOWED`, `WHOIS_UNSUPPORTED_TLD`, `WHOIS_CONNECTION_FAILED`, domain not found, truncation warning, network error.
6. **WHOIS page** (`page.tsx`): Compose form + output/loading/error based on state.
7. **i18n verification**: Confirm all 26 WHOIS keys exist in `en.json` and `fr.json`.
8. **Responsive**: Desktop two-panel, mobile single-column. Test at 375px, 768px, 1024px, 1200px.
9. **a11y**: Labels, `aria-live` regions, focus order, keyboard navigation for raw text block.

### 4.4 Tests

| Test | Scope | ACs Covered |
|---|---|---|
| `WhoisPage.render` | Vitest: page renders with form and empty output | 100 |
| `WhoisForm.submit` | Vitest: valid target → execute called | 101 |
| `WhoisOutput.rdap` | Vitest: mock RDAP result → structured fields rendered | 102 |
| `WhoisOutput.whois` | Vitest: mock WHOIS result → raw text block rendered | 103 |
| `WhoisOutput.copy` | Vitest: copy button → clipboard written | 104 |
| `WhoisForm.advanced` | Vitest: Advanced toggle → WHOIS Server field revealed | 105 |
| `WhoisOutput.notFound` | Vitest: `not_found` → warning banner | 106 |
| `WhoisError.unsupportedTld` | Vitest: `WHOIS_UNSUPPORTED_TLD` → error banner | 107 |
| `WhoisError.connectionFailed` | Vitest: `WHOIS_CONNECTION_FAILED` → error banner | 108 |
| `WhoisOutput.truncation` | Vitest: `truncated: true` → warning banner | 109 |
| `Whois.i18n.fr` | Vitest: French locale → French labels | 120 |
| `Whois.i18n.en` | Vitest: English locale → English labels | 121 |
| `Whois.accessibility` | Vitest: labels, aria-live, focus order | 130–134 |

### 4.5 Definition of Done

- [ ] `/whois` page renders with form + empty output panel
- [ ] Start button triggers execution and shows loading state
- [ ] RDAP result displays structured fields with blue "RDAP" badge
- [ ] WHOIS result displays structured fields + raw text with yellow "WHOIS" badge
- [ ] Copy button works for both RDAP and WHOIS results
- [ ] Advanced toggle reveals/hides WHOIS Server field
- [ ] Domain not found displays yellow warning
- [ ] All error banners render correctly
- [ ] Truncation warning displayed when applicable
- [ ] Responsive at desktop, tablet, and mobile breakpoints
- [ ] All i18n keys present in both locales
- [ ] All a11y requirements met (labels, aria-live, focus order)
- [ ] Frontend vitest → all WHOIS tests pass
- [ ] Frontend tsc → no errors
- [ ] Frontend biome → no issues

---

## 5. Sprint 4 — QA, Security Verification, E2E

### 5.1 Goal

Full acceptance test pass, security verification, E2E testing, regression check. All 70 ACs verified.

### 5.2 Files Touched

| File | Change | Owner |
|---|---|---|
| `src/frontend/e2e/whois.spec.ts` | **New**: Playwright E2E tests for WHOIS page | Frontend |
| `docs/qa/acceptance-whois.md` | Update with Sprint 1–3 test results | QA |

### 5.3 Tasks

1. **Backend AC verification**: Run all Sprint 1–2 tests. Verify all backend ACs pass.
2. **Frontend AC verification**: Run all Sprint 3 tests. Verify all UI ACs pass.
3. **E2E tests**: Playwright tests covering:
   - WHOIS page loads → enter domain → click Start → RDAP result displayed
   - WHOIS with custom server → WHOIS result displayed
   - Error states: private target blocked, unsupported TLD, domain not found
   - Copy button → clipboard populated
   - Mobile viewport → layout stacks correctly
   - Keyboard navigation → focus order correct
4. **Security verification checklist** (from `docs/security/review-whois.md` §4):
   - [ ] `target` validated through `filter_target()` before any connection
   - [ ] `server` validated through `filter_target()` before WHOIS connection
   - [ ] RDAP redirects intercepted and re-validated
   - [ ] Connections use validated IP (resolve-then-connect)
   - [ ] WHOIS response size cap enforced
   - [ ] `target` sanitized before WHOIS socket write
   - [ ] Rate limiting applied
   - [ ] Error responses use generic i18n keys
   - [ ] No new dependencies
   - [ ] No new migration
   - [ ] All timeouts enforced
5. **Non-regression**: Run full backend pytest suite (including existing tests for other tools), full frontend vitest suite, ruff, biome, tsc.
6. **Documentation**: Update `acceptance-whois.md` with Sprint 4 QA results.

### 5.4 Definition of Done

- [ ] All 70 ACs verified (PASS or documented deviation)
- [ ] E2E tests passing (Playwright)
- [ ] Security checklist fully ticked
- [ ] Full backend test suite passing (no regressions)
- [ ] Full frontend test suite passing (no regressions)
- [ ] Ruff / biome / tsc clean
- [ ] QA report in `acceptance-whois.md` updated
- [ ] Any deviations filed as follow-up issues

---

## 6. File Manifest (Complete)

### New Files

| File | Sprint | Purpose |
|---|---|---|
| `src/backend/app/tools/whois.py` | 1 | `WhoisLookupTool` class (definition + execute + RDAP/WHOIS clients + parser) |
| `src/backend/tests/test_whois_tool.py` | 1 | Unit + integration tests for backend |
| `src/backend/tests/test_whois_parsing.py` | 2 | Unit tests for WHOIS text parser |
| `src/backend/tests/test_whois_redirect.py` | 2 | Unit tests for RDAP redirect validation |
| `src/frontend/src/app/whois/page.tsx` | 3 | WHOIS page component |
| `src/frontend/src/components/tools/whois/WhoisForm.tsx` | 3 | Parameters form |
| `src/frontend/src/components/tools/whois/WhoisOutput.tsx` | 3 | Result display |
| `src/frontend/src/components/tools/whois/WhoisLoading.tsx` | 3 | Loading state |
| `src/frontend/src/components/tools/whois/WhoisError.tsx` | 3 | Error banners |
| `src/frontend/src/hooks/useWhois.ts` | 3 | WHOIS execution hook |
| `src/frontend/e2e/whois.spec.ts` | 4 | E2E tests |

### Modified Files

| File | Sprint | Change |
|---|---|---|
| `src/backend/app/main.py` | 1 | Register `WhoisLookupTool` (~3 lines) |
| `src/backend/app/config.py` | 1 | Add WHOIS settings (~10 lines) |

### No-Change Files (Verified)

| File | Reason |
|---|---|
| `src/backend/app/models/tool_module.py` | No schema change — reuse `ToolModule` table |
| `src/backend/app/models/role_tool_permission.py` | No schema change — reuse `RoleToolPermission` table |
| `src/backend/alembic/versions/` | No migration needed |
| `src/backend/pyproject.toml` | No new dependencies |
| `src/frontend/src/locales/en/tools.json` | All 24 `tools.whois.*` keys pre-existing |
| `src/frontend/src/locales/fr/tools.json` | All 24 `tools.whois.*` keys pre-existing |
| `src/frontend/src/locales/en/errors.json` | All 2 `errors.whois_*` keys pre-existing |
| `src/frontend/src/locales/fr/errors.json` | All 2 `errors.whois_*` keys pre-existing |

---

## 7. Risk Register

| Risk | Severity | Likelihood | Mitigation |
|---|---|---|---|
| IANA bootstrap service unreachable during testing | Low | Low | Mock IANA responses in unit tests. Real integration tests are best-effort (skip if IANA is down). |
| RDAP server changes break JSON parsing | Medium | Low | Parsing is defensive: all fields nullable, unknown fields ignored. Raw text always available from WHOIS fallback. |
| WHOIS parsing fails for unusual registry formats | Medium | Medium | Best-effort parsing — always return `raw_text`. Users can read the raw text for unusual formats. Follow-up issues for format-specific improvements. |
| SSRF bypass via IPv6-mapped IPv4 (`::ffff:127.0.0.1`) | High | Very Low | Covered by `BLOCKED_NETWORKS` in `address_filter.py` (includes `::ffff:0:0/96`). |
| SSRF bypass via DNS rebinding against `filter_target()` | High | Very Low | `filter_target()` has its own TOCTOU hardening (CNAME chain walking, resolve-then-check). The WHOIS tool uses the validated IP, not the hostname, for connections. |
| Rate limiting on remote WHOIS servers causes timeouts | Low | Medium | Timeouts are generous (15–20s). Rate-limited servers typically return a text response, not a timeout. If timeouts become common, add retry with backoff (future enhancement). |

---

## 8. References

| Source | Sections |
|---|---|
| `functional-spec.md` | §3.6 (WHOIS Lookup) |
| `spec-tool-whois.md` | Full technical specification |
| `ui-spec.md` | SCR-27, §5.5 |
| `spec-api-contract.md` | §6 (Tools), §9 (error codes), §10.3 (i18n keys) |
| `docs/adr/ADR-018-whois-resolution-and-ssrf-policy.md` | Architecture decision |
| `docs/security/review-whois.md` | Security review |
| `docs/qa/acceptance-whois.md` | Acceptance criteria |
| `app/security/address_filter.py` | `filter_target()` implementation |
| `app/tools/ssl_viewer.py:96` | SSRF filter usage pattern |
| `app/tools/base.py` | `BaseTool`, `ToolDefinition`, `ToolParameter` |
| `app/main.py:90-147` | Registry + seed pattern |

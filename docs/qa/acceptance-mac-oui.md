# Acceptance Criteria — MAC OUI Lookup

> **Version:** 0.2.0 (révision Sprint 0 post-revue)
> **Status:** Draft — pending review
> **Date:** 2026-05-31
> **Module:** MAC OUI Lookup (`mac_oui`)
> **References:** `functional-spec.md` §3.5, `spec-tools-instant.md` §4, `spec-backend.md` §4.2/§9.6, `spec-api-contract.md` §9-10, `spec-frontend.md` §4.1, `ui-spec.md` SCR-26, ADR-013, ADR-014

> **Architecture rappel** : le frontend extrait, normalise et envoie une liste d'OUI/MAC déjà formatée au backend. Le backend revalide en zero-trust, fait un lookup pur, retourne 200 OK avec résultats partiels et entrées rejetées (sanitisées). 422 réservé au JSON malformé. Voir ADR-014 §2.

---

## 1. Extraction côté frontend (formats acceptés)

### AC-MAC-OUI-001 — MAC colon-separated (6 octets)

**Given** the textarea contains `00:11:22:33:44:55`
**When** the user clicks Execute
**Then** the frontend extracts `001122334455`, normalizes to bare hex uppercase, and includes it in the API request payload

### AC-MAC-OUI-002 — MAC hyphen-separated (6 octets)

**Given** the textarea contains `00-11-22-33-44-55`
**When** the user clicks Execute
**Then** the frontend extracts `001122334455` (same normalization)

### AC-MAC-OUI-003 — MAC Cisco dot-separated (3 groups of 4)

**Given** the textarea contains `0011.2233.4455`
**When** the user clicks Execute
**Then** the frontend extracts `001122334455`

### AC-MAC-OUI-004 — MAC bare hex (12 digits, isolated)

**Given** the textarea contains `001122334455` surrounded by whitespace
**When** the user clicks Execute
**Then** the frontend extracts `001122334455`

### AC-MAC-OUI-005 — MAC bare hex (12 digits) NOT isolated

**Given** the textarea contains `abc001122334455def` (no word boundary)
**When** the user clicks Execute
**Then** the frontend does NOT extract `001122334455` (the `\b` boundary blocks the match)

### AC-MAC-OUI-006 — OUI 3 octets colon-separated

**Given** the textarea contains `00:11:22`
**When** the user clicks Execute
**Then** the frontend extracts `001122` (6 hex digits, MA-L candidate)

### AC-MAC-OUI-007 — OUI 3 octets hyphen-separated

**Given** the textarea contains `00-11-22`
**When** the user clicks Execute
**Then** the frontend extracts `001122` (accepted format, tolerant policy)

### AC-MAC-OUI-008 — OUI 3 octets Cisco 2-group

**Given** the textarea contains `0011.22`
**When** the user clicks Execute
**Then** the frontend extracts `001122`

### AC-MAC-OUI-009 — OUI 3 octets bare hex

**Given** the textarea contains `001122` isolated by word boundaries
**When** the user clicks Execute
**Then** the frontend extracts `001122`

### AC-MAC-OUI-010 — OUI MA-M (7 hex digits, all separators)

**Given** the textarea contains `00:11:22:3`, `00-11-22-3`, `0011223`
**When** the user clicks Execute
**Then** the frontend extracts `0011223` for each variant

### AC-MAC-OUI-011 — OUI MA-S (9 hex digits, all separators)

**Given** the textarea contains `00:11:22:33:4`, `0011.2233.4`, `001122334`
**When** the user clicks Execute
**Then** the frontend extracts `001122334` for each variant

### AC-MAC-OUI-012 — Mixed separators in same input

**Given** the textarea contains `00:11:22:33:44:55` and `aa-bb-cc-dd-ee-ff` and `0011.2233.4455`
**When** the user clicks Execute
**Then** all three are extracted and normalized: `001122334455`, `AABBCCDDEEFF`, `001122334455` (the last two of these are deduplicated to a single entry — see §3)

### AC-MAC-OUI-013 — Case insensitivity

**Given** the textarea contains `0a:1b:2c:3d:4e:5f` and `0A:1B:2C:3D:4E:5F`
**When** the user clicks Execute
**Then** both are normalized to `0A1B2C3D4E5F` (uppercase) and deduplicated

### AC-MAC-OUI-014 — Realistic ARP table paste

**Given** the textarea contains:
```
Internet  10.0.0.1   0   00:11:22:33:44:55   ARPA   Vlan10
Internet  10.0.0.2   0   00-11-22-33-44-AA   ARPA   Vlan10
```
**When** the user clicks Execute
**Then** the frontend extracts `001122334455` and `00112233 44AA`, both share the same OUI MA-L prefix `001122`

### AC-MAC-OUI-015 — Realistic Cisco config paste

**Given** the textarea contains `interface FastEthernet0/1\n mac-address 0011.2233.4455`
**When** the user clicks Execute
**Then** the frontend extracts `001122334455`

### AC-MAC-OUI-016 — Non-hex text ignored

**Given** the textarea contains `Server alpha-1 has IP 192.168.1.42 and runs ubuntu`
**When** the user clicks Execute
**Then** the frontend extracts nothing; the result is an empty list

### AC-MAC-OUI-017 — UUID NOT matched

**Given** the textarea contains `550e8400-e29b-41d4-a716-446655440000`
**When** the user clicks Execute
**Then** the frontend extracts nothing (UUID groups are 8-4-4-4-12, not 2-2-2-2-2-2)

### AC-MAC-OUI-018 — Date ISO NOT matched as hyphen OUI

**Given** the textarea contains `2026-05-31`
**When** the user clicks Execute
**Then** the frontend extracts nothing (groups are 4-2-2, not 2-2-2)

### AC-MAC-OUI-019 — Timestamp HH:MM:SS — accepted as false positive

**Given** the textarea contains `12:34:56` (looks like a timestamp)
**When** the user clicks Execute
**Then** the frontend extracts `123456` (OUI 3 octets) — this is an accepted false positive per ADR-014 §2.2 (recall > precision). The backend lookup will likely return "Unknown vendor".

### AC-MAC-OUI-020 — Length normalization to valid IEEE sizes

**Given** the frontend extracts a pattern that normalizes to 8 hex digits (e.g., `deadbeef`)
**When** normalization runs
**Then** the entry is **silently dropped** (length 8 not in {6, 7, 9, 12}); not sent to backend

---

## 2. Frontend normalization

### AC-MAC-OUI-021 — Strip separators

**Given** the frontend extracted `00:11:22:33:44:55`
**When** normalization runs
**Then** the output is `001122334455` (no separator)

### AC-MAC-OUI-022 — Convert to uppercase

**Given** the frontend extracted `ab:cd:ef`
**When** normalization runs
**Then** the output is `ABCDEF`

### AC-MAC-OUI-023 — Reject invalid characters

**Given** the frontend (via a hypothetical extraction artifact) produced `00112G` (`G` not hex)
**When** normalization runs
**Then** the entry is silently dropped before submission

### AC-MAC-OUI-024 — Send sorted unique list to backend

**Given** the frontend normalized 5 entries with 1 duplicate
**When** the API request is built
**Then** the request body is `{ "ouis": [...] }` with 4 unique entries

---

## 3. Frontend deduplication

### AC-MAC-OUI-025 — Exact duplicates

**Given** the textarea contains `00:11:22:33:44:55` twice
**When** the user clicks Execute
**Then** one unique entry `001122334455` is sent to backend

### AC-MAC-OUI-026 — Same MAC, different separators

**Given** the textarea contains `00:11:22:33:44:55` and `00-11-22-33-44-55` and `0011.2233.4455`
**When** the user clicks Execute
**Then** one unique entry `001122334455` is sent (all 3 normalize to the same value)

### AC-MAC-OUI-027 — Same OUI extracted twice via different MACs

**Given** the textarea contains `00:11:22:33:44:55` and `00:11:22:33:44:66`
**When** the user clicks Execute
**Then** two entries are sent to backend; the backend's longest-prefix lookup returns the same MA-L vendor for both. UI displays both rows.

---

## 4. Backend validation (zero-trust)

### AC-MAC-OUI-028 — Valid JSON, all entries valid

**Given** the API receives `{"ouis": ["001122", "112233445566"]}`
**When** the backend validates and looks up
**Then** the response is 200 OK with `results` array of 2 entries, `rejected` empty

### AC-MAC-OUI-029 — Valid JSON, one invalid entry

**Given** the API receives `{"ouis": ["001122", "test"]}`
**When** the backend validates
**Then** the response is 200 OK with `results` of 1 entry (`001122`), `rejected` listing index 2 with `reason="invalid_format"` and a sanitized `sample`

### AC-MAC-OUI-030 — Malformed JSON

**Given** the API receives a body that is not valid JSON
**When** the backend parses
**Then** the response is 422 with `VALIDATION_ERROR`

### AC-MAC-OUI-031 — Missing `ouis` field

**Given** the API receives `{}` (no `ouis` key)
**When** the backend validates
**Then** the response is 422 with `VALIDATION_ERROR`

### AC-MAC-OUI-032 — `ouis` field is not an array

**Given** the API receives `{"ouis": "001122"}` (string instead of array)
**When** the backend validates
**Then** the response is 422 with `VALIDATION_ERROR`

### AC-MAC-OUI-033 — Length invalid (8 digits)

**Given** the API receives `{"ouis": ["deadbeef"]}`
**When** the backend validates
**Then** the response is 200 OK with `results=[]` and `rejected=[{"index":1, "sample":"DEADBEEF", "reason":"invalid_length"}]`

### AC-MAC-OUI-034 — Non-hex characters

**Given** the API receives `{"ouis": ["001G22"]}`
**When** the backend validates
**Then** the response is 200 OK with `rejected=[{"index":1, "sample":"001G22", "reason":"non_hex_characters"}]`

### AC-MAC-OUI-035 — Empty `ouis` list

**Given** the API receives `{"ouis": []}`
**When** the backend processes
**Then** the response is 200 OK with `results=[]` and `rejected=[]`

### AC-MAC-OUI-036 — Backend batch size exceeded

**Given** the admin setting `MAC_OUI_BACKEND_BATCH_MAX_SIZE` is set to 2000
**And** the API receives `{"ouis": [... 2001 entries ...]}`
**When** the backend validates
**Then** the response is 422 with error code `MAC_OUI_TOO_MANY_INPUTS`

---

## 5. Security: bounded echo

### AC-MAC-OUI-037 — XSS payload sanitization

**Given** the API receives `{"ouis": ["<script>alert(1)</script>"]}`
**When** the backend validates
**Then** `rejected[0].sample` is `<script>alert(1)??` (truncated to 20 chars) and special chars replaced by `?`. **The original payload is never echoed.**

### AC-MAC-OUI-038 — Echo length cap

**Given** the API receives an invalid entry of 200 characters
**When** the backend sanitizes the echo
**Then** `rejected[i].sample` is at most 20 characters

### AC-MAC-OUI-039 — Echo charset filter

**Given** the API receives an entry with mixed characters: `00:11;22\nhello`
**When** the backend sanitizes the echo
**Then** characters outside `[0-9a-fA-F:.\-]` are replaced by `?`

### AC-MAC-OUI-040 — Frontend escapes echo

**Given** the API returns a `rejected[]` array with sanitized `sample` values
**When** the frontend renders the rejection notice
**Then** React's default escaping applies (no `dangerouslySetInnerHTML`). Test with a sample containing literal `<` and `>` chars to confirm rendering as text.

---

## 6. Lookup IEEE

### AC-MAC-OUI-041 — MA-L hit

**Given** the OUI `001122` exists in `mac_oui` with `oui_type='MA-L'`
**When** the backend looks up `001122`
**Then** the response includes `organization`, `address`, `oui_type="MA-L"`, `first_seen`, `last_seen`

### AC-MAC-OUI-042 — MA-M hit (7 digits)

**Given** the OUI `0011223` exists in `mac_oui` with `oui_type='MA-M'`
**When** the backend looks up `0011223`
**Then** the response includes `oui_type="MA-M"` and the corresponding organization

### AC-MAC-OUI-043 — MA-S hit (9 digits)

**Given** the OUI `001122334` exists in `mac_oui` with `oui_type='MA-S'`
**When** the backend looks up `001122334`
**Then** the response includes `oui_type="MA-S"`

### AC-MAC-OUI-044 — Longest prefix wins (MAC complète couvre MA-L et MA-M)

**Given** the MAC `001122334455`:
- `001122` exists in MA-L (organization = IEEE Registration Authority)
- `0011223` exists in MA-M (organization = Acme Corp)

**When** the backend looks up this MAC
**Then** the result is Acme Corp (MA-M, longest prefix) — not IEEE Registration Authority

### AC-MAC-OUI-045 — Longest prefix wins (MAC complète couvre MA-M et MA-S)

**Given** the MAC `001122334455`:
- `001122` in MA-L, `0011223` in MA-M, `001122334` in MA-S

**When** the backend looks up this MAC
**Then** the result is the MA-S entry (longest prefix)

### AC-MAC-OUI-046 — Unknown OUI

**Given** the OUI `FFEEDD` does not exist in `mac_oui`
**When** the backend looks up `FFEEDD`
**Then** the response entry has `result=null` and the frontend displays "Unknown vendor" (i18n `tools.mac_oui.unknown_vendor`)

### AC-MAC-OUI-047 — Ambiguous partial OUI (MA-L pool block)

**Given** the OUI `8C1F64` exists in MA-L with `organization="IEEE Registration Authority"`
**And** multiple MA-M entries exist with prefix starting `8C1F64...`
**When** the user submits only `8C:1F:64` (no full MAC)
**Then** the response entry includes:
- `result` populated with the IEEE Registration Authority data
- `ambiguous_extends_ma_m: true`
- `ambiguous_extends_ma_s` (true or false depending on actual data)

**And** the frontend displays this row in orange (token `--color-warning`) with the hint `tools.mac_oui.ambiguous_partial_oui`

### AC-MAC-OUI-048 — Single SELECT, no N+1

**Given** the API receives `{"ouis": [... 100 unique entries ...]}`
**When** the backend performs lookups
**Then** a single `SELECT * FROM mac_oui WHERE (oui, oui_type) IN ((...), ...)` is issued (or equivalent batched query). No per-entry round-trip.

---

## 7. Historique des changements

### AC-MAC-OUI-049 — OUI without history

**Given** OUI `001122` has no entries in `mac_oui_history`
**When** the backend returns the result
**Then** the entry's `history` field is `[]` (empty array, not null, not absent)

### AC-MAC-OUI-050 — Name change

**Given** OUI `001122` had `MacOuiHistory` row with `previous_organization="Cisco Systems, Inc."`, `new_organization="Cisco Systems, LLC"`, `change_type="name_change"`
**When** the user expands the history for this OUI
**Then** the entry is displayed with the labels (FR/EN per i18n) and the `detected_at` date

### AC-MAC-OUI-051 — Name + address change classified as name_change

**Given** OUI `001122` simultaneously changed `organization` (Aruba → HPE) and `address` (San Jose → Houston)
**When** the daily sync detects this
**Then** a single `MacOuiHistory` row is inserted with `change_type="name_change"`, all 4 fields populated (`previous_organization`, `new_organization`, `previous_address`, `new_address`)
**And** the frontend displays both diffs (name + address)

### AC-MAC-OUI-052 — Address-only change

**Given** OUI `001122` kept its organization name but changed address
**When** the daily sync detects this
**Then** a `MacOuiHistory` row is inserted with `change_type="address_change"`, `previous_organization == new_organization`, `previous_address != new_address`

### AC-MAC-OUI-053 — Revoked OUI

**Given** OUI `001122` was present in MA-L but the IEEE file now lists it with organization `"----"` or containing `revoked`
**When** the daily sync detects this
**Then** a `MacOuiHistory` row is inserted with `change_type="revoked"`. The `MacOui.organization` is updated to the IEEE file value.

### AC-MAC-OUI-054 — Multiple historical entries, chronological order

**Given** OUI `001122` has 3 `MacOuiHistory` rows: name change on 2026-01-15, address change on 2026-03-10, name change on 2026-05-20
**When** the user expands history
**Then** entries are loaded in ascending chronological order (oldest first)

### AC-MAC-OUI-055 — History pagination (lazy load)

**Given** OUI `001122` has 47 history entries
**And** the admin setting `MAC_OUI_HISTORY_PAGE_SIZE` is set to 10
**When** the user expands the history section
**Then** the first 10 entries are fetched and displayed
**And** scrolling to the bottom of the expanded section triggers loading the next 10 (infinite scroll pattern)
**And** the loading indicator appears between fetches

### AC-MAC-OUI-056 — History pagination endpoint

**Given** the API endpoint `GET /api/v1/tools/mac_oui/history?oui=001122&oui_type=MA-L&offset=0&limit=10` is called
**When** there are 47 entries
**Then** the response includes the first 10 entries plus `total: 47`, `has_more: true`

### AC-MAC-OUI-057 — History collection start date header

**Given** the module was deployed (first sync executed) on 2026-04-01
**When** the user expands any OUI's history
**Then** the section header reads `tools.mac_oui.history_since` (FR: « Historique collecté depuis le 01/04/2026 », EN: "History collected since 2026-04-01")

---

## 8. Sortie API

### AC-MAC-OUI-058 — Success response envelope

**Given** the tool executes successfully
**When** the API responds
**Then** the response is HTTP 200 with the standard envelope (per `spec-tools-instant.md` §1.2): `{"tool": "mac_oui", "success": true, "duration_ms": <number>, "data": {...}}`

### AC-MAC-OUI-059 — Parse stats structure

**Given** the request sent 3 entries (2 valid, 1 invalid; 1 of the valid was a duplicate already in the set)
**When** the API responds
**Then** `data.parse_stats` contains `total_inputs: 3, valid: 2, rejected: 1, unique: 2`

### AC-MAC-OUI-060 — OUI display format MA-L

**Given** a lookup result with `oui="001122"`, `oui_type="MA-L"`
**When** the response is built
**Then** `oui_display` field is `"00:11:22"` (uppercase, colon-separated)

### AC-MAC-OUI-061 — OUI display format MA-M

**Given** a lookup result with `oui="0011223"`, `oui_type="MA-M"`
**When** the response is built
**Then** `oui_display` field is `"00:11:22:3_"` (last group: 1 digit + underscore wildcard, per ADR-014 §2.5)

### AC-MAC-OUI-062 — OUI display format MA-S

**Given** a lookup result with `oui="001122334"`, `oui_type="MA-S"`
**When** the response is built
**Then** `oui_display` field is `"00:11:22:33:4_"`

### AC-MAC-OUI-063 — `history` array always present

**Given** any lookup result
**When** the API responds
**Then** each entry in `results[]` has a `history` field (empty array if no history)

---

## 9. UI / Affichage

### AC-MAC-OUI-064 — Underscore styled as wildcard placeholder

**Given** the result table displays a MA-M or MA-S `oui_display` containing `_`
**When** the row is rendered
**Then** the `_` character is styled with `color: var(--color-text-secondary)` (greyed)
**And** a tooltip appears on hover: `tools.mac_oui.tooltip_wildcard_digit` (« Ce digit varie selon l'équipement »)

### AC-MAC-OUI-065 — Legend below the result table

**Given** at least one result row has `oui_type` in `{MA-M, MA-S}`
**When** the table is rendered
**Then** a small caption below the table displays the legend i18n key `tools.mac_oui.legend_partial_byte`

### AC-MAC-OUI-066 — Ambiguous OUI highlighted

**Given** a result entry has `ambiguous_extends_ma_m=true` OR `ambiguous_extends_ma_s=true`
**When** the row is rendered
**Then** the row background uses `var(--color-warning-soft)` (orange-tinted) and the hint icon displays the message `tools.mac_oui.ambiguous_partial_oui` on hover/click

### AC-MAC-OUI-067 — Rejected entries banner

**Given** the API response includes `rejected[]` with at least one entry
**When** results are rendered
**Then** a banner appears above the table: « N entrée(s) ignorée(s) : [list of sanitized samples] » (i18n `tools.mac_oui.rejected_notice`)

### AC-MAC-OUI-068 — Copy to clipboard button

**Given** the result table is non-empty
**When** the user clicks the "Copy" button
**Then** the results are copied as tab-separated text suitable for pasting into a ticket or spreadsheet

### AC-MAC-OUI-069 — Empty result state

**Given** the API responds with `results=[]` and `rejected=[]`
**When** the page renders
**Then** the i18n `tools.mac_oui.no_results` message is displayed (no empty table)

### AC-MAC-OUI-070 — Loading state

**Given** the user clicks Execute
**When** the request is in flight
**Then** the Execute button is disabled, a spinner is shown, the textarea is read-only

---

## 10. i18n

### AC-MAC-OUI-071 — French locale

**Given** the user's locale is `fr`
**When** the page renders
**Then** all labels, messages, and error strings are in French (keys `tools.mac_oui.*`, `errors.mac_oui_*`)

### AC-MAC-OUI-072 — English locale

**Given** the user's locale is `en`
**When** the page renders
**Then** all labels, messages, and error strings are in English

### AC-MAC-OUI-073 — All i18n keys present

**Given** the keys list per `spec-api-contract.md` §10.6
**When** running the i18n key audit script
**Then** all `tools.mac_oui.*` keys exist in both `fr.json` and `en.json` with no missing translation

---

## 11. RBAC

### AC-MAC-OUI-074 — Default seed for `mac_oui` follows existing pattern

**Given** the application boots and the `mac_oui` tool is registered
**When** the seed runs (cf. `src/backend/app/main.py:126-137`)
**Then** a `RoleToolPermission` row is created for each of (`visitor`, `authenticated`, `administrator`) with `allowed=True` (identical pattern to other tools)

### AC-MAC-OUI-075 — Admin can revoke per role via the matrix

**Given** an admin opens Administration > Modules
**When** the admin toggles off the `visitor` permission for `mac_oui`
**Then** the next visitor request to `mac_oui` returns HTTP 403 with the standard `ROLE_NOT_ALLOWED` code (no MAC-OUI-specific code)

### AC-MAC-OUI-076 — Module disabled globally

**Given** the admin sets `ToolModule.enabled=false` for `mac_oui`
**When** any user attempts to execute
**Then** the API returns HTTP 403 with `TOOL_DISABLED` (existing project convention)

### AC-MAC-OUI-077 — `mac_oui` removed from sidebar when disabled

**Given** a user's effective permission for `mac_oui` is `false` (or the tool is globally disabled)
**When** the sidebar renders
**Then** the `MAC OUI` entry is **absent** from the sidebar (consistent with existing tool gating, cf. `ui-spec.md` §2.2)

---

## 12. Rate limiting

### AC-MAC-OUI-078 — Inherits global baselines

**Given** the default rate limits per `functional-spec.md` §5
**When** an authenticated user calls `mac_oui`
**Then** the global limit (1 req/s soft, 500 req/h hard) applies — no MAC-OUI-specific limit

### AC-MAC-OUI-079 — Per-tool override available

**Given** the admin sets a per-tool hard limit of 50 req/h for `mac_oui` for `authenticated`
**When** an authenticated user exceeds this in 1 hour
**Then** the API returns HTTP 429 with `Retry-After` header

---

## 13. IEEE Sync

### AC-MAC-OUI-080 — HTTPS confirmed

**Given** the sync service downloads the 3 IEEE files
**When** the URLs are fetched
**Then** all URLs use `https://standards-oui.ieee.org/...` (confirmed accessible 2026-05-31, cf. ADR-013 §2.1)

### AC-MAC-OUI-081 — Nominal daily sync

**Given** all 3 IEEE files (MA-L, MA-M, MA-S) are reachable
**When** the daily sync job runs at `OUI_SYNC_HOUR` UTC
**Then** all 3 files are downloaded and parsed; new OUIs inserted; existing OUIs with no diff get `last_seen` updated to today; summary log emitted: `{added} new, {changed} changed, {confirmed} confirmed, 0 failed`

### AC-MAC-OUI-082 — File MA-L unavailable

**Given** the MA-L URL returns 5xx or times out
**When** the daily sync job runs
**Then** the MA-L file is skipped; MA-M and MA-S are processed normally; a WARNING log is emitted

### AC-MAC-OUI-083 — Three consecutive failures of same file → CRITICAL log

**Given** MA-L has failed 3 consecutive daily attempts
**When** the 3rd failure occurs
**Then** a CRITICAL-level log is emitted with the marker `ALERT_OUI_SYNC_FAILED_3X`. The status column in Admin > Modules reflects this state in red.

### AC-MAC-OUI-084 — OUI absent from current files preserved

**Given** OUI `001122` exists in DB with `last_seen=2026-05-01`
**When** the sync runs and `001122` is absent from all 3 IEEE files
**Then** the row is NOT deleted; `last_seen` remains 2026-05-01; no history row is inserted

### AC-MAC-OUI-085 — Configurable sync hour

**Given** the env var `OUI_SYNC_HOUR=5`
**When** the scheduler triggers
**Then** the sync runs at 05:00 UTC

### AC-MAC-OUI-086 — Sync log persisted

**Given** any sync run completes (success, partial, or failure)
**When** the run terminates
**Then** a row is inserted in `oui_sync_log` (per Sprint 5 model) with start/end timestamps, counts, file failures

### AC-MAC-OUI-087 — `change_type` classification: 3 values

**Given** a sync detects a diff
**When** the classification logic runs (cf. ADR-013 §2.3)
**Then** `change_type` is one of `name_change`, `address_change`, `revoked` — never `reassigned`

### AC-MAC-OUI-088 — UNIQUE(oui, oui_type) allows overlap

**Given** the IEEE files contain `8C:1F:64` in MA-L (IEEE Registration Authority) and `8C:1F:64:0` in MA-M (Acme Corp)
**When** the sync inserts both
**Then** both rows are stored (different `oui_type`); the `UNIQUE(oui, oui_type)` constraint is satisfied

---

## 14. Administration

### AC-MAC-OUI-089 — Status column in Admin > Modules

**Given** the admin opens Administration > Modules
**When** the table renders
**Then** a new column "Statut" (i18n `admin.status`) appears between the role permission columns and the "Paramètres" column. The cell shows a colored icon for modules whose `has_status` is true, otherwise the cell is empty.

### AC-MAC-OUI-090 — Status icon color semantics

**Given** the `mac_oui` module exposes status
**When** the status icon is rendered
**Then** the color reflects the latest sync state:
- 🟢 green: last sync `success`
- 🟡 yellow: last sync `partial` (1-2 files failed)
- 🔴 red: 3+ consecutive failures OR last sync `failed`
- ⚪ grey: module enabled, never synced yet

### AC-MAC-OUI-091 — Status modal opens centered

**Given** the admin clicks the status icon for `mac_oui`
**When** the click handler runs
**Then** a centered `<Modal>` opens (component `src/frontend/src/components/ui/Modal.tsx`, NOT a lateral drawer) containing the detailed status

### AC-MAC-OUI-092 — Status modal content

**Given** the status modal is open for `mac_oui`
**When** content is rendered
**Then** it includes:
- Date of last sync (locale-formatted)
- Per-file outcome (MA-L/MA-M/MA-S: success/skipped/failed)
- Counts: added / changed / confirmed
- Consecutive failure counters per file
- Manual "Trigger sync now" button (POSTs to `POST /api/v1/admin/oui/sync`)
- Table of last 30 runs (newest first)

### AC-MAC-OUI-093 — Settings modal opens centered

**Given** the admin clicks the gear icon for `mac_oui`
**When** the click handler runs
**Then** the existing centered `<Modal>` opens (same as other tools) with the configurable parameters listed in AC-MAC-OUI-094

### AC-MAC-OUI-094 — Admin-configurable parameters

**Given** the admin opens the `mac_oui` Settings modal
**When** the form renders
**Then** the following parameters are editable (stored in `ToolModuleSetting` table or equivalent existing mechanism), with the listed defaults:

| Parameter | Default | Range |
|---|---|---|
| `MAC_OUI_FRONTEND_INPUT_MAX_CHARS` | 50 000 | 1 000 – 200 000 |
| `MAC_OUI_BACKEND_BATCH_MAX_SIZE` | 2 000 | 100 – 10 000 |
| `MAC_OUI_HISTORY_PAGE_SIZE` | 10 | 5 – 50 |
| `OUI_SYNC_HOUR` | 3 | 0 – 23 |
| `OUI_SYNC_LOG_RETENTION_DAYS` | 365 | 7 – 3650 |

### AC-MAC-OUI-095 — Settings persisted and applied immediately

**Given** the admin updates a setting (e.g., `MAC_OUI_HISTORY_PAGE_SIZE` from 10 to 20)
**When** save succeeds
**Then** the next history-fetch request uses the new value (no app restart required)

### AC-MAC-OUI-096 — Manual sync endpoint

**Given** the admin clicks "Trigger sync now"
**When** the request is sent
**Then** `POST /api/v1/admin/oui/sync` is called; if a sync is already running, the response is 409 with code `OUI_SYNC_ALREADY_RUNNING`. Else 202 with a task ID.

### AC-MAC-OUI-097 — CLI on-demand sync

**Given** an operator runs `sakn-cli sync-oui`
**When** the command executes
**Then** a full IEEE sync runs (recorded in `oui_sync_log` with `triggered_by="cli"`), the result counts are printed, the exit code is `1` if any file failed else `0`, and a graceful message is shown (exit `0`) when a sync is already running.
*Proof:* `tests/unit/cli/test_sync_oui.py`.

### AC-MAC-OUI-098 — Sync log bounded retention

**Given** `oui_sync_log` rows older than `OUI_SYNC_LOG_RETENTION_DAYS`
**When** the weekly `oui_sync_log_cleanup` job runs
**Then** rows older than the retention are deleted while the single most recent run is always preserved.
*Proof:* `tests/integration/test_oui_sync_log_cleanup.py`.

### AC-MAC-OUI-099 — `module_deployed_at` in execute response

**Given** at least one successful sync exists
**When** the MAC OUI execute endpoint returns
**Then** `result.module_deployed_at` is the date of the earliest non-failed sync; it is absent when no sync exists.
*Proof:* `tests/integration/test_mac_oui_endpoint.py::TestModuleDeployedAt`.

### AC-MAC-OUI-100 — Audit log nullable actor

**Given** an audit-logged admin action with an unknown actor
**When** the `audit_logs` row is written
**Then** `admin_id` is `NULL` (consistent with `ON DELETE SET NULL`), not an invalid sentinel.
*Proof:* `tests/integration/test_audit_log_admin_id_nullable.py`.

---

## 15. Doutes / arbitrages requis

Tous les doutes du draft initial ont été levés lors de la revue Sprint 0. Cette section reste pour traçabilité.

### 15.1 Doutes initiaux et résolutions

| ID | Doute initial | Résolution Sprint 0 |
|---|---|---|
| 11.1 | Déduplication formats différents (`00:11:22` vs `0011.2200`) | Normalisation bare hex uppercase, dédup sur chaîne normalisée. Longueurs distinctes = entrées distinctes. |
| 11.2 | Cisco 2/3/4 groupes ? | Frontend tolérant : 2 et 3 groupes acceptés. Politique rappel > précision (ADR-014). |
| 11.3 | Chevauchement MA-L/MA-M/MA-S | `UNIQUE(oui, oui_type)` — spec corrigée. Une même valeur 24-bit peut exister en MA-L (pool IEEE) et comme préfixe de MA-M/MA-S. |
| 11.4 | `change_type` détection auto | 3 valeurs seulement : `name_change`, `address_change`, `revoked`. `reassigned` abandonné. `name_change` englobe le cas nom+adresse simultané. |
| 11.5 | Timeout 50k chars | Levé : l'extraction se fait au frontend, le backend reçoit une liste normalisée. |
| 11.6 | HTTP vs HTTPS IEEE | HTTPS confirmé fonctionnel (test 2026-05-31). |
| 11.7 | Format `oui` MA-M/MA-S | `XX:XX:XX:X_` et `XX:XX:XX:XX:X_` (underscore = wildcard). Légende sous tableau. |
| 11.8 | Endpoint admin status | Colonne « Statut » dans Admin > Modules avec icône colorée + modal centré. Endpoint `GET /api/v1/admin/modules/{tool}/status` générique. Flag `has_status` sur `ToolModule`. |
| 11.9 | RBAC visitor explicite vs implicite | Faux problème. Le projet seed déjà toutes les paires (rôle, tool) avec `allowed=True` (cf. `main.py:126-137`). Pas de comportement spécial pour mac_oui. |

### 15.2 Doutes ouverts (à traiter en cours d'implémentation)

- **AC-MAC-OUI-019 (timestamps comme faux positifs)** : si le taux de faux positifs sur timestamps se révèle gênant en usage réel (Sprint 4 testing), une heuristique de contexte temporel pourra être ajoutée. Hors scope MVP.
- **Regex frontend finale** : à composer en Sprint 4 avec gestion correcte de la précédence (longueurs supérieures matchent en premier). Tests exhaustifs depuis l'annexe A de l'ADR-014.

---

## 16. Références croisées

| Source | Sections pertinentes |
|---|---|
| `functional-spec.md` | §3.5 (MAC OUI), §5 (rate limiting) |
| `spec-backend.md` | §4.2 (MacOui, MacOuiHistory — `UNIQUE(oui, oui_type)`), §9.6 (OUI sync HTTPS), §6 (rate limiting) |
| `spec-tools-instant.md` | §4 (MAC OUI: à corriger pour refléter l'extraction frontend), §1 (HTTP envelope), §6 (timeout) |
| `spec-api-contract.md` | §9 (error codes), §10 (i18n keys) |
| `spec-frontend.md` | §4.1 (textarea input — à étendre pour décrire la regex tolérante) |
| `ui-spec.md` | SCR-26 (MAC OUI Lookup page), §2.2 (sidebar) |
| `docs/adr/ADR-013-mac-oui-sync-strategy.md` | Stratégie de sync (3 change_type, UNIQUE(oui,oui_type), HTTPS, pas de purge) |
| `docs/adr/ADR-014-mac-oui-extraction-regex.md` | Extraction frontend tolérante, format MA-M/MA-S avec `_`, OUI ambigu |
| `src/backend/app/main.py:126-137` | Pattern de seed RoleToolPermission existant |
| `src/frontend/src/components/ui/Modal.tsx` | Composant Modal centré à réutiliser |
| `src/frontend/src/pages/admin/AdminModulesPage.tsx` | Structure existante du tableau Modules |

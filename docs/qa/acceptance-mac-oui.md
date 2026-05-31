# Acceptance Criteria — MAC OUI Lookup

> **Version:** 0.1.0 (draft)
> **Status:** Draft — pending review
> **Date:** 2026-05-31
> **Module:** MAC OUI Lookup (`mac_oui`)
> **References:** `functional-spec.md` §3.5, `spec-tools-instant.md` §4, `spec-backend.md` §4.2/§9.6, `spec-api-contract.md` §9-10, `spec-frontend.md` §4.1, `ui-spec.md` SCR-26

---

## 1. Extraction de patterns

### AC-MAC-OUI-001 — MAC colon-separated (6 octets)

**Given** the input text contains `00:11:22:33:44:55`
**When** the tool executes
**Then** the OUI `00:11:22` is extracted and looked up

---

### AC-MAC-OUI-002 — MAC hyphen-separated (6 octets)

**Given** the input text contains `00-11-22-33-44-55`
**When** the tool executes
**Then** the OUI `00:11:22` is extracted and looked up

---

### AC-MAC-OUI-003 — MAC dot-separated Cisco-style (6 octets)

**Given** the input text contains `0011.2233.4455`
**When** the tool executes
**Then** the OUI `00:11:22` is extracted and looked up

---

### AC-MAC-OUI-004 — MAC bare hex (6 octets)

**Given** the input text contains `001122334455`
**When** the tool executes
**Then** the OUI `00:11:22` is extracted and looked up

---

### AC-MAC-OUI-005 — OUI-only colon-separated (3 octets)

**Given** the input text contains `00:11:22`
**When** the tool executes
**Then** the OUI `00:11:22` is extracted and looked up

---

### AC-MAC-OUI-006 — OUI-only bare hex (3 octets)

**Given** the input text contains `001122`
**When** the tool executes
**Then** the OUI `00:11:22` is extracted and looked up

---

### AC-MAC-OUI-007 — Mixed formats in same input

**Given** the input text contains `00:11:22:33:44:55` and `00-11-22-33-44-55` and `0011.2233.4455`
**When** the tool executes
**Then** all three OUIs (`00:11:22`) are extracted, deduplicated to a single result row

---

### AC-MAC-OUI-008 — Case insensitivity

**Given** the input text contains `0A:1B:2C:3D:4E:5F` and `0a:1b:2c:3d:4e:5f`
**When** the tool executes
**Then** both are extracted as the same OUI `0A:1B:2C` (deduplicated, one result)

---

### AC-MAC-OUI-009 — Non-MAC text ignored

**Given** the input text is `Server 192.168.1.1 has MAC 00:11:22:33:44:55 on VLAN 10`
**When** the tool executes
**Then** only `00:11:22:33:44:55` is extracted; `192.168.1.1` and `10` are ignored

---

### AC-MAC-OUI-010 — Multiple distinct OUIs in same input

**Given** the input text contains `00:11:22:33:44:55` and `aa:bb:cc:dd:ee:ff`
**When** the tool executes
**Then** two result rows are returned: one for `00:11:22`, one for `AA:BB:CC`

---

### AC-MAC-OUI-011 — MAC embedded in ARP table output

**Given** the input text is a realistic ARP table:
```
Internet  10.0.0.1           0   00:11:22:33:44:55   ARPA   Vlan10
Internet  10.0.0.2           0   00-11-22-33-44-AA   ARPA   Vlan10
```
**When** the tool executes
**Then** both MACs are extracted; they share the same OUI `00:11:22`, so `parse_stats.mac_oui_count = 2` and `parse_stats.unique_oui_count = 1`, with one result row for `00:11:22`.

---

### AC-MAC-OUI-012 — Full MAC and OUI-only pattern with same prefix

**Given** the input text contains both `00:11:22:33:44:55` (full MAC) and `00:11:22` (OUI-only)
**When** the tool executes
**Then** one result row for `00:11:22` (deduplicated to single lookup)

---

## 2. Déduplication

### AC-MAC-OUI-013 — Exact duplicate OUIs

**Given** the input text contains `00:11:22:33:44:55` twice (same line repeated)
**When** the tool executes
**Then** the OUI `00:11:22` appears exactly once in the results

---

### AC-MAC-OUI-014 — Same OUI, different full-MAC formats

**Given** the input text contains `00:11:22:33:44:55` (colon) and `00-11-22-33-44-55` (hyphen) and `0011.2233.4455` (Cisco)
**When** the tool executes
**Then** one result row for `00:11:22` (all three are the same OUI)

---

### AC-MAC-OUI-015 — Same OUI, different separator but same byte count

**Given** the input text contains `00:11:22` (colon, 3 bytes) and `001122` (bare hex, 3 bytes)
**When** the tool executes
**Then** one result row for `00:11:22` (deduplicated to single lookup)

---

### AC-MAC-OUI-016 — OUI prefixes of different lengths (MA-L vs MA-M overlap)

**Given** the input text contains a MAC whose first 6 hex digits match an MA-L entry and whose first 7 hex digits match an MA-M entry
**When** the tool executes
**Then** only the longest-prefix match is returned (MA-M wins over MA-L), per `functional-spec.md` §3.5.4

---

## 3. Lookup IEEE

### AC-MAC-OUI-017 — MA-L hit (24-bit)

**Given** the OUI `00:11:22` exists in the `MacOui` table with `oui_type = MA-L`
**When** the tool looks up `00:11:22`
**Then** the result includes `organization`, `address`, `oui_type = "MA-L"`, `first_seen`, `last_seen`

---

### AC-MAC-OUI-018 — MA-M hit (28-bit)

**Given** the OUI `00:11:22:3` (7 hex digits) exists in the `MacOui` table with `oui_type = MA-M`
**When** the tool looks up this OUI
**Then** the result includes `oui_type = "MA-M"` and the corresponding organization

---

### AC-MAC-OUI-019 — MA-S hit (36-bit)

**Given** the OUI `00:11:22:33:4` (9 hex digits) exists in the `MacOui` table with `oui_type = MA-S`
**When** the tool looks up this OUI
**Then** the result includes `oui_type = "MA-S"` and the corresponding organization

---

### AC-MAC-OUI-020 — Longest prefix wins

**Given** the MAC `00:11:22:33:44:55`:
- `001122` matches an MA-L entry in the database
- `0011223` matches an MA-M entry in the database
**When** the tool looks up this MAC
**Then** the MA-M entry (`0011223`) is returned (most specific / longest prefix)

---

### AC-MAC-OUI-021 — Unknown vendor (OUI not in database)

**Given** the OUI `FF:EE:DD` is extracted from input but does not exist in the `MacOui` table
**When** the tool looks up this OUI
**Then** the result row shows `organization` = "Unknown vendor" (i18n key `tools.mac_oui.unknown_vendor`), and `oui_type`, `address`, `first_seen`, `last_seen` are `null`

---

### AC-MAC-OUI-022 — Lookup is case-insensitive

**Given** the database stores OUI `001122` (uppercase bare hex)
**When** the tool looks up extracted OUI `0a:1b:2c` (lowercase input)
**Then** the lookup normalizes to uppercase bare hex `0A1B2C` and matches correctly

---

### AC-MAC-OUI-023 — Result fields match spec

**Given** a successful lookup
**When** the API returns results
**Then** each result object contains exactly: `oui`, `organization`, `address`, `oui_type`, `first_seen`, `last_seen` (per `spec-tools-instant.md` §4.3)

---

## 4. Historique des changements

### AC-MAC-OUI-024 — OUI without history

**Given** an OUI `00:11:22` has existed in the database with the same organization since `first_seen`
**When** the tool looks up this OUI
**Then** the `history` array for this OUI is empty (`[]`)

---

### AC-MAC-OUI-025 — OUI with name change

**Given** OUI `00:11:22` changed organization name from "Cisco Systems, Inc." to "Cisco Systems, LLC" during a sync
**When** the tool looks up this OUI
**Then** the `history` array includes an entry with:
- `previous_organization` = "Cisco Systems, Inc."
- `new_organization` = "Cisco Systems, LLC"
- `change_type` = "name_change"
- `changed_at` = the date the sync detected the change

---

### AC-MAC-OUI-026 — OUI with address change

**Given** OUI `00:11:22` changed address between two syncs (same organization name)
**When** the tool looks up this OUI
**Then** the `history` array includes an entry with `change_type` = "address_change", containing `previous_address` and `new_address`

---

### AC-MAC-OUI-027 — OUI with revoked status

**Given** OUI `00:11:22` was present in a previous IEEE file but is now listed as revoked
**When** the tool looks up this OUI
**Then** the `history` array includes an entry with `change_type` = "revoked"

---

### AC-MAC-OUI-028 — OUI reassigned to different organization

**Given** OUI `00:11:22` changed from "Old Vendor Inc." to "New Vendor LLC" (different legal entity)
**When** the tool looks up this OUI
**Then** the `history` array includes an entry with `change_type` = "reassigned"

---

### AC-MAC-OUI-029 — OUI with multiple historical changes

**Given** OUI `00:11:22` has 3 `MacOuiHistory` rows: a name change on 2026-01-15, an address change on 2026-03-10, and a reassignment on 2026-05-20
**When** the tool looks up this OUI
**Then** the `history` array contains all 3 entries, ordered by `detected_at` ascending (oldest first)

---

## 5. Garde-fous

### AC-MAC-OUI-030 — Empty input

**Given** the input `text` parameter is an empty string (`""`)
**When** the tool executes
**Then** the API returns HTTP 422 with error code `MAC_OUI_PARSE_EMPTY` and `message_key` = `errors.mac_oui_parse_empty`

---

### AC-MAC-OUI-031 — Input exceeds 50 000 characters

**Given** the input `text` parameter is 50 001+ characters
**When** the tool executes
**Then** the API returns HTTP 422 with `VALIDATION_ERROR` (parameter constraint violated, per `functional-spec.md` §3.5.2)

---

### AC-MAC-OUI-032 — No valid MAC/OUI found

**Given** the input text is `This is a sentence with no MAC addresses. Just words.`
**When** the tool executes
**Then** the API returns HTTP 422 with error code `MAC_OUI_PARSE_EMPTY` and `message_key` = `errors.mac_oui_parse_empty`

---

### AC-MAC-OUI-033 — Input contains only invalid hex patterns

**Given** the input text is `12345` (odd number of hex digits, not a valid MAC/OUI pattern)
**When** the tool executes
**Then** no patterns are extracted; the API returns HTTP 422 with `MAC_OUI_PARSE_EMPTY`

---

### AC-MAC-OUI-034 — Whitespace-only input

**Given** the input `text` parameter is `"   \n\t   "` (only whitespace)
**When** the tool executes
**Then** the API returns HTTP 422 with `MAC_OUI_PARSE_EMPTY`

---

### AC-MAC-OUI-035 — Input at 50 000 characters with valid MACs

**Given** the input `text` is exactly 50 000 characters and contains valid MAC patterns
**When** the tool executes
**Then** the tool processes the text successfully within the 5-second timeout (per `spec-tools-instant.md` §6), extracts valid patterns, and returns results

---

## 6. Sortie API

### AC-MAC-OUI-036 — Success response envelope

**Given** the tool executes successfully
**When** the API responds
**Then** the response is HTTP 200 with the envelope `{"tool": "mac_oui", "success": true, "duration_ms": <number>, "data": {...}}` per `spec-tools-instant.md` §1.2

---

### AC-MAC-OUI-037 — `parse_stats` accuracy

**Given** an input text of 150 characters containing 3 MAC addresses with 2 unique OUIs
**When** the tool executes
**Then** `data.parse_stats` contains:
- `total_input_chars` = 150
- `mac_oui_count` = 3 (total patterns extracted before dedup)
- `unique_oui_count` = 2 (after dedup)

---

### AC-MAC-OUI-038 — `history` always present

**Given** a successful lookup of an OUI with no changes
**When** the API responds
**Then** `data.history` is an empty array `[]` (not absent, not `null`)

---

### AC-MAC-OUI-039 — OUI formatted as uppercase colon-separated in response

**Given** the extracted OUI is `001122` (bare hex)
**When** the API returns the result
**Then** the `oui` field is formatted as `00:11:22` (uppercase, colon-separated) per `spec-tools-instant.md` §4.3

---

## 7. i18n

### AC-MAC-OUI-040 — French locale

**Given** the user's locale is `fr` or `fr-FR`
**When** the frontend renders the MAC OUI tool page
**Then** all labels, messages, and error strings are displayed in French using the `tools.mac_oui.*` keys

---

### AC-MAC-OUI-041 — English locale

**Given** the user's locale is `en` or `en-US`
**When** the frontend renders the MAC OUI tool page
**Then** all labels, messages, and error strings are displayed in English

---

### AC-MAC-OUI-042 — Error message key for empty parse

**Given** the tool returns `MAC_OUI_PARSE_EMPTY`
**When** the frontend renders the error
**Then** the error message is translated from the `errors.mac_oui_parse_empty` key (FR and EN both available)

---

### AC-MAC-OUI-043 — "Unknown vendor" i18n

**Given** an OUI is not found in the database
**When** the frontend renders the result
**Then** the string "Unknown vendor" (EN) / "Fabricant inconnu" (FR) is shown, using key `tools.mac_oui.unknown_vendor`

---

## 8. RBAC

### AC-MAC-OUI-044 — Visitor denied by default

**Given** no admin has explicitly granted `visitor` role access to the `mac_oui` tool
**When** a visitor (unauthenticated) accesses the MAC OUI tool (page or API)
**Then** the API returns HTTP 403 with error code `ROLE_NOT_ALLOWED`

---

### AC-MAC-OUI-045 — Authenticated user allowed

**Given** the default `RoleToolPermission` for `authenticated` role on `mac_oui` is `allowed = true`
**When** an authenticated user executes the MAC OUI tool
**Then** the tool executes normally and returns HTTP 200

---

### AC-MAC-OUI-046 — Admin allowed

**Given** the default `RoleToolPermission` for `administrator` role on `mac_oui` is `allowed = true`
**When** an admin executes the MAC OUI tool
**Then** the tool executes normally and returns HTTP 200

---

### AC-MAC-OUI-047 — Tool disabled globally

**Given** an admin sets `ToolModule.enabled = false` for `mac_oui`
**When** any user (including admin) attempts to execute the tool
**Then** the API returns HTTP 403 with error code `TOOL_DISABLED`

---

## 9. Rate limiting

### AC-MAC-OUI-048 — Authenticated user within limits

**Given** an authenticated user has a global hard limit of 500 req/hr and has made 10 requests
**When** the user executes the MAC OUI tool
**Then** the API returns HTTP 200 (no rate limit triggered)

---

### AC-MAC-OUI-049 — Authenticated user exceeds soft limit

**Given** an authenticated user has a global soft limit of 1 req/sec
**When** the user sends 2 requests within 1 second
**Then** the second request returns HTTP 429 with `Retry-After: 1` and error code `RATE_LIMIT_EXCEEDED`

---

### AC-MAC-OUI-050 — Visitor IP rate limit applies

**Given** a visitor IP has a global hard limit of 200 req/hr
**When** the visitor (if granted access) exceeds this limit on the MAC OUI tool
**Then** the API returns HTTP 429 with `Retry-After: 3600`

---

### AC-MAC-OUI-051 — Per-tool rate limit can tighten global limit

**Given** an admin sets a per-tool hard limit of 50 req/hr for `mac_oui` for `authenticated` role (tighter than the global 500)
**When** an authenticated user exceeds 50 requests in an hour
**Then** the API returns HTTP 429 (per-tool limit enforced)

---

## 10. Synchronisation IEEE

### AC-MAC-OUI-052 — Nominal daily sync (all 3 files)

**Given** all 3 IEEE files (MA-L, MA-M, MA-S) are available at their URLs
**When** the daily sync job runs
**Then**:
- All 3 files are downloaded and parsed
- New OUIs are inserted with `first_seen = today`
- Existing OUIs with unchanged org/address get `last_seen` updated to today
- A summary log is emitted: `{added} new, {changed} changed, {confirmed} confirmed, 0 failed`

---

### AC-MAC-OUI-053 — MA-L file temporarily unavailable

**Given** `http://standards-oui.ieee.org/oui/oui.txt` returns HTTP 5xx or times out
**When** the daily sync job runs
**Then**:
- The MA-L file is skipped
- MA-M and MA-S files are processed normally
- A WARNING log is emitted for the MA-L failure
- Existing MA-L data is preserved unchanged (`last_seen` not updated)

---

### AC-MAC-OUI-054 — MA-M file temporarily unavailable

**Given** `http://standards-oui.ieee.org/oui28/mam.txt` is unreachable
**When** the daily sync job runs
**Then** MA-M is skipped; MA-L and MA-S are processed; WARNING logged; MA-M data preserved

---

### AC-MAC-OUI-055 — MA-S file temporarily unavailable

**Given** `http://standards-oui.ieee.org/oui36/oui36.txt` is unreachable
**When** the daily sync job runs
**Then** MA-S is skipped; MA-L and MA-M are processed; WARNING logged; MA-S data preserved

---

### AC-MAC-OUI-056 — Three consecutive failures for same file → CRITICAL alert

**Given** the MA-L file has failed to download for 3 consecutive daily sync attempts
**When** the 3rd consecutive failure occurs
**Then** a CRITICAL-level log is emitted (actionable as an admin alert), per `spec-backend.md` §9.6

---

### AC-MAC-OUI-057 — OUI not present in any IEEE file is preserved

**Given** an OUI `00:11:22` exists in the database with `last_seen = 2026-05-01`
**When** the daily sync runs and this OUI is absent from all 3 IEEE files
**Then**:
- The OUI row is NOT deleted
- `last_seen` remains `2026-05-01` (not updated)
- No `MacOuiHistory` row is inserted (absence from file is not a "change")

---

### AC-MAC-OUI-058 — All 3 files unavailable

**Given** all 3 IEEE files are unreachable
**When** the daily sync job runs
**Then**:
- All 3 are skipped
- A WARNING log is emitted for each
- Existing data is fully preserved
- The consecutive failure counter increments per file independently

---

### AC-MAC-OUI-059 — Sync schedule respects configured hour

**Given** the env var `OUI_SYNC_HOUR=5`
**When** the APScheduler job triggers
**Then** the sync runs at 05:00 UTC daily (per `spec-backend.md` §9.6)

---

### AC-MAC-OUI-060 — Sync job parse failure

**Given** one of the IEEE files is downloaded but contains malformed content (no valid `(hex)` lines)
**When** the sync processes this file
**Then**:
- An ERROR log is emitted
- The file is skipped
- The consecutive failure counter increments

---

## 11. Doutes / arbitrages requis

### 11.1 Déduplication de formats différents

Le brief mentionne : « doublons avec formats différents (`00:11:22` vs `0011.2200` représentent-ils la même chose ? → à trancher dans l'ADR §3.3) ».

**Analyse** :
- `00:11:22` en notation hex pairs = 3 octets (00 11 22), soit un OUI MA-L 24-bit.
- `0011.2200` en notation Cisco = 2 paires de 4 digits → `00 11` puis `22 00`, soit 4 octets (00 11 22 00), un OUI 28-bit.
- Ces deux patterns ont des longueurs différentes, donc ils ne peuvent pas représenter le même OUI.
- Le cas pertinent serait `00:11:22` vs `0011.22` (tous deux 3 octets), ou `00:11:22:33` vs `0011.2233` (tous deux 4 octets).

**Question** : l'exemple du brief est-il une coquille pour `00:11:22` vs `0011.22` (3 octets, deux formats), ou bien le brief demande-t-il si un OUI 3-octets et un OUI 4-octets qui partagent les 3 premiers octets doivent être considérés comme « doublons » pour la déduplication ?

**Impact** : si on déduplique `00:11:22` (MA-L) et `00112233` (MA-M potentiel), on perd la spécificité MA-M. La spec `functional-spec.md` §3.5.4 dit « longest prefix wins », ce qui suggère qu'on ne les déduplique pas — on garde le plus long.

→ À trancher lors de la revue conjointe et dans l'ADR-014.

### 11.2 Cisco dot-separated : 2, 3, ou 4 groupes ?

La spec `spec-tools-instant.md` §4.4 liste `0011.2233.4455` (3 groupes de 4 digits = 6 octets) et mentionne aussi `0011.22` (2 groupes = 3 octets). Mais le format Cisco peut aussi avoir :
- `0011.2233` (2 groupes = 4 octets)
- `0011.22` (2 groupes mais le second groupe n'a que 2 digits → 3 octets)

**Question** : le pattern Cisco accepte-t-il un nombre variable de groupes (2 ou 3) ? Accepte-t-il un dernier groupe tronqué à 2 digits (comme `0011.22` pour un OUI 3-octets) ?

**Impact** : si un dernier groupe de 2 digits est accepté, `0011.2233` (4 octets) et `0011.22` (3 octets) sont deux OUIs distincts qu'il faut extraire correctement.

→ À trancher dans l'ADR-014.

### 11.3 Chevauchement MA-L / MA-M / MA-S en base

La spec `spec-backend.md` §9.6 ne précise pas le comportement quand un même préfixe apparait dans deux fichiers IEEE différents (ex. `001122` dans MA-L et `0011223` dans MA-M). La spec dit « longest prefix wins » pour le lookup (§3.5.4 fonctionnel), mais ne dit pas comment stocker.

**Question** : stocke-t-on les deux entrées (MA-L et MA-M pour des préfixes qui se chevauchent) ou une seule ?

→ À trancher dans l'ADR-013.

### 11.4 `change_type` : détection automatique

La spec `spec-backend.md` §4.2 liste `change_type` avec les valeurs `name_change`, `address_change`, `revoked`, `reassigned`. Mais la spec §9.6 décrit seulement une comparaison org/address : « OUI exists with different org or address → insert MacOuiHistory row with change_type ».

**Question** : comment le sync service distingue-t-il automatiquement `name_change` de `reassigned` à partir d'un simple diff de chaînes ? Faut-il une heuristique (ex. distance de Levenshtein) ou l'opérateur humain devra-t-il reclassifier manuellement ?

→ À trancher dans l'ADR-013.

### 11.5 Timeout d'extraction

La spec `spec-tools-instant.md` §6 donne un timeout de 5s pour MAC OUI Lookup (DB query + regex). Pour un input de 50 000 caractères contenant des milliers de patterns potentiels, une regex complexe avec backtracking pourrait dépasser ce timeout.

**Question** : la regex a-t-elle été testée sur un worst-case de 50 000 caractères ? Faut-il prévoir une limite sur le nombre de patterns extraits (ex. max 1 000 OUIs) pour garantir le timeout ?

→ À vérifier lors du Sprint 3 (implémentation de l'extraction). L'ADR-014 doit inclure une analyse de complexité de la regex retenue.

### 11.6 IEEE file URLs — HTTP vs HTTPS

Les URLs dans `spec-backend.md` §9.6 et `spec-tools-instant.md` §4.5 utilisent `http://` (pas `https://`). En production, le téléchargement transite en clair.

**Question** : IEEE propose-t-il des endpoints HTTPS pour ces fichiers ? Si oui, doit-on utiliser HTTPS ? Si non, faut-il documenter le risque ?

→ À vérifier lors de la revue de sécurité. Si IEEE ne propose pas HTTPS, documenter dans `docs/security/`.

### 11.7 Format de sortie du champ `oui`

La spec `spec-tools-instant.md` §4.3 dit : « oui: the extracted OUI prefix (uppercase, colon-separated, e.g., 00:11:22) ». Mais pour un OUI MA-M (7 digits), le format n'est pas spécifié. Exemple : `00:11:22:3` ou `00:11:22:30` ?

**Question** : comment formate-t-on un OUI MA-M (28-bit, 7 hex digits) et MA-S (36-bit, 9 hex digits) en notation colon-separated ?

→ À clarifier et spécifier dans l'ADR-014.

### 11.8 Absence de spec pour le endpoint admin sync status

La spec `spec-backend.md` §9.6 mentionne « Admin visibility: sync status and last run time visible in the admin Modules section » mais aucun endpoint API n'est défini pour exposer cet état. Le `GET /admin/modules/{tool_name}/...` existe pour les DNS presets mais pas pour le statut de sync MAC OUI.

**Question** : faut-il un endpoint dédié (ex. `GET /admin/modules/mac_oui/sync-status`) ou étendre le endpoint modules existant ?

→ À spécifier dans le Sprint 6 (admin).

### 11.9 RBAC visitor : « désactivé par défaut » vs « deny if no config »

Le brief §3.1 dit « visitor désactivé par défaut ». La spec `functional-spec.md` §2.3 dit « Default: deny if no configuration exists ». Ces deux formulations sont-elles équivalentes ?

**Analyse** : oui — un visiteur sans `RoleToolPermission` explicite `allowed=true` se voit refuser l'accès. Mais le brief suggère que le comportement par défaut du seed de données doit explicitement mettre `visitor → denied` pour `mac_oui`.

**Question** : le seed doit-il explicitement créer une `RoleToolPermission(role=visitor, tool=mac_oui, allowed=false)` ou se contenter de l'absence de ligne ?

→ À trancher : explicite (plus clair, auditable) vs implicite (moins de lignes, cohérent avec le reste).

---

## 12. Références croisées

| Source | Sections pertinentes |
|---|---|
| `functional-spec.md` | §3.5 (MAC OUI), §5 (rate limiting) |
| `spec-backend.md` | §4.2 (MacOui, MacOuiHistory models), §9.6 (OUI sync), §6 (rate limiting) |
| `spec-tools-instant.md` | §4 (MAC OUI execution, parameters, result, sync), §1 (HTTP envelope), §6 (timeout) |
| `spec-api-contract.md` | §9 (error codes — `MAC_OUI_PARSE_EMPTY`), §10 (i18n keys `tools.mac_oui.*`, `errors.mac_oui_parse_empty`) |
| `spec-frontend.md` | §4.1 (textarea input) |
| `ui-spec.md` | SCR-26 (MAC OUI Lookup page) |

# Revue de sécurité — `dev0.2.0-macoui` → `dev0.2.0`

**Auditeur** : AppSec senior (revue indépendante)
**Date** : 2026-06-03
**Périmètre** : diff `master`@0.1.0 → `dev0.2.0-macoui` (~117 fichiers, +12 346 lignes), focus MAC OUI Lookup + fondations réutilisées.
**Mode** : lecture seule. Aucune modification de code applicatif.

## 1. Résumé exécutif

La feature **MAC OUI Lookup** (sync IEEE, lookup local, admin/observabilité, CLI) est, dans l'ensemble, **bien conçue côté sécurité** :

- La sync IEEE n'est **pas** un vecteur SSRF : URLs **codées en dur** en HTTPS, `follow_redirects=False`, cap de taille streaming (50 Mo) + timeout, fallback d'encodage maîtrisé (`oui_sync_service.py:22-26,74-80,329-359`).
- L'injection SQL est **écartée** : tout passe par des requêtes SQLAlchemy paramétrées (aucun `text()`/f-string en SQL).
- Le risque **ReDoS est neutralisé** : les regex backend sont bornées/ancrées sans backtracking (`mac_oui_validator.py:17-21`) ; les regex frontend sont linéaires (`macOuiExtractor.ts:36-57`).
- Le **XSS est maîtrisé** : rendu React échappé, aucun `dangerouslySetInnerHTML`, choke-point de sanitisation unique pour l'écho des entrées rejetées (`mac_oui_validator.py:53-60`), CSP stricte sans `unsafe-inline` sur les scripts (`security_headers.py:11-16`).
- L'**AuthN/AuthZ** des endpoints admin est cohérente (`require_admin` sur tous les `/admin/*` MAC OUI).

**Aucun finding nouveau de sévérité `high`/`critical` n'est introduit par cette branche.** Les 4 issues déjà tracées (#380-#383) sont confirmées comme `low`/`medium`. Un point pré-existant mais matériel (SSRF via résolveur DNS arbitraire) est rappelé car il **contredit un contrôle documenté dans le threat model** ; il n'est pas introduit par cette branche et ne touche pas son périmètre.

### Recommandation : **GO (accepter avec réserves)**

Le merge `dev0.2.0-macoui` → `dev0.2.0` peut procéder. Réserves :

1. Corriger #382 (masquage d'alerte « vert » quand les 3 fichiers échouent) avant la livraison 0.2.0 — impact observabilité/availability.
2. Ouvrir une issue pré-existante pour le **SSRF résolveur DNS** (NEW-1) et corriger l'écart de threat model.
3. Traiter #381 (race TTL-reclaim) et les durcissements `low` lors d'un sprint de suivi.

---

## 2. Tableau des findings

| ID | Titre | Sévérité | Fichier:ligne | Statut / Issue | Axe |
|----|-------|----------|---------------|----------------|-----|
| NEW-1 | SSRF — résolveur DNS arbitraire non filtré (visiteur non authentifié) | **medium** | `tools/dns_lookup.py:113-124,248-251` | nouveau (code **pré-existant**) ; écart threat-model — #385 | 3 SSRF |
| CONF-382 | Statut module « success » quand les 3 fichiers IEEE échouent | **medium** | `api/v1/endpoints/admin_modules.py:349-353` | confirmé #382 | 8 Intégrité/observabilité |
| CONF-381 | Race TOCTOU sur la branche TTL-reclaim du lock de sync | **low** | `services/oui_sync_service.py:154-169` | confirmé #381 | 10 Concurrence |
| NEW-2 | Pas de cap de longueur par chaîne d'entrée (amplification mémoire/CPU) | **low** | `tools/mac_oui_lookup.py:121-157` ; `mac_oui_validator.py:81-93` | nouveau (0.2.0) — #386 | 2 DoS |
| NEW-3 | CSRF non appliqué aux endpoints admin & `tools/execute` (token présent mais non vérifié) | **low** | `api/v1/endpoints/admin_oui_sync.py:31-37` ; `tools.py:385-409` | nouveau (admin_oui_sync) / pré-existant — #387 | 4 AuthZ |
| NEW-4 | Posture d'autorisation des outils en *default-allow* (auto-création `allowed=True`) | **low** | `main.py:136-147` ; `tools.py:345-371` | nouveau (mac_oui auto-exposé) — #388 | 4 AuthZ |
| NEW-5 | `PUT /admin/settings` sans allowlist de clés (écrasement de clés de contrôle interne) | **info** | `api/v1/endpoints/admin_settings.py:34-74` | nouveau — #389 | 9 Config |
| CONF-383 | Flag `ambiguous` non positionné (déviation ADR-014) | **info** | `tools/mac_oui_lookup_service.py:204-302` | confirmé #383 | (fonctionnel) |
| CONF-380 | Pagination historique vide pour MAC 48-bit | **info** | `tools.py:518-621` | confirmé #380 | (logique) |
| CONF-WS | `WS_REQUIRE_ORIGIN=False` par défaut (doit être `True` en prod) | **low** | `config.py:141` ; `tools.py:168-178` | rappel config | 7 WebSocket |

---

## 3. Détail par finding

### NEW-1 — SSRF via résolveur DNS arbitraire (medium)

**Axe** : 3 (SSRF). **Statut** : code pré-existant (hors diff fonctionnel 0.2.0), mais **en périmètre** et **contredisant le threat model**.

**Description.** L'outil DNS Lookup accepte un paramètre `resolver` fourni par le client dans le corps de `POST /api/v1/tools/dns_lookup/execute`. Cette valeur est utilisée telle quelle comme serveur de noms, **sans contrôle contre la blocklist** :

- `dns_lookup.py:113-114` : `resolver_ip = (params.get("resolver") or "").strip()` — seule la sentinelle `__system__` est traitée ; aucune validation d'IP ni blocklist.
- `dns_lookup.py:248-251` : `_make_resolver` fait `resolver_obj.nameservers = [resolver_ip]`.
- Le contrôle de sécurité `_security_check` (`dns_lookup.py:231-240`) ne valide que les **IP de réponse** de la cible, résolues via le **résolveur de confiance** `SECURITY_DNS_RESOLVER` — **jamais l'IP du résolveur fourni par l'utilisateur**.

L'outil est **accessible aux visiteurs non authentifiés** : le seed crée `RoleToolPermission(allowed=True)` pour tous les rôles (`main.py:136-147`).

**Impact.** Un attaquant non authentifié peut faire émettre au serveur des requêtes DNS (UDP/53, repli TCP/53) vers une **IP interne arbitraire** : `169.254.169.254`, résolveurs internes (AD/DNS d'entreprise), services en `10.0.0.0/8`/`192.168.0.0/16`. Permet : reconnaissance réseau interne (oracle d'atteignabilité/timing sur le port 53), interrogation de zones DNS internes (fuite d'infos), usage du serveur comme proxy/exfiltration DNS vers un résolveur contrôlé. Contraint au protocole DNS (pas de RCE, IMDS HTTP non atteignable par ce vecteur).

**PoC.**

```
POST /api/v1/tools/dns_lookup/execute
{"target":"internal.corp.example","record_types":["A","TXT"],"resolver":"10.0.0.53"}
```

→ le serveur interroge `10.0.0.53` et renvoie/diffère selon l'atteignabilité.

**Écart threat model.** `docs/security/threat-model.md:137` affirme « *same blocklist applied regardless of which resolver is selected; resolver IP itself is validated* » et classe le risque comme **opérateur/admin** (« Admin panel allows configuring arbitrary DNS server IPs as presets »). En réalité : (a) la blocklist s'applique aux **réponses**, pas à **l'IP du résolveur** ; (b) le paramètre `resolver` est **exécutable par n'importe quel visiteur**, pas seulement via les presets admin. La ligne 137 documente donc un contrôle **non implémenté**.

**Remédiation.** Valider `resolver_ip` comme IP et la passer dans `is_ip_blocked()` (réutiliser `address_filter.is_ip_blocked`) avant de l'affecter aux `nameservers`, en rejetant les IP bloquées avec `errors.target_not_allowed`. Restreindre éventuellement le résolveur libre aux rôles authentifiés/admin, ou n'autoriser que les presets en base. Mettre à jour la ligne 137 du threat model.

---

### CONF-382 — Statut « vert » quand les 3 fichiers IEEE échouent (medium) — confirmé #382

**Axe** : 8. `admin_modules.py:349-353` :

```python
elif last_log.files_failed:
    failed_files = _safe_parse_files_failed(last_log.files_failed)
    derived_status = "partial" if 1 <= len(failed_files) <= 2 else "success"
```

Lors d'un run où **les 3 fichiers** échouent : `_finalize_log` fixe `status="partial"` (puisque `files_failed` non vide, et **non** `"failed"`, `oui_sync_service.py:276`), donc la branche `last_log.status == "failed"` ne se déclenche pas ; `len(failed_files)==3` tombe dans le `else` → **`success`** (vert). Les compteurs `consecutive_failures` ne valent 1 (pas ≥3) au premier run total. **Confirmé** : un échec total est masqué en « succès » au premier passage. Impact sécurité = **suppression d'alerte / angle mort de supervision** (intégrité de la donnée OUI silencieusement périmée). **Remédiation** : `derived_status = "alert" if len(failed_files) >= 3 else ("partial" if failed_files else "success")`, et/ou propager `status="failed"` quand tous les fichiers échouent.

---

### CONF-381 — Race TOCTOU sur la branche TTL-reclaim (low) — confirmé #381

**Axe** : 10. Le chemin nominal est correct (CAS atomique `UPDATE ... WHERE value='0'`, `oui_sync_service.py:141-153`). En revanche la **branche de réclamation d'un lock périmé** (lignes 154-168) n'est pas atomique : deux appels concurrents peuvent tous deux voir `_is_running()==False` (TTL dépassé) puis exécuter chacun un `UPDATE ... value='1'` inconditionnel et committer → **deux syncs simultanées**. **Pré-condition** : lock périmé (crash en cours de sync, ou dépassement de `RUNNING_TTL_SECONDS=3600`) — faible probabilité. **Impact** : double téléchargement IEEE (3×~6,5 Mo ×2), upserts concurrents ; l'intégrité reste protégée par `UNIQUE(oui, oui_type)` (`mac_oui.py:33`) — une course d'insertion provoque `IntegrityError` → le fichier est marqué `failed`, pas de doublon de ligne `MacOui`. Risque résiduel : entrées d'historique parasites et runs en échec. **Remédiation** : rendre la réclamation atomique via `UPDATE ... WHERE value='1' AND started_at < :cutoff` et tester `rowcount==1`.

---

### NEW-2 — Absence de cap de longueur par chaîne d'entrée (low)

**Axe** : 2 (DoS). `mac_oui_lookup.py:147-157` plafonne le **nombre** d'entrées (`DEFAULT_BATCH_MAX_SIZE=2000`, configurable) mais **aucune limite de longueur par chaîne**. `validate_batch` applique `_HEX_STRIP_RE.sub` et `_HEX_ONLY_RE.match` sur la chaîne **entière** (`mac_oui_validator.py:93,108`) — linéaire, **pas de ReDoS**, mais une requête de 2000 chaînes de plusieurs Mo chacune entraîne une **amplification mémoire/CPU**. L'extraction frontend borne à 50 000 caractères (`macOuiExtractor.ts:74`), mais le backend est appelable directement. **Mitigation** : un cap de corps de requête au reverse-proxy (à confirmer côté déploiement) borne l'impact. **Remédiation** : rejeter (ou tronquer en `rejected[]`) toute chaîne dépassant ~64 caractères avant traitement ; documenter une limite de taille de corps applicative.

---

### NEW-3 — CSRF non vérifié sur admin & `tools/execute` (low)

**Axe** : 4. `validate_csrf` (double-submit, `security/csrf.py:33-35`) est appliqué sur `auth`, `sessions`, `account`, `preferences`, **mais pas** sur les endpoints `/admin/*` (dont le **nouveau** `POST /admin/oui/sync`, `admin_oui_sync.py:31`) ni sur `POST /tools/{tool}/execute` (`tools.py:385`). La protection repose alors **uniquement** sur `SameSite=Lax` du cookie de session (`session.py:168`), qui bloque l'envoi du cookie sur POST cross-site — protection réelle mais sans défense en profondeur, et incohérente avec le reste de l'API. **Remédiation** : appliquer `validate_csrf` (ou un middleware CSRF global pour les méthodes non-sûres) aux mutations admin et tool.

---

### NEW-4 — Autorisation des outils en *default-allow* (low)

**Axe** : 4. Le seed crée `allowed=True` pour **tous les rôles × tous les outils** (`main.py:136-147`) et `_check_tool_access` **auto-crée** une permission `allowed=True` si absente (`tools.py:353-357`). Conséquence : tout nouvel outil (ici `mac_oui`) est **immédiatement exposé aux visiteurs** sans décision explicite ; une défaillance de seed est « auto-réparée » en ouvrant l'accès plutôt qu'en le fermant (fail-open d'autorisation). **Remédiation** : adopter un *default-deny* (auto-création `allowed=False`, ou pas d'auto-création) et documenter l'exposition voulue de chaque outil.

---

### NEW-5 — `PUT /admin/settings` sans allowlist de clés (info)

**Axe** : 9. `update_settings` (`admin_settings.py:48-74`) écrit n'importe quelle clé/valeur `GlobalSetting`, **sans allowlist ni validation de type**, contrairement au chemin module-settings qui valide (`admin_modules.py:117-144`). Un admin (ou une session admin compromise) peut écraser des **clés de contrôle interne** : `oui_sync_running`, `oui_sync_started_at`, compteurs `oui_sync_failures_*`, `MAC_OUI_BACKEND_BATCH_MAX_SIZE` (DoS par valeur géante). Admin-only → **info/durcissement**. **Remédiation** : allowlist des clés modifiables et validation de type/plage côté `/admin/settings`.

---

### CONF-383 / CONF-380 (info) — confirmés

- **#383** : l'ambiguïté n'est calculée que pour `bit_size==24` (`mac_oui_lookup_service.py:204-302`) — déviation fonctionnelle ADR-014, **sans impact sécurité**.
- **#380** : pagination historique vide pour MAC 48-bit (`tools.py:518-621`) — bug de logique, **sans impact sécurité** (donnée IEEE publique, requête paramétrée, `offset/limit` bornés, pas d'IDOR).

---

## 4. Couverture par axe

| # | Axe | Verdict |
|---|-----|---------|
| 1 | **Injection** (SQL / commande / header) | **OK**. SQL 100 % paramétré. Exécuteurs subprocess via `create_subprocess_exec(*args)` sans `shell=True` ; la cible est **résolue en IP validée** par `filter_target` **avant** exec (`ping.py:145-149`, `traceroute.py:267-271`, `ping_ws.py:59-68`). |
| 2 | **ReDoS / DoS** | Regex non vulnérables (front & back). Caps présents (download 50 Mo, batch 2000, timeouts). Voir **NEW-2** (cap longueur par chaîne). |
| 3 | **SSRF** | Sync IEEE **OK** (URLs codées en dur, no-redirect, cap, timeout). Ping/traceroute/DNS-cible filtrés par blocklist (35 plages). Voir **NEW-1** (résolveur DNS). |
| 4 | **AuthN/AuthZ / RBAC / IDOR** | `require_admin` sur tous `/admin/*`. `_check_tool_access` cohérent. Pas d'IDOR (ressources OUI = données publiques). Voir **NEW-3**, **NEW-4**. |
| 5 | **Sessions & cookies** | **OK**. Token CSPRNG 256-bit, HMAC-SHA256 peppéré (ADR-007), comparaison constante (`tokens.py`), cookie `__Host-`/`HttpOnly`/`Secure`/`SameSite=Lax` (`cookies.py`, `session.py:163-172`). Sessions anonymes persistées (ADR-011). |
| 6 | **XSS / sortie** | **OK**. Rendu React échappé, aucun `dangerouslySetInnerHTML` (`MacOuiResultsTable.tsx`), choke-point `sanitize_sample` pour l'écho rejeté, CSP `script-src 'self'` (`security_headers.py`). |
| 7 | **WebSocket** | Origin validé **avant** tout I/O (`tools.py:190-196`), rate-limit WS, auth/permission avant `accept`. Voir **CONF-WS** (`WS_REQUIRE_ORIGIN` défaut `False`). |
| 8 | **Intégrité audit & logs** | `audit_logs.admin_id` nullable + suppression sentinelle « unknown » (migrations/commits récents). Pas de fuite de secret évidente dans les logs. Voir **CONF-382** (masquage de statut). |
| 9 | **Secrets & config** | **OK**. `SECRET_KEY` validé en non-dev (rejet des défauts connus, entropie ≥20 caractères distincts, ≥32 car. — `config.py:47-67`). Voir **NEW-5**. |
| 10 | **Concurrence / intégrité** | CAS atomique nominal OK ; `UNIQUE`/`CHECK` présents **sur les modèles** (testables). Voir **CONF-381**. |
| 11 | **Dépendances** | `httpx` déclaré en runtime (corrigé), `vitest` CVE corrigée. Recommandation : exécuter `pip-audit`/`npm audit` en CI (non vérifié dynamiquement ici → **info**). |
| 12 | **Rate limiting / anti-bruteforce** | Sliding-window Redis (Lua atomique), repli in-memory **fail-open documenté (ADR-005)** → conforme. Double check session+IP visiteurs. |

---

## 5. Conformité ADR / threat model

- **ADR-007 (HMAC sessions)**, **ADR-008 (CSP)**, **ADR-009 (WS origin)**, **ADR-011 (sessions anonymes)**, **ADR-005 (rate-limit fail-open)** : **conformes**.
- **ADR-013 (sync MAC OUI)** : conforme (HTTPS, no-redirect, cap, lock) — sauf race résiduelle **CONF-381**.
- **ADR-014 (regex extraction / zero-trust backend)** : conforme sur l'architecture zero-trust ; déviation fonctionnelle **CONF-383** (flag ambiguïté).
- **Threat model `threat-model.md:137`** : **déviation matérielle** — contrôle « résolveur filtré par blocklist » documenté mais **non implémenté** (voir **NEW-1**). À corriger dans le code et/ou le document.
- Contrainte projet (constraints `UNIQUE`/`CHECK` portées par les **modèles**, pas seulement les migrations) : **respectée** (`mac_oui.py:28-35`, `mac_oui_history.py:27-34`, `oui_sync_log.py:51-63`) → effectivement testable via `metadata.create_all`. Migrations portables `batch_alter_table` confirmées sur l'historique des commits.

---

## 6. Risques résiduels & recommandations (hors blocage merge)

1. **NEW-1 (medium, #385)** — filtrer l'IP du résolveur DNS contre la blocklist + restreindre le paramètre libre ; aligner le threat model. *(pré-existant, à traiter rapidement)*
2. **CONF-382 (medium, #382)** — corriger le masquage de statut avant la release 0.2.0.
3. **CONF-381 (low, #381)** — rendre la réclamation de lock atomique.
4. **NEW-2/3/4/5 (low/info)** — caps de longueur d'entrée (#386), CSRF sur admin/tools (#387), default-deny d'autorisation (#388), allowlist `/admin/settings` (#389).
5. **CONF-WS** — garantir `WS_REQUIRE_ORIGIN=True` en production (checklist de déploiement).
6. **Axe 11** — intégrer `pip-audit` et `npm audit` (non-dev) au pipeline CI comme gate.

---

**Verdict final : GO — accepter avec réserves.** Aucune régression `high`/`critical` introduite par `dev0.2.0-macoui`. Le code MAC OUI est solide sur les axes injection/SSRF/XSS/ReDoS/secrets. Conditionner la *release* 0.2.0 à la correction de **CONF-382** et à l'ouverture/planification d'une issue pour **NEW-1**.

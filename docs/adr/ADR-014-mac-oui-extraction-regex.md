# ADR-014 — MAC OUI Extraction (Frontend-Side, Tolerant)

> **Status:** Proposed
> **Date:** 2026-05-31 (revised after Sprint 0 review)
> **Deciders:** Yann GAUTERON + assistant
> **References:** `functional-spec.md` §3.5.3, `spec-tools-instant.md` §4.4, `docs/adr/ADR-013-mac-oui-sync-strategy.md`

---

## 1. Contexte

L'outil MAC OUI Lookup permet à l'utilisateur de coller du texte arbitraire (output de `arp -a`, `show mac address-table`, export de matériel, etc.) et d'extraire automatiquement les adresses MAC et OUI pour lookup. La question est : **où** se fait l'extraction et **avec quelle politique** (tolérante ou stricte) ?

Cette ADR tranche deux choix structurants :

1. **Localisation de l'extraction** : backend (réception de texte brut, regex serveur) ou frontend (extraction navigateur, envoi d'une liste normalisée) ?
2. **Politique d'extraction** : précision > rappel (réduire les faux positifs) ou rappel > précision (capter tous les patterns possibles) ?

---

## 2. Décisions

### 2.1 Localisation : extraction côté frontend, backend strict

**Décision : le frontend extrait, normalise et envoie une liste d'OUI/MAC au backend. Le backend fait un lookup pur sur valeurs déjà normalisées.**

Architecture :

```
┌──────────────────────────────────────────┐
│ Frontend (MacOuiLookupPage)              │
│  ──────────────────────────────────────  │
│  1. Lit le textarea (texte brut)         │
│  2. Applique la regex tolérante          │
│  3. Normalise → bare hex uppercase       │
│  4. Déduplique                           │
│  5. POST { "ouis": ["001122", ...] }     │
└─────────────────┬────────────────────────┘
                  │
                  ▼
┌──────────────────────────────────────────┐
│ Backend (mac_oui_lookup tool)            │
│  ──────────────────────────────────────  │
│  1. Valide le JSON (sinon → 422)         │
│  2. Valide chaque entrée (format strict) │
│  3. Entrées valides → SELECT en DB       │
│  4. Entrées invalides → "rejected[]"     │
│  5. Retourne 200 OK avec results+rejected│
└──────────────────────────────────────────┘
```

**Format strict accepté par le backend** : bare hex uppercase, longueur ∈ {6, 7, 9, 12} digits. Les séparateurs (`:`, `-`, `.`) sont tolérés à l'entrée mais retirés avant validation. Les chaînes ne respectant pas ce format strict sont rejetées (sans réinterprétation).

**Sécurité du rejet** : voir §2.5.

### 2.2 Politique d'extraction : rappel > précision

**Décision : le frontend est tolérant. Mieux vaut un faux positif (l'utilisateur ignorera le résultat « Unknown vendor ») qu'un faux négatif (l'utilisateur ne comprend pas pourquoi son `00-11-22` n'a pas été reconnu).**

**Raisonnement UX** : l'utilisateur qui colle une sortie CLI souhaite que **tout** ce qui ressemble à une adresse MAC ou un OUI soit traité. Une regex trop stricte qui exclut son format préféré (Cisco 2 groupes, hyphen 3 groupes, bare hex 6 digits) le frustre sans raison technique. Un faux positif (extrait inattendu, lookup « Unknown vendor ») est silencieux et facile à ignorer.

### 2.3 Formats acceptés par le frontend

Les **4 séparateurs** suivants sont acceptés, individuellement ou mélangés :

| Séparateur | Exemple |
|---|---|
| Deux-points `:` | `00:11:22:33:44:55` |
| Tiret `-` | `00-11-22-33-44-55` |
| Point `.` | `0011.2233.4455` |
| Aucun (continu) | `001122334455` |

Les **longueurs acceptées** (en hex digits) :

| Longueur | Nature | Type IEEE potentiel |
|---|---|---|
| 6 | OUI 24-bit | MA-L |
| 7 | OUI 28-bit | MA-M |
| 9 | OUI 36-bit | MA-S |
| 12 | MAC complète 48-bit | — (le préfixe est extrait pour le lookup) |

Les longueurs intermédiaires (8, 10, 11) ne sont **pas standard IEEE** et sont rejetées.

### 2.4 Normalisation côté frontend

Avant envoi au backend :

1. Retirer tous les séparateurs (`:`, `-`, `.`).
2. Convertir en uppercase.
3. Vérifier que la chaîne contient uniquement `[0-9A-F]`.
4. Vérifier que la longueur ∈ {6, 7, 9, 12}.
5. Dédupliquer la liste.

Une entrée qui ne passe pas ces vérifications est **silencieusement ignorée côté frontend** (cas rare : extrait par la regex large mais ne survit pas à la normalisation). Le compteur `parse_stats` reflète ce filtrage.

### 2.5 Format d'affichage MA-M / MA-S

Pour les OUI MA-M (7 digits) et MA-S (9 digits), l'affichage ajoute un marqueur **`_`** (underscore = wildcard universel) pour le digit indéterminé du dernier groupe :

| Type | Digits | Affichage |
|---|---|---|
| MA-L | `001122` | `00:11:22` |
| MA-M | `0011223` | `00:11:22:3_` |
| MA-S | `001122334` | `00:11:22:33:4_` |

Style CSS : l'underscore est rendu en couleur grisée (token `--color-text-secondary`) avec un tooltip *« Ce digit varie selon l'équipement (au-delà du préfixe OUI). »*

Légende sous le tableau (i18n key `tools.mac_oui.legend_partial_byte`) : *« Pour les OUI MA-M et MA-S, le dernier digit indiqué fait partie du préfixe IEEE ; les digits suivants identifient l'équipement et ne sont pas couverts par l'OUI. »*

### 2.6 OUI ambigu (préfixe partiel)

Si l'utilisateur saisit un OUI 6-digit (`00:11:22`) qui **n'existe pas en MA-L** mais dont la valeur correspond au préfixe 24-bit d'au moins une entrée MA-M ou MA-S : le résultat est affiché en **orange** (token `--color-warning`) avec un hint i18n key `tools.mac_oui.ambiguous_partial_oui` : *« Aucun préfixe MA-L trouvé pour `00:11:22`. Ce préfixe est cependant utilisé par des assignations MA-M ou MA-S. Saisissez une adresse MAC complète pour identifier le fabricant précis. »*

Le backend retourne dans la réponse (par entrée résolue) :

```json
{
  "input": "001122",
  "oui_display": "00:11:22",
  "result": null,
  "ambiguous_extends_ma_m": true,
  "ambiguous_extends_ma_s": false
}
```

### 2.7 Politique de rejet backend (zero-trust)

Si une entrée envoyée par le frontend ne respecte pas le format strict (par exemple `"test"`, ou si un attaquant tape directement l'API) :

- **Pas de 422** sur l'entrée invalide. La réponse reste **200 OK** avec résultats partiels.
- Chaque entrée rejetée est listée dans `rejected[]` avec :
  - Sa **position d'index** dans la liste reçue (1-based).
  - Un **extrait sanitisé** : 20 chars max, tout caractère hors `[0-9a-fA-F:.\-]` remplacé par `?`.
  - Une `reason` parmi un enum fermé : `invalid_format`, `invalid_length`, `non_hex_characters`.
- 422 reste réservé au **JSON malformé** (corps non parseable, schéma non respecté).

Exemple :

```json
POST /api/v1/tools/mac_oui/execute
{ "ouis": ["001122", "112233445566", "test<script>"] }

→ 200 OK
{
  "results": [
    {"input": "001122", "oui_display": "00:11:22", "result": {...}},
    {"input": "112233445566", "oui_display": "11:22:33:44:55:66", "result": {...}}
  ],
  "rejected": [
    {"index": 3, "sample": "test?????????", "reason": "invalid_format"}
  ],
  "parse_stats": {"total_inputs": 3, "valid": 2, "rejected": 1, "unique": 2}
}
```

**Sécurité** : la sanitisation borne l'écho à 20 chars et restreint le charset, neutralisant les payloads d'injection. React échappe par défaut côté frontend, et la limitation backend ajoute une seconde ligne de défense. Test obligatoire en Sprint 3 avec payload `<script>alert(1)</script>` → vérifier que `sample` retourné est inoffensif.

---

## 3. Regex frontend (référence)

```ts
// Tous les patterns combinés en une seule alternation.
// Chaque pattern accepte un séparateur uniforme dans la chaîne (4 séparateurs au choix).
const MAC_OUI_REGEX = new RegExp(
  [
    // Format 1: 6 octets séparés par :, -, ., ou rien
    "(?:[0-9A-Fa-f]{2}[:.-]){5}[0-9A-Fa-f]{2}",   // séparé par : ou - ou .
    "[0-9A-Fa-f]{12}",                              // continu (12 digits)
    // Format 2: Cisco 3 groupes de 4
    "(?:[0-9A-Fa-f]{4}\\.){2}[0-9A-Fa-f]{4}",
    // Format 3: OUI 9 digits (MA-S) — toutes notations
    "(?:[0-9A-Fa-f]{2}[:.-]){3}[0-9A-Fa-f]{2}[:.-][0-9A-Fa-f]",
    "[0-9A-Fa-f]{9}",
    // Format 4: OUI 7 digits (MA-M)
    "(?:[0-9A-Fa-f]{2}[:.-]){2}[0-9A-Fa-f]{2}[:.-][0-9A-Fa-f]",
    "[0-9A-Fa-f]{7}",
    // Format 5: OUI 3 octets — toutes notations
    "(?:[0-9A-Fa-f]{2}[:.-]){2}[0-9A-Fa-f]{2}",
    "[0-9A-Fa-f]{6}",
  ].join("|"),
  "g"
);
```

Une **regex finale unique** sera composée en Sprint 4 avec :
- Précédence aux longueurs supérieures (12 → 9 → 7 → 6 hex digits) pour éviter qu'un match 12 digits ne soit tronqué à 6.
- Frontières de mot uniquement sur le bare hex (`\b`) pour empêcher de capter `abc001122334455def`.
- Insensibilité à la casse via flag `i`.

Après extraction, **normalisation** :
- Retrait des séparateurs.
- Conversion en uppercase.
- Validation longueur ∈ {6, 7, 9, 12} (rejet sinon).
- Pour les MAC 12 digits, on extrait **chaque** sous-OUI candidat (3, 7, 9 digits) pour permettre le longest-prefix lookup backend, puis on agrège côté UI sur la MAC d'origine.

### 3.1 Cas particuliers gérés

- **MAC concaténée à du texte** (`abc001122334455def`) : le `\b` sur le bare hex 12 digits empêche le match. Les autres formats avec séparateurs ne sont pas concernés.
- **UUID** (`550e8400-e29b-41d4-a716-446655440000`) : exclu par construction — les groupes UUID font 8/4/4/4/12 digits, pas 2/2/2/2/2/2.
- **IP** (`192.168.1.1`) : non hex (`192` est hex valide mais `168` contient `8` qui est hex, idem pour les autres). Cependant le contexte des `.` avec groupes de tailles variables (`{1,3}`) ne matche pas le format Cisco strict (`{4}.{4}.{4}`).
- **Timestamps `HH:MM:SS`** : peuvent matcher le format 5 (OUI 3 octets). C'est le **faux positif acceptable** par la politique rappel > précision. L'utilisateur verra un résultat « Unknown vendor » et comprendra.

---

## 4. Alternatives considérées

### 4.1 Extraction côté backend vs frontend

| Approche | Avantages | Inconvénients |
|---|---|---|
| **Backend** | Logique centralisée, testable côté serveur | Backend reçoit du texte brut (50 000 chars) → surface d'attaque (ReDoS, injection texte), couplage fort frontend-backend, l'utilisateur ne voit pas ce qui a été extrait avant submit |
| **Frontend** (choisie) | Backend allégé (juste un lookup), feedback immédiat à l'utilisateur (« 12 MAC trouvées »), surface backend minimale (liste de chaînes normalisées) | Logique d'extraction en JavaScript, doit être testée côté frontend |

### 4.2 Politique stricte vs tolérante

| Approche | Avantages | Inconvénients |
|---|---|---|
| Stricte (précision > rappel) | Pas de faux positif visible | Frustration utilisateur : formats courants exclus (hyphen 3 groupes, Cisco 2 groupes, bare hex 6 digits) |
| **Tolérante** (choisie, rappel > précision) | Tout format raisonnable extrait, UX fluide | Quelques faux positifs (timestamps `HH:MM:SS`) → résultat « Unknown vendor », ignoré par l'utilisateur |

### 4.3 Format MA-M / MA-S : représentation du digit partiel

| Marqueur | Conséquence |
|---|---|
| `X.` (point) | Conflit syntaxique : `.` est séparateur de groupe Cisco |
| `X?` (point d'interrogation) | Confusion avec opérateur de requête |
| **`X_` (underscore)** (choisi) | Wildcard SQL universel, ASCII pur, aucune collision |
| `X░` ou autres Unicode | Encodage fragile, peu portable |

---

## 5. Conséquences

### 5.1 Positives

- **UX fluide** : l'utilisateur colle son texte et ça marche, quel que soit le format.
- **Backend minimal** : une seule responsabilité (lookup + validation stricte), surface d'attaque réduite.
- **Zero-trust préservé** : le backend revalide tout ce qu'il reçoit, ne fait confiance à rien.
- **Sécurité** : pas de regex tournant sur 50 000 chars côté serveur. Le ReDoS éventuel reste isolé dans le navigateur de l'utilisateur (peut au pire freezer son onglet).

### 5.2 Négatives

- **Logique d'extraction en JS** : doit être testée côté frontend (Vitest), pas juste pytest. Tests Sprint 4 nettement plus fournis qu'avant.
- **Faux positifs résiduels** : timestamps `HH:MM:SS` peuvent matcher comme OUI 3 octets. Acceptable par construction.
- **Pas d'extraction si JS désactivé** : le tool nécessite JS (déjà le cas du reste du projet — voir `functional-spec.md` §3.7.4).

### 5.3 Risque ReDoS

La regex frontend utilise des quantifiers fixes (`{2}`, `{4}`, `{5}`, `{12}`) et des alternations bornées. **Risque ReDoS nul** côté JS. Test obligatoire en Sprint 4 avec payload pathologique (`"0" * 50_000`).

Côté backend, la regex ne s'applique pas (le backend reçoit déjà la liste normalisée). Le backend valide juste le format hex strict via `re.fullmatch(r"^[0-9A-F]{6,12}$", entry)` — pas de risque ReDoS.

---

## 6. Doutes / arbitrages requis

Les doutes initiaux sont levés. Cette section reste pour traçabilité.

### 6.1 Faux positifs résiduels acceptables

Les timestamps `HH:MM:SS` (ex. `12:34:56`) matchent le format OUI 3 octets. Le résultat affichera « Unknown vendor » et sera ignoré par l'utilisateur. Une amélioration possible (Sprint 4+) : détecter heuristiquement le contexte temporel (présence de patterns `YYYY-MM-DD`, formats de log standard) et signaler dans `parse_stats` le nombre d'entrées qui ressemblent à des timestamps. Hors scope MVP.

### 6.2 Bare hex 8, 10 digits

Ces longueurs (4 octets, 5 octets) ne correspondent à aucune assignation IEEE standard. Elles sont rejetées par la normalisation (longueur hors {6, 7, 9, 12}). Si un besoin émerge, ajouter ces longueurs nécessitera une mise à jour de l'ADR et de la regex.

### 6.3 Précédence dans la regex finale

L'ordre des alternations doit privilégier les longueurs supérieures pour éviter qu'un match 12 digits soit tronqué prématurément à 6 digits. À vérifier en Sprint 4 avec un set de tests exhaustif (le tableau A ci-dessous est un point de départ).

---

## Annexe A — Jeu de test frontend (à étendre en Sprint 4)

### A.1 Cas positifs

| # | Input | OUI(s) extraits (normalisés) |
|---|---|---|
| 1 | `00:11:22:33:44:55` | `001122334455` (MAC 6 octets) |
| 2 | `00-11-22-33-44-55` | `001122334455` |
| 3 | `0011.2233.4455` | `001122334455` |
| 4 | `001122334455` | `001122334455` |
| 5 | `00:11:22` | `001122` (OUI 3 octets) |
| 6 | `00-11-22` | `001122` |
| 7 | `0011.22` | `001122` |
| 8 | `001122` | `001122` |
| 9 | `00:11:22:3` (MA-M) | `0011223` |
| 10 | `00:11:22:33:4` (MA-S) | `001122334` |
| 11 | `0011223` (MA-M continu) | `0011223` |
| 12 | `001122334` (MA-S continu) | `001122334` |
| 13 | `0A:1B:2C:3D:4E:5F` | `0A1B2C3D4E5F` |
| 14 | `0a:1b:2c:3d:4e:5f` | `0A1B2C3D4E5F` (upper-cased) |
| 15 | `MAC: 00:11:22:33:44:55, IP: 192.168.1.1` | `001122334455` |
| 16 | `Server-A 00-11-22-33-44-55\nServer-B 00:11:22:33:44:66` | `001122334455`, `001122334466` |
| 17 | `interface Fa0/1\n mac-address 0011.2233.4455` | `001122334455` |
| 18 | `aa:bb:cc:dd:ee:ff` | `AABBCCDDEEFF` |

### A.2 Cas négatifs

| # | Input | Pourquoi exclu |
|---|---|---|
| 19 | `2026-05-31` | Date ISO (groupes de tailles variables 4-2-2) |
| 20 | `550e8400-e29b-41d4-a716-446655440000` | UUID (groupes 8-4-4-4-12) |
| 21 | `192.168.1.1` | IP (groupes décimaux variables) |
| 22 | `Hello, world!` | Pas de pattern hex |
| 23 | `00:11` | Trop court (< 6 hex digits) |
| 24 | `abc001122334455def` | Bare hex 12 digits non isolé (`\b` rejette) |

### A.3 Cas faux positifs acceptés

| # | Input | Lookup | Politique |
|---|---|---|---|
| 25 | `12:34:56` | Probablement timestamp HH:MM:SS, lookup → « Unknown vendor » | Acceptable, utilisateur ignore |
| 26 | `deadbeef` (bare hex 8 digits) | Rejeté par normalisation (longueur 8 hors {6,7,9,12}) | Pas affiché, comportement attendu |

---

## 7. Références

- `docs/specs/functional-spec.md` §3.5.3 — Supported MAC/OUI Formats
- `docs/specs/technical/spec-tools-instant.md` §4.4 — Pattern Extraction (à corriger : extraction frontend, plus backend)
- `docs/specs/technical/spec-api-contract.md` §10.6 — i18n keys MAC OUI
- `docs/adr/ADR-013-mac-oui-sync-strategy.md` — sync strategy (ADR sœur)

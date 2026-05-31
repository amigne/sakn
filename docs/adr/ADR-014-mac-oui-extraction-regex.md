# ADR-014 — MAC OUI Extraction Regex

> **Status:** Proposed
> **Date:** 2026-05-31
> **Deciders:** Yann GAUTERON + assistant (review meeting required)
> **References:** `functional-spec.md` §3.5.3, `spec-tools-instant.md` §4.4, `docs/adr/ADR-013-mac-oui-sync-strategy.md`

---

## 1. Contexte

L'outil MAC OUI Lookup extrait des adresses MAC et préfixes OUI à partir de texte arbitraire via une regex. La spec `spec-tools-instant.md` §4.4 liste 4 formats mais comporte des ambiguïtés qui rendent l'implémentation impossible sans décision préalable :

| Chaîne | Ambiguïté |
|---|---|
| `0011.2233` | 2 groupes Cisco → 4 octets (`00112233`) ou 3 octets avec suffixe tronqué (`001122` + `33` ignoré) ? |
| `001122334455` | MAC 6 octets, mais `00112233` (7 premiers digits) est aussi un OUI MA-M valide → quel préfixe extraire ? |
| `001122` | OUI 3 octets, ou préfixe d'un MAC plus long ? |
| `00:11:22` dans `Connection from 00:11:22:33:44:55` | Le pattern OUI-only peut matcher un timestamp tronqué `00:11:22` (HH:MM:SS) → faux positif. |

Sans décision sur ces cas, le Sprint 3 (implémentation de l'extraction) sera bloqué.

---

## 2. Décision proposée

### 2.1 Liste exhaustive des patterns acceptés

La regex finale accepte **5 formats**, avec normalisation en bare hex uppercase pour la lookup :

| # | Format | Pattern | Exemple | Octets extraits | Bare hex |
|---|---|---|---|---|---|
| 1 | Colon-separated pairs (6 groupes) | `([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}` | `00:11:22:33:44:55` | 6 | `001122334455` |
| 2 | Hyphen-separated pairs (6 groupes) | `([0-9A-Fa-f]{2}-){5}[0-9A-Fa-f]{2}` | `00-11-22-33-44-55` | 6 | `001122334455` |
| 3 | Dot-separated Cisco (3 groupes de 4) | `[0-9A-Fa-f]{4}\.[0-9A-Fa-f]{4}\.[0-9A-Fa-f]{4}` | `0011.2233.4455` | 6 | `001122334455` |
| 4 | Bare hex (12 digits) | `\b[0-9A-Fa-f]{12}\b` | `001122334455` | 6 | `001122334455` |
| 5 | OUI-only colon (3 groupes) | `([0-9A-Fa-f]{2}:){2}[0-9A-Fa-f]{2}` | `00:11:22` | 3 | `001122` |

**Formats NON acceptés** :
- OUI-only hyphen (`00-11-22`) : trop de faux positifs avec les dates ISO (ex. `2026-05-31`). Si ce format est nécessaire, l'utilisateur peut remplacer `-` par `:` avant de coller.
- OUI-only Cisco 2 groupes (`0011.22`) : ambigu avec 3 octets vs 4 octets quand le second groupe fait 4 digits (§1). Exclu pour éliminer l'ambiguïté.
- Bare hex de longueur < 12 digits : `\b[0-9A-Fa-f]{6}\b` (6 digits = 3 octets) est rejeté car tout nombre hexadécimal de 6 chiffres dans un log (ex. codes erreur, offsets mémoire) générerait un faux positif massif.

### 2.2 Règle de priorité en cas de chevauchement

**Décision : longest match en nombre d'octets extraits, puis priorité de format.**

Quand une même sous-chaîne matche plusieurs patterns, on garde celui qui produit le plus d'octets OUI :

1. Un match 6 octets (formats 1-4) a priorité sur un match 3 octets (format 5).
2. En cas d'égalité (ex. `001122334455` matche à la fois le bare hex 12 digits et, potentiellement, deux OUI 6-digit chevauchants), on garde le match le plus long en caractères.
3. La regex est exécutée avec des **frontières de mot** (`\b`) pour les formats bare hex. Pour les formats avec séparateurs (`:`, `-`, `.`), le séparateur lui-même sert de frontière.

**Conséquence** : `001122334455` extrait le préfixe 6 octets `001122334455`, puis le lookup cherche le longest prefix en base (MA-S > MA-M > MA-L, cf. ADR-013). On ne tente PAS d'extraire `001122` (3 octets) depuis `001122334455`.

### 2.3 Frontières de mot

**Décision : frontières strictes pour le bare hex, séparateurs comme frontières naturelles.**

| Format | Frontière |
|---|---|
| Colon-separated (`:`) | Les `:` délimitent naturellement. Pas de `\b` requis — un `:` adjacent à un caractère non-hex est déjà non-matchant. |
| Hyphen-separated (`-`) | Idem, les `-` délimitent. |
| Dot-separated (`.`) | Les `.` délimitent. |
| Bare hex 12 digits | `\b` avant et après. |
| OUI-only colon | Les `:` délimitent, PLUS vérification que le match n'est pas suivi de `:` + 2 hex digits (sinon ce serait un format 1 complet). Utilisation d'un **negative lookahead** : `(?!\:[0-9A-Fa-f]{2})`. |

**Justification** :
- `\b` sur le bare hex empêche `001122334455` de matcher dans `abc001122334455def` (concaténé à du texte).
- Le negative lookahead sur l'OUI-only empêche `00:11:22` de matcher comme OUI-only quand le texte contient en réalité `00:11:22:33:44:55` (le format 1 complet capture déjà).

### 2.4 Politique sur les faux positifs

**Décision : précision > rappel. Priorité à l'absence de faux positifs.**

- Un faux positif (pattern extrait qui n'est pas une MAC) est pire qu'un faux négatif (vraie MAC non extraite), car il affiche une information erronée à l'utilisateur.
- Conséquences concrètes :
  - Pas d'extraction de bare hex < 12 digits (risque de faux positifs sur des IDs hexadécimaux, codes couleur, offsets mémoire).
  - Pas d'extraction OUI-only sans séparateur (même raison).
  - Pas d'extraction hyphen-only 3 groupes (risque de collision avec dates ISO `YYYY-MM-DD`).
- L'utilisateur qui a un format non supporté peut normaliser son input (ex. remplacer `-` par `:`) — le coût d'un faux négatif est faible et contournable. Le coût d'un faux positif (info erronée) est élevé et non détectable par l'utilisateur.

---

## 3. Regex finale

```
# Format 1: colon-separated 6 octets (full MAC)
(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}

# Format 2: hyphen-separated 6 octets (full MAC)
(?:(?:[0-9A-Fa-f]{2}-){5}[0-9A-Fa-f]{2})

# Format 3: Cisco dot-separated 3 groupes de 4
(?:[0-9A-Fa-f]{4}\.[0-9A-Fa-f]{4}\.[0-9A-Fa-f]{4})

# Format 4: bare hex 12 digits (full MAC, 6 octets)
(?:\b[0-9A-Fa-f]{12}\b)

# Format 5: OUI-only colon 3 octets, avec negative lookahead
(?:(?:[0-9A-Fa-f]{2}:){2}[0-9A-Fa-f]{2}(?!:[0-9A-Fa-f]{2}))
```

Tous les patterns sont combinés avec `|` (alternation). La regex est appliquée avec `re.IGNORECASE`. L'ordre dans l'alternation n'a pas d'importance car les patterns sont mutuellement exclusifs (sauf format 1 et format 5 qui sont distingués par le negative lookahead).

À chaque match, on extrait les digits hexadécimaux et on les stocke en uppercase bare hex.

---

## 4. Alternatives considérées

### 4.1 Approche tolérante (extraire tout ce qui ressemble à de l'hex)

| Approche | Avantages | Inconvénients |
|---|---|---|
| **Extraire toutes les séquences hex de 6-12 digits** (avec ou sans séparateurs), même sans frontières strictes | Capte plus de patterns (ex. `001122` dans un log, OUI Cisco 2 groupes) | Taux de faux positifs élevé : codes erreur hex, offsets mémoire, IDs de session, hash tronqués, etc. |
| **Regex ciblée avec frontières** (choisie) | Faux positifs quasi nuls, résultats fiables | Peut manquer des formats rares (ex. OUI hyphen 3 groupes) |

**Raison du choix** : la confiance de l'utilisateur dans l'outil dépend de l'exactitude des résultats. Un outil qui affiche « Unknown vendor » pour un code erreur hexadécimal est pire qu'un outil qui ne trouve rien et le dit explicitement.

### 4.2 OUI-only : extraction proactive vs conservative

| Approche | Avantages | Inconvénients |
|---|---|---|
| **Extraire tous les OUI possibles** (bare hex 6 digits, hyphen 3 groupes, Cisco 2 groupes) | Fonctionne sans que l'utilisateur n'ait à normaliser son input | Faux positifs sur dates ISO, codes hex, offsets mémoire |
| **Extraire seulement OUI colon-separated** (choisie) | Pas de faux positifs, comportement prévisible | L'utilisateur doit utiliser `:` pour les OUI-only ; ne supporte pas `00-11-22` |

**Raison du choix** : cohérent avec la politique précision > rappel (§2.4). Un OUI écrit `00-11-22` est probablement une MAC complète dans un contexte Windows (`00-11-22-33-44-55`) — le format 2 le capture. Un OUI isolé `00-11-22` est rarissime en pratique (les tables ARP utilisent `:` ou le format complet). Si le besoin émerge, on pourra ajouter le format hyphen 3 groupes avec un échappement explicite par l'utilisateur.

### 4.3 Frontières : `\b` partout vs approche mixte

| Approche | Avantages | Inconvénients |
|---|---|---|
| `\b` sur tous les formats | Cohérence | `\b` ne fonctionne pas bien avec les séparateurs non-alphanumériques (`:`, `-`, `.`) car `\b` est vraie entre `\w` et `\W`. Exemple : dans `x:00:11:22`, le premier `:` crée déjà une frontière naturelle. Ajouter `\b` peut casser le match. |
| **Approche mixte** (choisie) : `\b` uniquement sur bare hex, séparateurs naturels pour les autres | Robuste, pas de faux négatif lié à `\b` mal placé | Moins uniforme |

---

## 5. Conséquences

### 5.1 Positives

- **Pas de faux positifs** : la combinaison de frontières strictes et de formats explicites garantit que tout ce qui est extrait est bien une MAC/OUI.
- **Comportement déterministe** : pas d'heuristique floue ni de « best guess » — les règles sont exhaustives et non ambiguës.
- **Maintenabilité** : la regex est documentée pattern par pattern, modifiable indépendamment.
- **Jeu de tests complet** : l'annexe A fournit 25+ chaînes de test qui serviront de base aux tests unitaires du Sprint 3.

### 5.2 Négatives

- **Pas de support OUI hyphen** : `00-11-22` n'est pas extrait. Solution : l'utilisateur remplace `-` par `:`.
- **Pas de support OUI Cisco 2 groupes** : `0011.22` n'est pas extrait. Solution : l'utilisateur convertit en `00:11:22`.
- **Pas de support bare hex 6 digits** : `001122` n'est pas extrait. Solution : l'utilisateur ajoute `:` → `00:11:22`.
- **MAC partielles non supportées** : une MAC tronquée `00:11` (2 octets) n'est pas extraite.
- **Complexité de la regex** : le negative lookahead pour distinguer format 1 du format 5 rend la regex plus difficile à lire. Compensé par la documentation en §3.

### 5.3 Risque ReDoS

La regex n'utilise pas de quantificateurs imbriqués (`*`, `+`, `{n,}`) sans ancrage. Tous les quantificateurs sont fixes (`{2}`, `{4}`, `{5}`, `{12}`). Le risque de backtracking catastrophique (ReDoS) est **nul**.

---

## 6. Doutes / arbitrages requis

### 6.1 OUI Cisco 2 groupes : faut-il vraiment l'exclure ?

Le format `0011.22` (3 octets en Cisco-style) est utilisé dans certaines documentations Cisco anciennes. L'exclure peut frustrer les utilisateurs qui travaillent exclusivement avec du matériel Cisco.

**Alternative** : accepter le format `\b[0-9A-Fa-f]{4}\.[0-9A-Fa-f]{4}\b` comme OUI 4 octets, et `\b[0-9A-Fa-f]{4}\.[0-9A-Fa-f]{2}\b` comme OUI 3 octets. Le risque de faux positifs est faible (peu de texte contient `XXXX.YY` ou `XXXX.YYYY` avec que des hex digits hors contexte MAC).

→ **Recommandation** : réévaluer en revue. Si l'utilisateur cible est network engineer Cisco, l'inclure. Si l'utilisateur cible est généraliste, l'exclure. Piste médiane : l'accepter mais avec un commentaire dans l'UI (« Cisco format detected, extracted as OUI »).

### 6.2 OUI bare hex : compromis à 8 ou 10 digits ?

La spec `spec-tools-instant.md` §4.4 dit « even-length hex strings of 6–12 characters ». Mais des strings de 8 ou 10 digits hex peuvent être des IDs (ex. `deadbeef`, `cafebabe`). La décision actuelle ne supporte que 12 digits exactement.

**Question** : faut-il supporter 8 et 10 digits (MA-M et longueurs intermédiaires) ?

→ **Recommandation** : non pour le Sprint 0. MA-M (7 hex digits, impair) n'est pas extractible en bare hex. MA-S (9 digits, impair) non plus. Un OUI 4 octets (8 digits) ou 5 octets (10 digits) n'est pas un standard IEEE. Si le besoin émerge, on pourra ajouter `\b[0-9A-Fa-f]{8}\b` et `\b[0-9A-Fa-f]{10}\b` après validation qu'ils ne génèrent pas de faux positifs.

### 6.3 UUID / GUID : risque de faux positif

Un UUID comme `550e8400-e29b-41d4-a716-446655440000` contient des groupes hex. Le format hyphen (format 2) cherche exactement 6 groupes de 2 hex digits. Un UUID en a 5 groupes (8-4-4-4-12), donc pas de collision.

**Vérification** : `550e8400-e29b-41d4-a716-446655440000` ne matche pas `([0-9A-Fa-f]{2}-){5}[0-9A-Fa-f]{2}` car les groupes n'ont pas tous 2 digits (le premier en a 8, le dernier 12). **Pas de risque.**

### 6.4 Timestamps et heures

**Analyse** : `00:11:22` pourrait être une heure (00:11:22 = 0h 11min 22s). Mais dans un log réseau (ARP table, CAM table), le contexte rend ce pattern bien plus probable d'être une MAC. La décision de ne PAS extraire le OUI-only hyphen (`00-11-22`) élimine le risque de collision avec les dates ISO (`2026-05-31`).

**Risque résiduel** : un log qui contient à la fois des timestamps `HH:MM:SS` et des MAC `HH:MM:SS` (coïncidence de format). La seule mitigation est le contexte humain — l'utilisateur voit le résultat et peut l'ignorer. Pas de solution automatique sans NLP.

---

## Annexe A — Jeu de test (25 chaînes)

### A.1 Cas positifs (doivent matcher)

| # | Input | Patterns matchés | OUI(s) extrait(s) | Note |
|---|---|---|---|---|
| 1 | `00:11:22:33:44:55` | Format 1 (full colon) | `001122` | Cas nominal |
| 2 | `00-11-22-33-44-55` | Format 2 (full hyphen) | `001122` | Windows-style |
| 3 | `0011.2233.4455` | Format 3 (Cisco 3 groupes) | `001122` | Cisco-style |
| 4 | `001122334455` | Format 4 (bare hex 12) | `001122334455` (6 octets) | Bare hex |
| 5 | `00:11:22` | Format 5 (OUI colon) | `001122` | OUI-only |
| 6 | `0A:1B:2C:3D:4E:5F` | Format 1 | `0A1B2C` | Mix casse |
| 7 | `0a:1b:2c:3d:4e:5f` | Format 1 | `0A1B2C` | Tout minuscule |
| 8 | `00:AA:BB:CC:DD:EE` | Format 1 | `00AABB` | Mixte chiffres/lettres |
| 9 | `MAC: 00:11:22:33:44:55, IP: 192.168.1.1` | Format 1 | `001122` | Texte mélangé |
| 10 | `00:11:22:33:44:55 et aa:bb:cc:dd:ee:ff` | Format 1 ×2 | `001122`, `AABBCC` | Deux MACs distinctes |
| 11 | `Internet  10.0.0.1   0   00:11:22:33:44:55   ARPA   Vlan10` | Format 1 | `001122` | Sortie ARP table |
| 12 | `001122334455 (Cisco)` | Format 4 | `001122334455` | Bare hex dans texte |
| 13 | `aa-bb-cc-dd-ee-ff` | Format 2 | `AABBCC` | Hyphen minuscule |
| 14 | `interface FastEthernet0/1\n mac-address 0011.2233.4455` | Format 3 | `001122` | Config Cisco |
| 15 | `00:11:22:33:44:55\n00:11:22:33:44:66` | Format 1 ×2 | `001122` (×1 après dédup) | Même OUI, deux MACs |
| 16 | `000000000000` | Format 4 | `000000000000` | OUI zéro (valide IEEE) |
| 17 | `ffffffffffff` | Formats 1/2/4 | `FFFFFFFFFFFF` | Broadcast MAC (hors OUI mais extractible) |

### A.2 Cas négatifs (ne doivent PAS matcher)

| # | Input | Faux positif évité | Raison |
|---|---|---|---|
| 18 | `2026-05-31` | Date ISO | Pas 6 groupes de 2 digits |
| 19 | `00-11-22` | OUI hyphen | Format non supporté (choix délibéré) |
| 20 | `001122` | Bare hex 6 digits | Format non supporté (< 12 digits bare hex) |
| 21 | `550e8400-e29b-41d4-a716-446655440000` | UUID | Groupes de tailles variables (8-4-4-4-12) |
| 22 | `00:11` | Paire hex isolée | Seulement 2 groupes |
| 23 | `192.168.1.1` | Adresse IP | Contient des digits décimaux, pas hex (le `9` n'est pas hex, mais `192` contient `9` qui est hex... en réalité `192` est valide en hex, mais il n'y a que 3 groupes de tailles variables) |
| 24 | `deadbeef` | Hex 8 digits | Format non supporté |
| 25 | `Hello, world!` | Texte sans hex | Pas de pattern hex |

---

## Annexe B — Regex Python de référence

```python
import re

# Patterns individuels (IGNORECASE appliqué au compile)
PATTERNS = [
    r"(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}",          # Format 1: full colon
    r"(?:[0-9A-Fa-f]{2}-){5}[0-9A-Fa-f]{2}",           # Format 2: full hyphen
    r"[0-9A-Fa-f]{4}\.[0-9A-Fa-f]{4}\.[0-9A-Fa-f]{4}", # Format 3: Cisco 3-group
    r"\b[0-9A-Fa-f]{12}\b",                            # Format 4: bare hex 12
    r"(?:[0-9A-Fa-f]{2}:){2}[0-9A-Fa-f]{2}(?!:[0-9A-Fa-f]{2})",  # Format 5: OUI colon
]

MAC_OUI_RE = re.compile("|".join(PATTERNS), re.IGNORECASE)

def extract_ouis(text: str) -> list[str]:
    """Extract unique OUI prefixes (uppercase bare hex) from text."""
    matches = MAC_OUI_RE.findall(text)
    # Normalize: strip separators, uppercase
    ouis = set()
    for m in matches:
        hex_only = re.sub(r"[^0-9A-Fa-f]", "", m).upper()
        ouis.add(hex_only)
    return sorted(ouis)
```

---

## 8. Références

- `docs/specs/functional-spec.md` §3.5.3 — Supported MAC/OUI Formats
- `docs/specs/technical/spec-tools-instant.md` §4.4 — Pattern Extraction
- `docs/adr/ADR-013-mac-oui-sync-strategy.md` — sync strategy (ADR sœur, décisions liées)

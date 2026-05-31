# ADR-013 — MAC OUI Sync Strategy

> **Status:** Proposed
> **Date:** 2026-05-31 (revised after Sprint 0 review)
> **Deciders:** Yann GAUTERON + assistant
> **References:** `functional-spec.md` §3.5, `spec-backend.md` §4.2/§9.6, `spec-tools-instant.md` §4.5

---

## 1. Contexte

La fonctionnalité MAC OUI Lookup repose sur une base locale synchronisée quotidiennement avec les 3 fichiers IEEE :
- MA-L (`oui.txt`) — préfixes 24-bit (6 hex digits)
- MA-M (`mam.txt`) — préfixes 28-bit (7 hex digits)
- MA-S (`oui36.txt`) — préfixes 36-bit (9 hex digits)

Le sync service (`oui_sync_service.py`) télécharge ces fichiers, parse les entrées, et met à jour les tables `MacOui` et `MacOuiHistory`. Quatre décisions structurantes ne sont pas tranchées par les specs existantes :

1. **Protocole de téléchargement** : HTTP vs HTTPS.
2. **Stratégie d'upsert** : que faire quand un OUI change d'organisation entre 2 syncs ?
3. **Classification du `change_type`** : comment distinguer les types de changement à partir de diffs textuels ?
4. **Politique de rétention** : la spec dit « no deletion » — règle stricte ou nuancée ?
5. **Chevauchement entre fichiers** : un préfixe 24-bit peut apparaître à la fois en MA-L et comme préfixe d'assignations MA-M / MA-S. Que stocke-t-on ?

---

## 2. Décisions

### 2.1 Protocole : HTTPS confirmé

**Décision : HTTPS pour tous les téléchargements IEEE.**

Test effectué le 2026-05-31 : les 3 URLs (`https://standards-oui.ieee.org/oui/oui.txt`, `https://standards-oui.ieee.org/oui28/mam.txt`, `https://standards-oui.ieee.org/oui36/oui36.txt`) répondent en HTTP/1.1 200 OK avec TLS valide. `Content-Length` du fichier MA-L : 6 467 392 octets (~6,5 Mo).

Les URLs `http://` mentionnées dans `spec-backend.md` §9.6 et `spec-tools-instant.md` §4.5 sont obsolètes. La spec sera corrigée au Sprint 2.

### 2.2 Stratégie d'upsert

**Décision : comparaison champ par champ avec historisation.**

Pour chaque entrée parsée d'un fichier IEEE :

1. Si l'OUI n'existe pas pour ce `oui_type` → `INSERT` dans `MacOui` avec `first_seen = today`, `last_seen = today`.
2. Si l'OUI existe (`oui`, `oui_type`) avec `organization` ET `address` identiques → `UPDATE last_seen = today`. Aucune ligne d'historique.
3. Si l'OUI existe mais `organization` ou `address` diffère → `INSERT` dans `MacOuiHistory` (cf. §2.3), puis `UPDATE` des champs modifiés dans `MacOui` + `last_seen = today`.
4. Pour les OUIs absents des 3 fichiers : **aucune action** (pas de `DELETE`, pas d'`UPDATE` de `last_seen`).

### 2.3 Classification du `change_type`

**Décision : 3 valeurs, hiérarchie claire.**

| Valeur | Condition de classification |
|---|---|
| `revoked` | Mot-clé `revoked` détecté (insensible à la casse) dans `new_organization` OU `new_organization` réduit à `----` ou vide après trim |
| `name_change` | `organization` modifié (avec ou sans modification d'adresse) — englobe le cas acquisition/fusion |
| `address_change` | `organization` inchangé et `address` modifié uniquement |

**La valeur `reassigned` est abandonnée.** Justification : distinguer une réassignation (transfert à une autre entité légale) d'un changement de nom (même entité, nouvelle raison sociale) nécessiterait une source métier externe que SAKN ne possède pas. Une heuristique automatique serait fragile, et une reclassification manuelle par l'admin n'est pas réaliste (les fabricants exotiques ou de niche échappent à la connaissance générale).

**Cas combiné « nom + adresse changent simultanément »** (ex. Aruba → HPE avec nouveau siège) : classé `name_change`. Les 4 champs `previous_organization`, `new_organization`, `previous_address`, `new_address` sont tous remplis. L'utilisateur voit l'ensemble du diff dans l'UI.

### 2.4 Chevauchement entre fichiers IEEE

**Décision : table unique `MacOui` avec contrainte `UNIQUE(oui, oui_type)`.**

Dans la base IEEE réelle, certains préfixes 24-bit appartiennent à *« IEEE Registration Authority »* et servent de **pool** pour des assignations MA-M / MA-S à de petits fabricants (ex. `8C:1F:64`). Le même préfixe 24-bit apparaît donc simultanément :
- 1 fois dans `oui.txt` (`oui_type=MA-L`, organisation = IEEE Registration Authority),
- N fois dans `mam.txt` / `oui36.txt` (`oui_type=MA-M` ou `MA-S`, organisations = petits fabricants).

La contrainte `UNIQUE(oui, oui_type)` permet de stocker ces 3 occurrences sans duplication. Une simple `UNIQUE(oui)` (telle que la spec backend §4.2 initiale) bloquerait l'insertion.

**Spec corrigée** : `spec-backend.md` §4.2 modifié au Sprint 0 pour refléter cette contrainte.

**Conséquence UX** : si l'utilisateur saisit seulement `8C:1F:64` (sans MAC complète), il verra l'entrée MA-L (« IEEE Registration Authority ») avec une indication visuelle « OUI ambigu » l'invitant à fournir une MAC complète pour identifier le vrai fabricant. Voir AC-MAC-OUI dédiés.

### 2.5 Rétention

**Décision : aucune suppression, jamais.**

- Aucun `DELETE` automatique.
- Aucun outil ni commande CLI de purge. La valeur forensique des données prime sur le coût stockage.
- Justification : la base `MacOui` croît lentement (~50 000 entrées aujourd'hui, ~500-2 000 mouvements par an). La table `MacOuiHistory` croît à ~2 500 lignes/an dans le pire cas. À 10 ans, le volume reste très inférieur au seuil où la purge deviendrait utile.

---

## 3. Alternatives considérées

### 3.1 Tables séparées vs table unique avec `oui_type`

| Approche | Avantages | Inconvénients |
|---|---|---|
| 3 tables (`mac_oui_ma_l`, `mac_oui_ma_m`, `mac_oui_ma_s`) | Requêtes simples sans filtre | 3 jeux de modèles/migrations/services, duplication, jointures complexes pour le lookup longest-prefix |
| **Table unique + `oui_type`** (choisie) | Lookup unifié, une seule table à interroger, `UNIQUE(oui, oui_type)` autorise les chevauchements légitimes | Filtrage `WHERE oui_type =` dans les requêtes admin |

### 3.2 Détection de changement : hash vs comparaison champ par champ

| Approche | Avantages | Inconvénients |
|---|---|---|
| Hash d'entrée (`SHA-256(oui\|org\|address)`) | Comparaison O(1) | Impossible de classifier `change_type` (on ne sait pas quel champ a changé) |
| **Comparaison champ par champ** (choisie) | Permet la classification `name_change` vs `address_change` | Légèrement plus de code |

### 3.3 `change_type` : 4 valeurs vs 3 vs avant/après seul

| Approche | Conséquence |
|---|---|
| 4 valeurs (`name_change`, `address_change`, `revoked`, `reassigned`) | Heuristique `reassigned` non fiable, valeur peu actionnable |
| **3 valeurs** (choisie) | Compromis lisible. L'utilisateur voit `name_change` + le diff complet pour les acquisitions |
| Avant/après seul, sans classification | Minimaliste, l'utilisateur doit interpréter à chaque fois |

### 3.4 Rétention : jamais vs purge automatique vs purge manuelle

| Approche | Conséquence |
|---|---|
| Purge automatique après N années | Perte forensique, complexité, risque de supprimer un OUI qui sera réattribué |
| Commande CLI manuelle (`sakn-cli oui-purge`) | Surface admin supplémentaire, peu de bénéfice |
| **Jamais de suppression** (choisie) | Valeur forensique maximale, croissance maîtrisée |

---

## 4. Conséquences

### 4.1 Positives

- **Traçabilité complète** : chaque changement d'organisation est documenté avec un `change_type` lisible.
- **Lookup unifié** : table unique simplifie le cas d'usage principal.
- **Pas de perte de données** : la politique « never delete » préserve la valeur forensique.
- **Pas de mécanique admin spéciale** : pas de purge à coder, pas de reclassification `reassigned`.

### 4.2 Négatives

- **Pas de distinction `name_change` vs `reassigned`** : un utilisateur lisant l'historique d'une acquisition (ex. Aruba → HPE) voit `name_change` au lieu de `reassigned`. Mitigation : le diff complet est affiché, l'utilisateur peut interpréter.
- **Croissance de `MacOuiHistory`** : ~2 500 lignes/an au maximum. À 10 ans : 25 000 lignes. Acceptable.

### 4.3 Impacts sur les sprints

| Sprint | Impact |
|---|---|
| Sprint 1 (modèles) | Contrainte `UNIQUE(oui, oui_type)` au lieu de `UNIQUE(oui)` |
| Sprint 2 (sync) | HTTPS obligatoire ; comparaison champ par champ ; logique de classification en 3 valeurs |
| Sprint 5 (admin) | Pas de commande de purge à exposer |

---

## 5. Implémentation (sketch)

### 5.1 Contrainte d'unicité

```python
class MacOui(Base):
    __tablename__ = "mac_oui"
    __table_args__ = (
        UniqueConstraint("oui", "oui_type", name="uq_mac_oui_oui_type"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid7)
    oui: Mapped[str] = mapped_column(String(12), nullable=False)
    oui_type: Mapped[str] = mapped_column(String(4), nullable=False)
    organization: Mapped[str] = mapped_column(String(255), nullable=False)
    address: Mapped[str] = mapped_column(Text, nullable=False)
    first_seen: Mapped[date] = mapped_column(Date, nullable=False)
    last_seen: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
```

### 5.2 Classification (pseudo-code)

```python
REVOKED_MARKERS = ("revoked",)  # case-insensitive substring match
def classify_change(old_org: str, new_org: str, old_addr: str, new_addr: str) -> str:
    new_org_norm = new_org.strip()
    if not new_org_norm or new_org_norm == "----" or "revoked" in new_org_norm.lower():
        return "revoked"
    if old_org != new_org:
        return "name_change"  # covers acquisition/fusion (org + address may both change)
    return "address_change"
```

### 5.3 URLs HTTPS

```python
OUI_SOURCES = (
    ("MA-L", "https://standards-oui.ieee.org/oui/oui.txt"),
    ("MA-M", "https://standards-oui.ieee.org/oui28/mam.txt"),
    ("MA-S", "https://standards-oui.ieee.org/oui36/oui36.txt"),
)
```

---

## 6. Doutes / arbitrages requis

Tous les doutes initiaux sont levés. Cette section reste pour traçabilité.

### 6.1 Mot-clé `revoked` : dépendance au format IEEE

La détection du statut `revoked` dépend de la présence du mot `revoked` dans le champ organisation du fichier IEEE. Si IEEE change son format, cette détection cassera silencieusement (tous les `revoked` seront classés `name_change`). Pas de solution robuste sans source externe faisant autorité.

**Mitigation** : monitoring de l'évolution du format IEEE en Sprint 5 (observabilité). Si le format change, un mainteneur ajustera la liste `REVOKED_MARKERS`.

### 6.2 Performance du « longest prefix » sur table unique

Le lookup « longest prefix wins » sur une table unique nécessite de chercher le préfixe 9 digits, puis 7, puis 6, en s'arrêtant au premier hit. Pour ~50 000 lignes avec un index sur `(oui)`, c'est O(log n) × 3 = négligeable.

Stratégie d'optimisation : faire **une seule** requête `SELECT * FROM mac_oui WHERE oui IN (?, ?, ?) AND oui_type IN (?, ?, ?)` avec les 3 préfixes candidats par MAC, puis dédupliquer côté Python en privilégiant le plus long. Évite N requêtes par MAC.

---

## 7. Références

- `docs/specs/functional-spec.md` §3.5.4 — « no deletion, historical entries retained for forensic value »
- `docs/specs/technical/spec-backend.md` §4.2 — MacOui, MacOuiHistory models (corrigé Sprint 0)
- `docs/specs/technical/spec-backend.md` §9.6 — OUI sync logic
- `docs/specs/technical/spec-tools-instant.md` §4.5 — OUI database sync
- `docs/adr/ADR-014-mac-oui-extraction.md` — extraction côté frontend (ADR sœur)

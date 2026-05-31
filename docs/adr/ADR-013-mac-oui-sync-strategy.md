# ADR-013 — MAC OUI Sync Strategy

> **Status:** Proposed
> **Date:** 2026-05-31
> **Deciders:** Yann GAUTERON + assistant (review meeting required)
> **References:** `functional-spec.md` §3.5, `spec-backend.md` §4.2/§9.6, `spec-tools-instant.md` §4.5

---

## 1. Contexte

La fonctionnalité MAC OUI Lookup repose sur une base locale synchronisée quotidiennement avec les 3 fichiers IEEE :
- MA-L (`oui.txt`) — préfixes 24-bit (6 hex digits)
- MA-M (`mam.txt`) — préfixes 28-bit (7 hex digits)
- MA-S (`oui36.txt`) — préfixes 36-bit (9 hex digits)

Le sync service (`oui_sync_service.py`) télécharge ces fichiers, parse les entrées, et met à jour les tables `MacOui` et `MacOuiHistory`. Plusieurs décisions structurantes ne sont pas tranchées par les specs existantes :

1. **Stratégie d'upsert** : que faire quand un OUI change d'organisation entre 2 syncs ?
2. **Classification automatique du `change_type`** : comment distinguer `name_change`, `address_change`, `revoked`, `reassigned` à partir de diffs textuels ?
3. **Politique de rétention** : la spec dit « no deletion » — faut-il confirmer, nuancer, ou prévoir une purge future ?
4. **Chevauchement entre fichiers** : un préfixe MA-M peut couvrir un sous-ensemble d'un préfixe MA-L. Que stocke-t-on ?

---

## 2. Décision proposée

### 2.1 Stratégie d'upsert

**Décision : comparaison champ par champ avec historique.**

Pour chaque entrée parsée d'un fichier IEEE :

1. Si l'OUI n'existe pas en base → `INSERT` dans `MacOui` avec `first_seen = today`, `last_seen = today`.
2. Si l'OUI existe avec `organization` ET `address` identiques → `UPDATE last_seen = today`. Aucune ligne d'historique.
3. Si l'OUI existe mais `organization` ou `address` diffère → `INSERT` dans `MacOuiHistory` avec le `change_type` approprié (voir §2.2), puis `UPDATE` les champs modifiés dans `MacOui` et `last_seen = today`.
4. Pour les OUIs absents des 3 fichiers : aucune action (pas de `DELETE`, pas d'`UPDATE` de `last_seen`).

### 2.2 Classification du `change_type`

**Décision : heuristique conservative avec valeur par défaut explicite.**

| Condition | `change_type` |
|---|---|
| `organization` inchangé, `address` modifié | `address_change` |
| `organization` modifié, OUI présent dans le même fichier IEEE qu'avant | `name_change` |
| `organization` modifié, OUI a changé de fichier IEEE (ex. était dans MA-L, maintenant dans MA-M) | `reassigned` |
| OUI présent dans le fichier IEEE avec une mention de révocation (mot-clé `revoked` ou `----` dans le champ organisation) | `revoked` |
| Toute autre modification | `name_change` (fallback conservateur) |

**Justification** :
- `name_change` vs `reassigned` : la distinction fiable nécessiterait une connaissance métier externe (est-ce la même entité légale qui a changé de nom, ou un nouveau propriétaire ?). La comparaison du type de fichier IEEE (MA-L → MA-M) est un indicateur objectif mais pas infaillible.
- `revoked` : détectable via le mot-clé IEEE standard dans le champ organisation.
- Le fallback `name_change` est choisi comme valeur par défaut la moins engageante (elle n'affirme pas un changement de propriétaire).

### 2.3 Politique de rétention

**Décision : « jamais de suppression automatique », avec purge manuelle admin.**

- **Principe** : la spec §3.5.4 dit « no deletion — historical entries retained for forensic value ». On confirme cette règle.
- **Nuance** : une commande admin manuelle (`sakn-cli oui-purge --older-than <date>`) permettra de purger les entrées non vues depuis N années, pour les déploiements contraints en espace disque. Cette commande n'est PAS automatique et nécessite une action admin explicite.
- **Justification forensique** : un OUI qui disparaît des fichiers IEEE n'est pas « supprimé » — il peut réapparaître (rachat d'entreprise, réattribution). Le conserver permet de répondre à la question « à qui appartenait ce préfixe à la date T ? ».

### 2.4 Chevauchement entre fichiers IEEE

**Décision : 3 tables séparées (une par type OUI) n'est PAS retenu. Table unique `MacOui` avec colonne `oui_type`.**

- Un OUI est identifié par `(oui, oui_type)` — la colonne `oui` seule n'est pas UNIQUE, c'est la paire `(oui, oui_type)` qui est unique.
- Exemple : `001122` peut exister en MA-L et `0011223` en MA-M. Ce sont deux lignes distinctes dans `MacOui`.
- **Contrainte d'unicité** : `UNIQUE (oui, oui_type)`.

---

## 3. Alternatives considérées

### 3.1 Tables séparées vs table unique avec `oui_type`

| Approche | Avantages | Inconvénients |
|---|---|---|
| **3 tables** (`mac_oui_ma_l`, `mac_oui_ma_m`, `mac_oui_ma_s`) | Requêtes simples (pas de filtre `oui_type`), schéma explicite | 3 jeux de modèles/migrations/services, duplication de logique, jointures complexes pour le lookup « longest prefix » |
| **Table unique + `oui_type`** (choisie) | Lookup unifié, une seule table à interroger, `UNIQUE(oui, oui_type)` empêche les doublons inter-fichiers tout en permettant les chevauchements | Filtrage `WHERE oui_type =` dans les requêtes admin, colonne `oui_type` obligatoire |

**Raison du choix** : la spec `spec-backend.md` §4.2 a déjà modélisé une table unique. Le cas d'usage principal (lookup) est simplifié. La contrainte `UNIQUE(oui, oui_type)` est ajoutée par rapport à la spec actuelle qui a `UNIQUE(oui)` — ce point nécessite une correction de spec (documenté en §6).

### 3.2 Détection de changement : hash vs comparaison champ par champ

| Approche | Avantages | Inconvénients |
|---|---|---|
| **Hash d'entrée** (`SHA-256(oui|org|address)`) | Comparaison O(1), simple à implémenter | Ne permet PAS de déterminer quel champ a changé → impossible de classifier `change_type`. Une modification mineure (espace, casse) produit un hash différent. |
| **Comparaison champ par champ** (choisie) | Permet la classification du `change_type` (§2.2), insensible aux changements de casse/espaces si normalisé | Légèrement plus de code Python |

**Raison du choix** : le besoin de classifier `change_type` (`name_change`, `address_change`, etc.) impose de savoir quel champ a changé. Le hash seul ne le permet pas.

### 3.3 Rétention : jamais de suppression vs purge après N années

| Approche | Avantages | Inconvénients |
|---|---|---|
| **Jamais de suppression** (choisie, avec nuance manuelle) | Valeur forensique maximale, cohérent avec la spec §3.5.4 | Croissance illimitée de la table (environ 50 000 entrées aujourd'hui, croissance lente) |
| **Purge automatique après N années** | Contrôle de la taille de la base | Perte de données forensiques, complexité (faut-il aussi purger l'historique ?), risque de supprimer un OUI qui sera réattribué |

**Raison du choix** : la croissance est lente (les OUI IEEE évoluent peu : quelques centaines d'ajouts/modifications par an). La table `MacOui` avec ~50 000 lignes reste petite. La valeur forensique l'emporte sur le gain d'espace. La commande manuelle offre une soupape sans automatiser la destruction de données.

---

## 4. Conséquences

### 4.1 Positives

- **Traçabilité** : chaque changement d'organisation est documenté avec un `change_type` classifié automatiquement.
- **Lookup unifié** : la table unique simplifie le cas d'usage principal (extraire un OUI → chercher dans une seule table).
- **Pas de perte de données** : la politique « never delete » préserve la valeur forensique.
- **Contrainte explicite** : `UNIQUE(oui, oui_type)` empêche les doublons inter-fichiers.

### 4.2 Négatives

- **`change_type` heuristique** : la classification automatique peut se tromper (ex. un `name_change` classé comme `reassigned` si l'OUI change de fichier IEEE). Une reclassification manuelle admin pourrait être nécessaire.
- **Correction de spec nécessaire** : la spec `spec-backend.md` §4.2 a `UNIQUE` sur `oui` seul. Il faut la modifier en `UNIQUE(oui, oui_type)`.
- **Pas de détection automatique des OUI « disparus »** : un OUI retiré des fichiers IEEE sans mention `revoked` reste en base avec son ancien `last_seen`, sans entrée d'historique. Un admin qui consulte la table ne peut pas distinguer un OUI actif d'un OUI disparu sans regarder `last_seen`.
- **Croissance de `MacOuiHistory`** : la table d'historique grandit à chaque changement. Pour ~50 000 OUIs avec un taux de changement faible (< 5%/an), cela reste acceptable (~2 500 lignes/an).

### 4.3 Impacts sur les sprints

| Sprint | Impact |
|---|---|
| Sprint 1 (modèles) | Ajouter `UNIQUE(oui, oui_type)` au modèle `MacOui` |
| Sprint 2 (sync) | Implémenter la comparaison champ par champ + heuristique `change_type` |
| Sprint 6 (admin) | Ajouter la commande `sakn-cli oui-purge` et un endpoint `sync-status` |

---

## 5. Implémentation (sketch)

### 5.1 Contrainte d'unicité corrigée

```python
# MacOui model (spec-backend.md §4.2, corrigé)
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

### 5.2 Logique de sync (pseudo-code)

```python
def classify_change(old_org: str, new_org: str, old_addr: str, new_addr: str,
                    old_file: str, new_file: str) -> str:
    """Classify change_type from diff."""
    if "revoked" in new_org.lower() or new_org.strip() == "----":
        return "revoked"
    if old_org != new_org and old_file != new_file:
        return "reassigned"
    if old_org != new_org:
        return "name_change"
    if old_addr != new_addr:
        return "address_change"
    return "name_change"  # fallback
```

---

## 6. Doutes / arbitrages requis

### 6.1 Correction de spec : `UNIQUE(oui)` → `UNIQUE(oui, oui_type)`

La spec actuelle (`spec-backend.md` §4.2) définit `oui VARCHAR(12) UNIQUE`. Avec la décision de permettre le chevauchement MA-L/MA-M, cette contrainte doit devenir `UNIQUE(oui, oui_type)`. **Ceci est une modification de spec identifiée**, non appliquée (règle du sprint : pas de modification de spec). À valider en revue.

### 6.2 Heuristique `reassigned` : fiabilité faible

La détection de `reassigned` basée sur le changement de fichier IEEE (MA-L → MA-M) est fragile :
- Un OUI peut changer de nom ET de fichier sans changer de propriétaire (réorganisation de la base IEEE).
- Un OUI peut être réassigné à une autre entité tout en restant dans le même fichier.

**Recommandation** : ajouter une colonne `change_type_confirmed BOOLEAN DEFAULT FALSE` dans `MacOuiHistory` pour permettre une reclassification manuelle par un admin. À discuter en revue.

### 6.3 Mot-clé `revoked` : dépendance au format IEEE

La détection du statut `revoked` dépend de la présence du mot `revoked` dans le champ organisation du fichier IEEE. Si IEEE change son format, cette détection cassera silencieusement (tous les `revoked` seront classés `name_change`). Pas de solution robuste sans source externe faisant autorité.

### 6.4 Table unique : performance du « longest prefix »

Le lookup « longest prefix wins » sur une table unique nécessite de chercher le préfixe 9 digits, puis 7, puis 6, en s'arrêtant au premier hit. Pour 50 000 lignes avec un index sur `oui`, c'est O(log n) × 3 = négligeable. Mais si le nombre de OUIs dépasse 500 000 à l'avenir, il faudra re-benchmarker.

### 6.5 Commande de purge manuelle : scope

La commande `sakn-cli oui-purge` proposée en §2.3 n'est pas spécifiée dans les briefs de sprint actuels. Si elle est retenue, il faut l'ajouter au périmètre du Sprint 6 (admin). À défaut, la créer en tant qu'issue de suivi post-MVP.

---

## 7. Références

- `docs/specs/functional-spec.md` §3.5.4 — « no deletion, historical entries retained for forensic value »
- `docs/specs/technical/spec-backend.md` §4.2 — MacOui, MacOuiHistory models
- `docs/specs/technical/spec-backend.md` §9.6 — OUI sync logic
- `docs/specs/technical/spec-tools-instant.md` §4.5 — OUI database sync
- `docs/adr/ADR-014-mac-oui-extraction-regex.md` — extraction regex (ADR sœur, décisions liées)

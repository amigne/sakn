# ADR-016: MAC OUI Sync Failure Email Alerting

## Status
Accepted — 2026-06-03

## Context

`OuiSyncService` maintient un compteur d'échecs consécutifs par fichier IEEE
(MA-L / MA-M / MA-S) et émet un log `error` avec le marker
`ALERT_OUI_SYNC_FAILED_3X` au 3ᵉ échec consécutif (`_handle_failure`).

Jusqu'ici **aucune notification active** n'était envoyée (#373) : un admin
devait lire les logs ou consulter le status modal pour détecter une
dégradation. Or SAKN dispose déjà d'une **infrastructure d'envoi email**
(`app/services/email_service.py::send_email`, utilisée pour la vérification
d'email) — il n'est donc pas nécessaire de construire une nouvelle infra.

## Decision

**Envoyer une alerte email aux administrateurs lors de la transition vers le
3ᵉ échec consécutif d'un fichier IEEE, en réutilisant `send_email`.**

### Règles

- **Déclenchement** : uniquement sur la **transition** `count == 3` (et non à
  chaque échec ≥ 3). Comme une sync réussie remet le compteur à 0, un nouvel
  incident re-déclenchera une alerte — c'est un throttling naturel, sans état
  supplémentaire.
- **Destinataires** : tous les utilisateurs `role=administrator` au statut
  `active`. (Extensible plus tard via une setting `module.mac_oui.alert_recipients`.)
- **Best-effort** : l'envoi est encapsulé dans un `try/except`. Un échec
  d'envoi (SMTP indisponible, erreur réseau) **ne doit jamais** interrompre la
  sync ni masquer le log `ALERT_OUI_SYNC_FAILED_3X` (qui reste la source de
  vérité). `send_email` est déjà un no-op gracieux si `SMTP_HOST` n'est pas
  configuré.
- **Canal** : email (réutilise l'infra existante). Un webhook sortant
  (Slack/Discord) reste une évolution possible mais hors périmètre.

### Contenu

Sujet : `[SAKN] MAC OUI sync failed 3 consecutive times — {file}`
Corps : fichier concerné, horodatage, dernier message d'erreur si disponible,
et lien vers `/admin/modules/mac_oui/status`.

## Consequences

- Les admins sont notifiés activement d'une dégradation de la sync IEEE.
- Aucune nouvelle dépendance ni infra : réutilisation de `send_email`.
- Pas de notification si SMTP non configuré (dégradé propre + warning loggué) —
  le log marker reste disponible pour la supervision.
- L'envoi par destinataire est synchrone (SMTP) dans le job de sync de fond ;
  acceptable vu la rareté de l'événement (3 échecs consécutifs) et le timeout
  court de `send_email` (10 s).

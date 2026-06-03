# ADR-015: Prometheus Metrics for MAC OUI Observability

## Status
Accepted — 2026-06-03

## Context

L'observabilité de la synchronisation MAC OUI et du service de lookup repose
aujourd'hui sur :

1. **Logs structurés JSON** (`oui_sync_started`, `oui_sync_finished`, etc.)
2. **Table `oui_sync_log`** (persistance des runs avec compteurs et statuts)
3. **Endpoint admin** `GET /admin/modules/mac_oui/status` (statut agrégé)

Ces mécanismes permettent le debugging post-mortem et la consultation manuelle,
mais ne permettent pas :

- L'alerting déclaratif (ex. « alerter si > 3 échecs consécutifs sur MA-L »)
- Les dashboards timeseries (durées, volumes, taux d'échec par fichier)
- L'intégration avec une stack de monitoring standard (Prometheus, Grafana)

Le projet n'a pas d'infrastructure de métriques. Le choix de la première
brique doit être simple, léger, et compatible avec les déploiements existants.

## Decision

**Adopter `prometheus_client` comme bibliothèque de métriques, avec exposition
via un endpoint HTTP `/metrics` monté dans FastAPI.**

### Pourquoi Prometheus (plutôt que statsd ou OpenTelemetry) ?

| Critère | Prometheus (`prometheus_client`) | statsd | OpenTelemetry |
|---------|----------------------------------|--------|---------------|
| Dépendance | 1 package Python (~200 KB) | 1 package + daemon statsd | SDK OTel + collector |
| Protocole | HTTP pull (GET /metrics) | UDP push | OTLP (HTTP/gRPC) |
| Intégration FastAPI | `make_asgi_app()` natif | Manuel | `opentelemetry-instrumentation-fastapi` |
| Adoption CNCF | Graduated | N/A | Incubating |
| Complexité infra | Zéro (endpoint HTTP) | Daemon statsd requis | Collector OTel requis |
| Dashboards | Grafana (standard) | Grafana (via plugin) | Grafana / Jaeger |

Prometheus est choisi pour sa simplicité : zéro infrastructure externe, une
dépendance Python légère, et un endpoint HTTP standard directement dans
l'application. C'est le choix le plus adapté à un projet sans stack de
monitoring existante.

### Métriques définies

#### Synchronisation OUI (`oui_sync_*`)

| Nom | Type | Labels |
|-----|------|--------|
| `oui_sync_runs_total` | Counter | `trigger`, `status` |
| `oui_sync_duration_seconds` | Histogram | `trigger` |
| `oui_sync_records_total` | Counter | `change_type` |
| `oui_sync_files_failed` | Gauge | `file` |
| `oui_sync_consecutive_failures` | Gauge | `file` |
| `oui_sync_lock_acquisition_total` | Counter | `outcome` |

#### Lookup MAC OUI (`mac_oui_lookup_*`)

| Nom | Type | Labels |
|-----|------|--------|
| `mac_oui_lookup_requests_total` | Counter | `result` |
| `mac_oui_lookup_duration_seconds` | Histogram | *(aucun)* |

### Conventions de nommage

- Préfixe `oui_sync_` pour les métriques de synchronisation
- Préfixe `mac_oui_` pour les métriques de lookup
- Suffixe `_total` pour les counters (convention Prometheus)
- Suffixe `_seconds` pour les durées (unité de base Prometheus)
- Labels en snake_case, valeurs en minuscules

### Sécurité de l'endpoint `/metrics`

L'endpoint `/metrics` est exposé sans authentification applicative (comme
`/health`). Il expose des métriques agrégées sans PII — aucun label ne
contient d'IP, d'email, d'user_id ou d'identifiant utilisateur. La protection
contre l'accès non autorisé doit être assurée au niveau du **reverse proxy**
(nginx/Caddy/Traefik) via IP allowlist ou basic auth. Ceci est documenté dans
les docs ops.

## Consequences

- Les métriques sont disponibles au format Prometheus sur `GET /metrics`
- Les dashboards Grafana et les alertes Alertmanager peuvent être configurés
  par les opérateurs sans modification du code
- La dépendance `prometheus_client` (~200 KB) est ajoutée aux dépendances
  runtime — impact négligeable sur la taille de l'image Docker
- Les métriques sont réinitialisées à chaque redémarrage du processus
  (comportement standard Prometheus — l'historique est dans la TSDB Prometheus)
- Le module `app/monitoring/metrics.py` centralise toutes les définitions de
  métriques, facilitant l'ajout futur de nouvelles métriques

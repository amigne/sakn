# MAC OUI Lookup — Administration Guide

Audience: SAKN administrators. This guide covers operating the MAC OUI Lookup
module: configuration, the IEEE synchronization, monitoring, on-demand sync,
and log retention.

## Overview

MAC OUI Lookup resolves MAC address prefixes (OUI) to their registered IEEE
organization. The local OUI database is populated from the three IEEE
registries (MA-L, MA-M, MA-S) by a daily background synchronization. The tool
itself performs read-only lookups against this local database.

## Configuration (Admin → Modules → MAC OUI Lookup → ⚙ Settings)

| Setting | Key | Default | Range |
|---|---|---|---|
| Frontend input max chars | `MAC_OUI_FRONTEND_INPUT_MAX_CHARS` | 50000 | 1000–200000 |
| Backend batch max size | `MAC_OUI_BACKEND_BATCH_MAX_SIZE` | 2000 | 100–10000 |
| History page size | `MAC_OUI_HISTORY_PAGE_SIZE` | 10 | 5–50 |
| Sync hour (UTC) | `OUI_SYNC_HOUR` | 3 | 0–23 |
| Sync log retention (days) | `OUI_SYNC_LOG_RETENTION_DAYS` | 365 | 7–3650 |

Settings persist as `module.mac_oui.<KEY>` rows in `global_settings`. Backend
validation rejects out-of-range or non-integer values (HTTP 400). Changing
`OUI_SYNC_HOUR` reschedules the daily job immediately (on the worker that owns
the scheduler).

## Daily IEEE synchronization

- Runs daily at `OUI_SYNC_HOUR` (UTC) via APScheduler (job `oui_sync_daily`).
- Downloads MA-L / MA-M / MA-S over HTTPS, parses, and upserts the local DB.
- Each run appends one row to `oui_sync_log` (started/finished, status, counts).
- A run is skipped if another sync holds the running lock.

### Monitoring (Admin → Modules → MAC OUI Lookup → Status)

The Status modal shows: total OUI records, last run, next scheduled run, the
recent `oui_sync_log` history (last 30), and per-file consecutive failure
counters. After 3 consecutive failures for a file, an `error` log is emitted
with the marker `ALERT_OUI_SYNC_FAILED_3X` (active push notifications — email
or webhook — are tracked separately and not yet implemented).

## On-demand sync (CLI)

To force a synchronization outside the daily schedule (e.g. first
provisioning, or after a failure), use the CLI instead of crafting an
authenticated POST:

```bash
sakn-cli sync-oui
```

Behavior:
- Downloads and syncs all three IEEE registries, recorded in `oui_sync_log`
  with `triggered_by="cli"`.
- Prints the result counts (added / changed / confirmed).
- Exit code `1` if one or more files failed, `0` otherwise. If a sync is
  already running, it reports so and exits `0`.

> Note: the command must run in an environment where the `app` package is
> importable and `DATABASE_URL` points at the SAKN database (same as
> `sakn-cli create-admin`).

## Sync log retention (purge)

`oui_sync_log` grows by at least one row per day. A weekly cleanup job
(`oui_sync_log_cleanup`, Sundays 04:00 UTC) deletes rows older than
`OUI_SYNC_LOG_RETENTION_DAYS`, always preserving the single most recent run so
the Status view never loses the "last run". Lower the retention to keep the
table small; raise it to keep a longer audit trail.

## Related

- ADR-013 — MAC OUI sync strategy (3 change types, `UNIQUE(oui, oui_type)`, HTTPS).
- `docs/qa/acceptance-mac-oui.md` — acceptance criteria.
- `docs/specs/technical/spec-api-contract.md` — API contract.

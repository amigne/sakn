"""Prometheus metrics for SAKN observability (ADR-015).

All metric definitions are centralized here.  Modules that emit metrics
import the relevant objects directly — no global registry access needed.
"""

from prometheus_client import Counter, Gauge, Histogram

# ── OUI Sync ───────────────────────────────────────────────────────────────

oui_sync_runs_total = Counter(
    "oui_sync_runs_total",
    "Total number of OUI sync runs completed.",
    ["trigger", "status"],
)

oui_sync_duration_seconds = Histogram(
    "oui_sync_duration_seconds",
    "Duration of a complete OUI sync run.",
    ["trigger"],
    buckets=(30, 60, 120, 300, 600, 900, 1800, 3600),
)

oui_sync_records_total = Counter(
    "oui_sync_records_total",
    "Number of OUI records processed (added, changed, or confirmed).",
    ["change_type"],
)

oui_sync_files_failed = Gauge(
    "oui_sync_files_failed",
    "Whether the most recent sync of a file failed (1 = failed, 0 = success).",
    ["file"],
)

oui_sync_consecutive_failures = Gauge(
    "oui_sync_consecutive_failures",
    "Number of consecutive failures per IEEE source file.",
    ["file"],
)

oui_sync_lock_acquisition_total = Counter(
    "oui_sync_lock_acquisition_total",
    "Lock acquisition attempts on the OUI sync running flag.",
    ["outcome"],
)

# ── MAC OUI Lookup ─────────────────────────────────────────────────────────

mac_oui_lookup_requests_total = Counter(
    "mac_oui_lookup_requests_total",
    "Number of MAC OUI lookup requests processed.",
    ["result"],
)

mac_oui_lookup_duration_seconds = Histogram(
    "mac_oui_lookup_duration_seconds",
    "Duration of a MAC OUI lookup batch request.",
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0),
)

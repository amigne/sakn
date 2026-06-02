import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import type { ModuleStatus, OuiSyncHistoryEntry } from "@/api/admin/moduleStatus";
import { getModuleStatus, triggerOuiSync } from "@/api/admin/moduleStatus";
import { Badge, Button, Modal, Spinner } from "@/components/ui";

interface MacOuiStatusModalProps {
  open: boolean;
  onClose: () => void;
}

type StatusKind = "running" | "success" | "partial" | "alert" | "idle";

const STATUS_COLOR: Record<StatusKind, string> = {
  running: "bg-blue-500",
  success: "bg-green-500",
  partial: "bg-amber-500",
  alert: "bg-red-500",
  idle: "bg-gray-400",
};

const POLL_INTERVAL_MS = 5000;
const MAX_CONSECUTIVE_ERRORS = 5;
const ERROR_BACKOFF_FACTOR = 2;
const MAX_BACKOFF_MS = 60000;

export default function MacOuiStatusModal({ open, onClose }: MacOuiStatusModalProps) {
  const { t } = useTranslation();
  const [status, setStatus] = useState<ModuleStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [syncing, setSyncing] = useState(false);
  const [syncError, setSyncError] = useState<string | null>(null);
  const [syncSuccess, setSyncSuccess] = useState<string | null>(null);
  const [showConfirm, setShowConfirm] = useState(false);
  const pollTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const errorCountRef = useRef(0);
  const backoffRef = useRef(POLL_INTERVAL_MS);

  const fetchStatus = useCallback(async () => {
    try {
      const data = await getModuleStatus("mac_oui");
      setStatus(data);
      setError(null);
      errorCountRef.current = 0;
      backoffRef.current = POLL_INTERVAL_MS;
    } catch (e) {
      setError(e instanceof Error ? e.message : t("admin.failed_load_modules"));
    } finally {
      setLoading(false);
    }
  }, [t]);

  // Initial load + polling loop
  useEffect(() => {
    if (!open) return;
    setLoading(true);
    setError(null);
    errorCountRef.current = 0;
    backoffRef.current = POLL_INTERVAL_MS;
    fetchStatus();

    return () => {
      if (pollTimerRef.current) {
        clearTimeout(pollTimerRef.current);
        pollTimerRef.current = null;
      }
    };
  }, [open, fetchStatus]);

  // Polling effect: when status is "running", poll every 5s with backoff on error
  useEffect(() => {
    if (!open || !status) return;

    if (pollTimerRef.current) {
      clearTimeout(pollTimerRef.current);
      pollTimerRef.current = null;
    }

    if (status.status === "running") {
      const scheduleNext = () => {
        pollTimerRef.current = setTimeout(async () => {
          try {
            const data = await getModuleStatus("mac_oui");
            setStatus(data);
            setError(null);
            errorCountRef.current = 0;
            backoffRef.current = POLL_INTERVAL_MS;
            if (data && data.status === "running") {
              scheduleNext();
            }
          } catch {
            errorCountRef.current += 1;
            if (errorCountRef.current >= MAX_CONSECUTIVE_ERRORS) {
              setError(t("admin.failed_load_modules"));
              return;
            }
            backoffRef.current = Math.min(backoffRef.current * ERROR_BACKOFF_FACTOR, MAX_BACKOFF_MS);
            pollTimerRef.current = setTimeout(scheduleNext, backoffRef.current);
          }
        }, backoffRef.current);
      };
      scheduleNext();
    }

    return () => {
      if (pollTimerRef.current) {
        clearTimeout(pollTimerRef.current);
        pollTimerRef.current = null;
      }
    };
  }, [open, status?.status, t]);

  const handleTriggerSync = async () => {
    setSyncing(true);
    setSyncError(null);
    setSyncSuccess(null);
    setShowConfirm(false);
    try {
      await triggerOuiSync();
      setSyncSuccess(t("admin.oui_sync.trigger_success"));
      // Immediately refetch to show "running"
      await fetchStatus();
    } catch (e) {
      setSyncError(e instanceof Error ? e.message : t("admin.failed_update_module"));
    } finally {
      setSyncing(false);
    }
  };

  const formatDate = (iso: string | null): string => {
    if (!iso) return "—";
    return new Date(iso).toLocaleString();
  };

  const statusLabel = (kind: StatusKind): string => {
    const keyMap: Record<StatusKind, string> = {
      running: "admin.oui_sync.status_running",
      success: "admin.oui_sync.status_success",
      partial: "admin.oui_sync.status_partial",
      alert: "admin.oui_sync.status_failed",
      idle: "admin.oui_sync.status_idle",
    };
    return t(keyMap[kind]);
  };

  const renderHistoryRow = (entry: OuiSyncHistoryEntry) => (
    <tr key={entry.started_at} className="border-b border-[var(--color-border)] text-xs">
      <td className="px-2 py-1 whitespace-nowrap">{formatDate(entry.started_at)}</td>
      <td className="px-2 py-1 whitespace-nowrap">{formatDate(entry.finished_at)}</td>
      <td className="px-2 py-1">{entry.triggered_by}</td>
      <td className="px-2 py-1 text-center">
        <span
          className={`inline-block h-2 w-2 rounded-full ${STATUS_COLOR[entry.status as StatusKind] ?? "bg-gray-400"}`}
        />
      </td>
      <td className="px-2 py-1 text-center">{entry.added}</td>
      <td className="px-2 py-1 text-center">{entry.changed}</td>
      <td className="px-2 py-1 text-center">{entry.confirmed}</td>
      <td className="px-2 py-1">{(entry.files_failed ?? []).join(", ") || "—"}</td>
    </tr>
  );

  return (
    <Modal open={open} onClose={onClose} title={t("admin.oui_sync.title")}>
      <div className="space-y-4">
        {/* Loading */}
        {loading && (
          <div className="flex justify-center py-4">
            <Spinner />
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="p-3 rounded bg-red-50 dark:bg-red-950 text-sm text-red-700 dark:text-red-300">{error}</div>
        )}

        {/* Status */}
        {status && !loading && (
          <>
            {/* Summary */}
            <div className="flex items-center gap-2">
              <span className={`inline-block h-3 w-3 rounded-full ${STATUS_COLOR[status.status]}`} />
              <span className="text-sm font-semibold text-[var(--color-text)]">{statusLabel(status.status)}</span>
              <span className="text-xs text-[var(--color-text-secondary)]">({status.total_records} records)</span>
            </div>

            {/* Last run */}
            <div className="text-xs text-[var(--color-text-secondary)] space-y-1">
              <p>
                <span className="font-medium">{t("admin.oui_sync.last_run")}:</span>{" "}
                {status.last_run ? formatDate(status.last_run.started_at) : "—"}
              </p>
              <p>
                <span className="font-medium">{t("admin.oui_sync.next_run")}:</span>{" "}
                {formatDate(status.next_scheduled_run)}
              </p>
            </div>

            {/* Per-file consecutive failures */}
            <div className="space-y-1">
              <p className="text-xs font-semibold text-[var(--color-text-secondary)]">
                {t("admin.oui_sync.consecutive_failures")}:
              </p>
              {Object.entries(status.consecutive_failures).map(([file, count]) => (
                <div key={file} className="flex items-center gap-2 text-xs">
                  <span className="font-mono w-12 text-[var(--color-text)]">{file}</span>
                  <Badge variant={count >= 3 ? "error" : count >= 1 ? "warning" : "neutral"}>{count}</Badge>
                </div>
              ))}
            </div>

            {/* Counters */}
            {status.last_run && (
              <div className="flex gap-4 text-xs text-[var(--color-text-secondary)]">
                <span>
                  {t("admin.oui_sync.added")}:{" "}
                  <strong className="text-[var(--color-text)]">{status.last_run.added}</strong>
                </span>
                <span>
                  {t("admin.oui_sync.changed")}:{" "}
                  <strong className="text-[var(--color-text)]">{status.last_run.changed}</strong>
                </span>
                <span>
                  {t("admin.oui_sync.confirmed")}:{" "}
                  <strong className="text-[var(--color-text)]">{status.last_run.confirmed}</strong>
                </span>
              </div>
            )}

            {/* Trigger button */}
            <div className="flex items-center gap-2">
              {!showConfirm ? (
                <Button
                  size="sm"
                  variant="primary"
                  disabled={syncing || status.status === "running"}
                  onClick={() => setShowConfirm(true)}
                >
                  {syncing ? <Spinner size="sm" /> : null}
                  {t("admin.oui_sync.trigger_button")}
                </Button>
              ) : (
                <div className="flex items-center gap-2 text-xs">
                  <span className="text-[var(--color-text-secondary)]">{t("admin.oui_sync.trigger_confirm")}</span>
                  <Button size="sm" variant="primary" disabled={syncing} onClick={handleTriggerSync}>
                    {t("admin.confirm")}
                  </Button>
                  <Button size="sm" variant="secondary" onClick={() => setShowConfirm(false)}>
                    {t("common.cancel")}
                  </Button>
                </div>
              )}
              {syncSuccess && <span className="text-xs text-green-600">{syncSuccess}</span>}
              {syncError && <span className="text-xs text-red-600">{syncError}</span>}
            </div>

            {/* History table */}
            {status.history && status.history.length > 0 && (
              <div>
                <p className="text-xs font-semibold text-[var(--color-text-secondary)] mb-2">
                  {t("admin.oui_sync.history_title")}
                </p>
                <div className="max-h-64 overflow-y-auto">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="border-b border-[var(--color-border)]">
                        <th
                          scope="col"
                          className="px-2 py-1 text-start text-[var(--color-text-secondary)] font-semibold"
                        >
                          {t("admin.oui_sync.last_run")}
                        </th>
                        <th
                          scope="col"
                          className="px-2 py-1 text-start text-[var(--color-text-secondary)] font-semibold"
                        >
                          Finished
                        </th>
                        <th
                          scope="col"
                          className="px-2 py-1 text-start text-[var(--color-text-secondary)] font-semibold"
                        >
                          Trigger
                        </th>
                        <th
                          scope="col"
                          className="px-2 py-1 text-center text-[var(--color-text-secondary)] font-semibold w-8"
                        >
                          St.
                        </th>
                        <th
                          scope="col"
                          className="px-2 py-1 text-center text-[var(--color-text-secondary)] font-semibold"
                        >
                          {t("admin.oui_sync.added")}
                        </th>
                        <th
                          scope="col"
                          className="px-2 py-1 text-center text-[var(--color-text-secondary)] font-semibold"
                        >
                          {t("admin.oui_sync.changed")}
                        </th>
                        <th
                          scope="col"
                          className="px-2 py-1 text-center text-[var(--color-text-secondary)] font-semibold"
                        >
                          {t("admin.oui_sync.confirmed")}
                        </th>
                        <th
                          scope="col"
                          className="px-2 py-1 text-start text-[var(--color-text-secondary)] font-semibold"
                        >
                          {t("admin.oui_sync.failed_files")}
                        </th>
                      </tr>
                    </thead>
                    <tbody>{status.history.map(renderHistoryRow)}</tbody>
                  </table>
                </div>
              </div>
            )}

            {status.status === "idle" && (
              <p className="text-xs text-[var(--color-text-secondary)] italic">{t("admin.oui_sync.no_data")}</p>
            )}
          </>
        )}
      </div>
    </Modal>
  );
}

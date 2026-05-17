import { useState, useEffect, useCallback, useRef } from "react";
import { useNavigate } from "react-router-dom";
import AdminLayout from "@/components/admin/AdminLayout";
import { Select, ToggleSwitch, Pagination, Badge, Spinner } from "@/components/ui";
import { listToolExecutions, listSecurityEvents, listAuditLogs } from "@/services/admin";
import { useAuthStore } from "@/stores/authStore";
import { toolDisplayName, auditActionLabel, auditDetail, type ToolExecutionLog, type SecurityEventLog, type AuditLog, type Pagination as PaginationType } from "@/types/admin";

type LogTab = "tool-executions" | "security-events" | "audit";

const PAGE_SIZES = [10, 25, 50, 100, 200, 500, 1000];
const PREF_KEY_PAGE_SIZE = "admin_logs_page_size";
const PREF_KEY_AUTO_REFRESH = "admin_logs_auto_refresh";

function fmtDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

function UserCell({ email, onClick }: { email: string | null; userId?: string | null; onClick?: () => void }) {
  if (!email) return <span className="italic text-[var(--color-text-secondary)]">[Guest]</span>;
  return (
    <span
      className={`text-[var(--color-text)] max-w-[140px] truncate block${onClick ? " cursor-pointer hover:text-primary-600 hover:underline" : ""}`}
      title={email}
      onClick={onClick}
    >
      {email}
    </span>
  );
}

function getSecurityBadgeVariant(eventType: string): "error" | "warning" | "info" | "success" {
  const t = eventType.toLowerCase();
  if (t.includes("blocked") || t.includes("brute") || t.includes("failed") || t.includes("mismatch")) return "error";
  if (t.includes("rate") || t.includes("limit") || t.includes("lockout") || t.includes("locked")) return "warning";
  if (t.includes("success") || t.includes("verified") || t.includes("login_success")) return "success";
  return "info";
}

export default function AdminLogsPage() {
  const navigate = useNavigate();
  const preferences = useAuthStore((s) => s.preferences);
  const savePreferences = useAuthStore((s) => s.savePreferences);
  const isInitialized = useAuthStore((s) => s.isInitialized);

  const [tab, setTab] = useState<LogTab>("tool-executions");
  const [toolFilter, setToolFilter] = useState("all");
  const [autoRefresh, setAutoRefresh] = useState(false);
  const [limit, setLimit] = useState(10);
  const [prefsApplied, setPrefsApplied] = useState(false);

  // Apply saved preferences once they're loaded
  useEffect(() => {
    if (!isInitialized || prefsApplied) return;
    const prefMap = (preferences as unknown as Record<string, string>) || {};
    const savedPageSize = parseInt(prefMap[PREF_KEY_PAGE_SIZE] || "10", 10);
    if (PAGE_SIZES.includes(savedPageSize)) setLimit(savedPageSize);
    if (prefMap[PREF_KEY_AUTO_REFRESH] === "true") setAutoRefresh(true);
    setPrefsApplied(true);
  }, [isInitialized, preferences, prefsApplied]);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(false); // Start false, only fetch after prefs applied
  const [error, setError] = useState<string | null>(null);

  const [toolLogs, setToolLogs] = useState<ToolExecutionLog[]>([]);
  const [securityLogs, setSecurityLogs] = useState<SecurityEventLog[]>([]);
  const [auditLogs, setAuditLogs] = useState<AuditLog[]>([]);
  const [pagination, setPagination] = useState<PaginationType>({ offset: 0, limit: 10, total: 0 });

  const refreshTimer = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchLogs = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params: Record<string, string | number> = { offset, limit };
      if (toolFilter !== "all") params.tool = toolFilter;
      if (tab === "tool-executions") {
        const data = await listToolExecutions(params as never);
        setToolLogs(data.tool_executions);
        setPagination(data.pagination);
      } else if (tab === "security-events") {
        const data = await listSecurityEvents(params as never);
        setSecurityLogs(data.security_events);
        setPagination(data.pagination);
      } else {
        const data = await listAuditLogs(params as never);
        setAuditLogs(data.audit_logs);
        setPagination(data.pagination);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load logs");
    } finally {
      setLoading(false);
    }
  }, [tab, offset, limit, toolFilter]);

  useEffect(() => {
    if (isInitialized && prefsApplied) fetchLogs();
  }, [fetchLogs, isInitialized, prefsApplied]);

  useEffect(() => {
    if (autoRefresh) { refreshTimer.current = setInterval(fetchLogs, 5000); }
    return () => { if (refreshTimer.current) { clearInterval(refreshTimer.current); refreshTimer.current = null; } };
  }, [autoRefresh, fetchLogs]);

  const handleTabChange = (t: LogTab) => { setTab(t); setOffset(0); setToolFilter("all"); };

  const handleLimitChange = (val: string) => {
    const n = parseInt(val, 10);
    setLimit(n);
    setOffset(0);
    savePreferences({ [PREF_KEY_PAGE_SIZE]: val } as never);
  };

  const handleAutoRefreshChange = (v: boolean) => {
    setAutoRefresh(v);
    savePreferences({ [PREF_KEY_AUTO_REFRESH]: v ? "true" : "false" } as never);
  };

  return (
    <AdminLayout title="Log Viewer">
      <div className="card p-4">
        <div className="flex flex-wrap items-center gap-3 mb-4">
          <div className="flex items-center gap-1 rounded bg-[var(--color-surface-alt)] p-0.5">
            {(["tool-executions", "security-events", "audit"] as LogTab[]).map((t) => (
              <button key={t} onClick={() => handleTabChange(t)}
                className={`px-3 py-1 text-xs rounded font-medium transition-colors ${
                  tab === t ? "bg-[var(--color-surface)] text-[var(--color-text)] shadow-sm"
                  : "text-[var(--color-text-secondary)] hover:text-[var(--color-text)]"}`}>
                {t === "tool-executions" ? "Tool Executions" : t === "security-events" ? "Security Events" : "Audit"}
              </button>
            ))}
          </div>
          {tab === "tool-executions" && (
            <Select options={[
              { value: "all", label: "All Tools" }, { value: "ping", label: "Ping" },
              { value: "traceroute", label: "Traceroute" }, { value: "dns_lookup", label: "DNS Lookup" },
              { value: "ssl_viewer", label: "TLS Viewer" },
            ]} value={toolFilter} onChange={(v) => { setToolFilter(v); setOffset(0); }} ariaLabel="Filter by tool" />
          )}
          <ToggleSwitch checked={autoRefresh} onChange={handleAutoRefreshChange} label="Auto-refresh" />
          <div className="flex items-center gap-1 ml-auto">
            <span className="text-xs text-[var(--color-text-secondary)]">Rows:</span>
            <Select options={PAGE_SIZES.map((n) => ({ value: String(n), label: String(n) }))}
              value={String(limit)} onChange={handleLimitChange} ariaLabel="Rows per page" />
          </div>
        </div>

        {error && <div className="mb-4 p-3 rounded bg-red-50 dark:bg-red-950 text-sm text-red-700 dark:text-red-300">{error}</div>}
        {loading ? <div className="flex justify-center py-12"><Spinner /></div> : (
          <>

            {/* ── Tool Executions ──────────────────────────────── */}
            {tab === "tool-executions" && (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-[var(--color-border)]">
                      <th className="px-3 py-2 text-start text-xs font-semibold text-[var(--color-text-secondary)] uppercase whitespace-nowrap">Date / Time</th>
                      <th className="px-3 py-2 text-start text-xs font-semibold text-[var(--color-text-secondary)] uppercase">Username</th>
                      <th className="px-3 py-2 text-start text-xs font-semibold text-[var(--color-text-secondary)] uppercase">IP</th>
                      <th className="px-3 py-2 text-start text-xs font-semibold text-[var(--color-text-secondary)] uppercase">Tool</th>
                      <th className="px-3 py-2 text-start text-xs font-semibold text-[var(--color-text-secondary)] uppercase hidden md:table-cell">Query</th>
                      <th className="px-3 py-2 text-start text-xs font-semibold text-[var(--color-text-secondary)] uppercase hidden md:table-cell">Result</th>
                      <th className="px-3 py-2 text-end text-xs font-semibold text-[var(--color-text-secondary)] uppercase hidden lg:table-cell">Duration</th>
                    </tr>
                  </thead>
                  <tbody>
                    {toolLogs.length === 0 ? (
                      <tr><td colSpan={7} className="px-3 py-8 text-center text-[var(--color-text-secondary)]">No logs found.</td></tr>
                    ) : toolLogs.map((log) => {
                      const isSuccess = log.result === "success";
                      const isPartial = log.result === "partial";
                      return (
                        <tr key={log.id} className="border-b border-[var(--color-border)] hover:bg-[var(--color-surface-alt)]">
                          <td className="px-3 py-2 text-[var(--color-text-secondary)] text-xs whitespace-nowrap">{new Date(log.created_at).toLocaleString()}</td>
                          <td className="px-3 py-2">
                            <UserCell email={log.user_email} userId={log.user_id}
                              onClick={log.user_id ? () => navigate(`/admin/users/${log.user_id}`) : undefined} />
                          </td>
                          <td className="px-3 py-2 font-mono text-[var(--color-text)] text-xs">{log.source_ip}</td>
                          <td className={`px-3 py-2 font-medium text-[var(--color-text)] ${isSuccess ? "max-md:text-success-600 max-md:dark:text-success-500" : isPartial ? "max-md:text-warning-600 max-md:dark:text-warning-500" : "max-md:text-error-600 max-md:dark:text-error-500"}`}>
                            {toolDisplayName(log.tool_name)}
                          </td>
                          <td className="px-3 py-2 text-[var(--color-text)] text-xs font-mono max-w-[200px] truncate hidden md:table-cell" title={log.query}>{log.query || "—"}</td>
                          <td className="px-3 py-2 hidden md:table-cell"><Badge variant={isSuccess ? "success" : isPartial ? "warning" : "error"}>{log.result}</Badge></td>
                          <td className="px-3 py-2 text-end font-mono text-[var(--color-text)] text-xs hidden lg:table-cell">{fmtDuration(log.duration_ms)}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}

            {/* ── Security Events ─────────────────────────────── */}
            {tab === "security-events" && (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-[var(--color-border)]">
                      <th className="px-3 py-2 text-start text-xs font-semibold text-[var(--color-text-secondary)] uppercase whitespace-nowrap">Date / Time</th>
                      <th className="px-3 py-2 text-start text-xs font-semibold text-[var(--color-text-secondary)] uppercase">Username</th>
                      <th className="px-3 py-2 text-start text-xs font-semibold text-[var(--color-text-secondary)] uppercase">IP</th>
                      <th className="px-3 py-2 text-start text-xs font-semibold text-[var(--color-text-secondary)] uppercase">Event</th>
                    </tr>
                  </thead>
                  <tbody>
                    {securityLogs.length === 0 ? (
                      <tr><td colSpan={4} className="px-3 py-8 text-center text-[var(--color-text-secondary)]">No events found.</td></tr>
                    ) : securityLogs.map((log) => (
                      <tr key={log.id} className="border-b border-[var(--color-border)] hover:bg-[var(--color-surface-alt)]">
                        <td className="px-3 py-2 text-[var(--color-text-secondary)] text-xs whitespace-nowrap">{new Date(log.created_at).toLocaleString()}</td>
                        <td className="px-3 py-2">
                          <UserCell email={log.user_email} userId={log.user_id}
                            onClick={log.user_id ? () => navigate(`/admin/users/${log.user_id}`) : undefined} />
                        </td>
                        <td className="px-3 py-2 font-mono text-[var(--color-text)] text-xs">{log.source_ip || log.ip_address || "-"}</td>
                        <td className="px-3 py-2"><Badge variant={getSecurityBadgeVariant(log.event_type)}>{log.event_type.replace(/_/g, " ")}</Badge></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {/* ── Audit ────────────────────────────────────────── */}
            {tab === "audit" && (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-[var(--color-border)]">
                      <th className="px-3 py-2 text-start text-xs font-semibold text-[var(--color-text-secondary)] uppercase whitespace-nowrap">Date / Time</th>
                      <th className="px-3 py-2 text-start text-xs font-semibold text-[var(--color-text-secondary)] uppercase">Admin</th>
                      <th className="px-3 py-2 text-start text-xs font-semibold text-[var(--color-text-secondary)] uppercase">Action</th>
                      <th className="px-3 py-2 text-start text-xs font-semibold text-[var(--color-text-secondary)] uppercase hidden md:table-cell">Details</th>
                    </tr>
                  </thead>
                  <tbody>
                    {auditLogs.length === 0 ? (
                      <tr><td colSpan={4} className="px-3 py-8 text-center text-[var(--color-text-secondary)]">No audit entries found.</td></tr>
                    ) : auditLogs.map((log) => {
                      const detail = auditDetail(log);
                      return (
                        <tr key={log.id} className="border-b border-[var(--color-border)] hover:bg-[var(--color-surface-alt)]">
                          <td className="px-3 py-2 text-[var(--color-text-secondary)] text-xs whitespace-nowrap">{new Date(log.created_at).toLocaleString()}</td>
                          <td className="px-3 py-2">
                            <UserCell email={log.admin_email} userId={log.admin_id}
                              onClick={log.admin_id ? () => navigate(`/admin/users/${log.admin_id}`) : undefined} />
                          </td>
                          <td className="px-3 py-2 text-[var(--color-text)]">{auditActionLabel(log.action)}</td>
                          <td className="px-3 py-2 text-[var(--color-text-secondary)] text-xs hidden md:table-cell">{detail || "—"}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}

            <div className="mt-4 flex flex-wrap items-center justify-between gap-2">
              <span className="text-xs text-[var(--color-text-secondary)]">{pagination.total.toLocaleString()} entries</span>
              <Pagination offset={offset} limit={limit} total={pagination.total} onChange={setOffset} />
            </div>
          </>
        )}
      </div>
    </AdminLayout>
  );
}

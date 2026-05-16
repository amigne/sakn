import { useState, useEffect, useCallback, useRef } from "react";
import AdminLayout from "@/components/admin/AdminLayout";
import { Select, ToggleSwitch, Pagination, Badge, Spinner } from "@/components/ui";
import { listToolExecutions, listSecurityEvents, listAuditLogs } from "@/services/admin";
import type { ToolExecutionLog, SecurityEventLog, AuditLog, Pagination as PaginationType } from "@/types/admin";
import { toolDisplayName } from "@/types/admin";

type LogTab = "tool-executions" | "security-events" | "audit";

export default function AdminLogsPage() {
  const [tab, setTab] = useState<LogTab>("tool-executions");
  const [toolFilter, setToolFilter] = useState("all");
  const [autoRefresh, setAutoRefresh] = useState(false);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [toolLogs, setToolLogs] = useState<ToolExecutionLog[]>([]);
  const [securityLogs, setSecurityLogs] = useState<SecurityEventLog[]>([]);
  const [auditLogs, setAuditLogs] = useState<AuditLog[]>([]);
  const [pagination, setPagination] = useState<PaginationType>({ offset: 0, limit: 10, total: 0 });

  const limit = 10;
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
  }, [tab, offset, toolFilter]);

  useEffect(() => {
    fetchLogs();
  }, [fetchLogs]);

  useEffect(() => {
    if (autoRefresh) {
      refreshTimer.current = setInterval(fetchLogs, 5000);
    }
    return () => {
      if (refreshTimer.current) {
        clearInterval(refreshTimer.current);
        refreshTimer.current = null;
      }
    };
  }, [autoRefresh, fetchLogs]);

  const handleTabChange = (t: LogTab) => {
    setTab(t);
    setOffset(0);
    setToolFilter("all");
  };

  return (
    <AdminLayout title="Log Viewer">
      <div className="card p-4">
        <div className="flex flex-wrap items-center gap-3 mb-4">
          <div className="flex items-center gap-1 rounded bg-[var(--color-surface-alt)] p-0.5">
            {(["tool-executions", "security-events", "audit"] as LogTab[]).map((t) => (
              <button
                key={t}
                onClick={() => handleTabChange(t)}
                className={`px-3 py-1 text-xs rounded font-medium transition-colors ${
                  tab === t
                    ? "bg-[var(--color-surface)] text-[var(--color-text)] shadow-sm"
                    : "text-[var(--color-text-secondary)] hover:text-[var(--color-text)]"
                }`}
              >
                {t === "tool-executions" ? "Tool Executions" : t === "security-events" ? "Security Events" : "Audit"}
              </button>
            ))}
          </div>

          {tab === "tool-executions" && (
            <Select
              options={[
                { value: "all", label: "All Tools" },
                { value: "ping", label: "Ping" },
                { value: "traceroute", label: "Traceroute" },
                { value: "dns_lookup", label: "DNS" },
                { value: "ssl_viewer", label: "TLS" },
              ]}
              value={toolFilter}
              onChange={(v) => { setToolFilter(v); setOffset(0); }}
              ariaLabel="Filter by tool"
            />
          )}

          <ToggleSwitch checked={autoRefresh} onChange={setAutoRefresh} label="Auto-refresh" />
        </div>

        {error && (
          <div className="mb-4 p-3 rounded bg-red-50 dark:bg-red-950 text-sm text-red-700 dark:text-red-300">{error}</div>
        )}

        {loading ? (
          <div className="flex justify-center py-12"><Spinner /></div>
        ) : (
          <>
            {/* Tool Executions Table */}
            {tab === "tool-executions" && (
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-[var(--color-border)]">
                    <th className="px-3 py-2 text-start text-xs font-semibold text-[var(--color-text-secondary)] uppercase">Tool</th>
                    <th className="px-3 py-2 text-start text-xs font-semibold text-[var(--color-text-secondary)] uppercase">IP</th>
                    <th className="px-3 py-2 text-start text-xs font-semibold text-[var(--color-text-secondary)] uppercase">Result</th>
                    <th className="px-3 py-2 text-end text-xs font-semibold text-[var(--color-text-secondary)] uppercase">Duration</th>
                    <th className="px-3 py-2 text-start text-xs font-semibold text-[var(--color-text-secondary)] uppercase">Date</th>
                  </tr>
                </thead>
                <tbody>
                  {toolLogs.length === 0 ? (
                    <tr><td colSpan={5} className="px-3 py-8 text-center text-[var(--color-text-secondary)]">No logs found.</td></tr>
                  ) : (
                    toolLogs.map((log) => (
                      <tr key={log.id} className="border-b border-[var(--color-border)] hover:bg-[var(--color-surface-alt)]">
                        <td className="px-3 py-2 font-medium text-[var(--color-text)]">{toolDisplayName(log.tool_name)}</td>
                        <td className="px-3 py-2 font-mono text-[var(--color-text)]">{log.source_ip}</td>
                        <td className="px-3 py-2">
                          <Badge variant={log.result === "success" ? "success" : "error"}>{log.result}</Badge>
                        </td>
                        <td className="px-3 py-2 text-end font-mono text-[var(--color-text)]">{log.duration_ms}ms</td>
                        <td className="px-3 py-2 text-[var(--color-text-secondary)] text-xs">{new Date(log.created_at).toLocaleString()}</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            )}

            {/* Security Events Table */}
            {tab === "security-events" && (
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-[var(--color-border)]">
                    <th className="px-3 py-2 text-start text-xs font-semibold text-[var(--color-text-secondary)] uppercase">Event</th>
                    <th className="px-3 py-2 text-start text-xs font-semibold text-[var(--color-text-secondary)] uppercase">IP</th>
                    <th className="px-3 py-2 text-start text-xs font-semibold text-[var(--color-text-secondary)] uppercase">User</th>
                    <th className="px-3 py-2 text-start text-xs font-semibold text-[var(--color-text-secondary)] uppercase">Date</th>
                  </tr>
                </thead>
                <tbody>
                  {securityLogs.length === 0 ? (
                    <tr><td colSpan={4} className="px-3 py-8 text-center text-[var(--color-text-secondary)]">No events found.</td></tr>
                  ) : (
                    securityLogs.map((log) => {
                      const eventV = log.event_type.includes("blocked") || log.event_type.includes("brute")
                        ? "error"
                        : log.event_type.includes("rate") ? "warning" : "info";
                      return (
                        <tr key={log.id} className="border-b border-[var(--color-border)]">
                          <td className="px-3 py-2"><Badge variant={eventV as "error" | "warning" | "info"}>{log.event_type.replace(/_/g, " ")}</Badge></td>
                          <td className="px-3 py-2 font-mono text-[var(--color-text)]">{log.ip_address || log.source_ip || "-"}</td>
                          <td className="px-3 py-2 text-[var(--color-text)]">{log.user_id || "-"}</td>
                          <td className="px-3 py-2 text-[var(--color-text-secondary)] text-xs">{new Date(log.created_at).toLocaleString()}</td>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            )}

            {/* Audit Table */}
            {tab === "audit" && (
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-[var(--color-border)]">
                    <th className="px-3 py-2 text-start text-xs font-semibold text-[var(--color-text-secondary)] uppercase">Admin</th>
                    <th className="px-3 py-2 text-start text-xs font-semibold text-[var(--color-text-secondary)] uppercase">Action</th>
                    <th className="px-3 py-2 text-start text-xs font-semibold text-[var(--color-text-secondary)] uppercase">Entity</th>
                    <th className="px-3 py-2 text-start text-xs font-semibold text-[var(--color-text-secondary)] uppercase">Date</th>
                  </tr>
                </thead>
                <tbody>
                  {auditLogs.length === 0 ? (
                    <tr><td colSpan={4} className="px-3 py-8 text-center text-[var(--color-text-secondary)]">No audit entries found.</td></tr>
                  ) : (
                    auditLogs.map((log) => (
                      <tr key={log.id} className="border-b border-[var(--color-border)]">
                        <td className="px-3 py-2 text-[var(--color-text)]">{log.admin_id || "-"}</td>
                        <td className="px-3 py-2 text-[var(--color-text)] capitalize">{log.action.replace(/_/g, " ")}</td>
                        <td className="px-3 py-2 text-[var(--color-text)] capitalize">{log.entity_type} #{log.entity_id?.slice(-8)}</td>
                        <td className="px-3 py-2 text-[var(--color-text-secondary)] text-xs">{new Date(log.created_at).toLocaleString()}</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            )}

            <div className="mt-4">
              <Pagination offset={offset} limit={limit} total={pagination.total} onChange={setOffset} />
            </div>
          </>
        )}
      </div>
    </AdminLayout>
  );
}

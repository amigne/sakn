import { useState, useMemo } from "react";
import AdminLayout from "@/components/admin/AdminLayout";
import { TextInput, Select, ToggleSwitch, Pagination, Badge } from "@/components/ui";

type LogTab = "tool-executions" | "security-events" | "audit";

interface ToolLog {
  id: string;
  user_email: string;
  tool_name: string;
  target: string;
  status: string;
  duration_ms: number;
  details: string;
  created_at: string;
}

interface SecurityLog {
  id: string;
  event_type: string;
  user_email: string | null;
  ip_address: string;
  details: string;
  created_at: string;
}

interface AuditEntry {
  id: string;
  admin_email: string;
  action: string;
  entity_type: string;
  entity_id: string;
  details: string;
  created_at: string;
}

const mockToolLogs: ToolLog[] = Array.from({ length: 25 }, (_, i) => ({
  id: `log-${i}`,
  user_email: `user${i + 1}@example.com`,
  tool_name: ["ping", "traceroute", "dns_lookup", "ssl_viewer"][i % 4]!,
  target: ["8.8.8.8", "example.com", "google.com", "1.1.1.1"][i % 4]!,
  status: i % 5 === 0 ? "error" : "success",
  duration_ms: Math.floor(100 + Math.random() * 5000),
  created_at: new Date(2026, 4, 14 - Math.floor(i / 3), 10, i * 3).toISOString(),
  details: JSON.stringify({ extra: "Request details here..." }),
}));

const mockSecurityLogs: SecurityLog[] = Array.from({ length: 15 }, (_, i) => ({
  id: `sec-${i}`,
  event_type: ["blocked_address", "rate_limit_exceeded", "csrf_mismatch", "brute_force_attempt"][i % 4]!,
  user_email: i % 3 === 0 ? null : `user${i}@example.com`,
  ip_address: `203.0.113.${i + 1}`,
  details: JSON.stringify({ reason: "Target in blocked network range" }),
  created_at: new Date(2026, 4, 14 - i, 8, i * 10).toISOString(),
}));

const mockAuditLogs: AuditEntry[] = Array.from({ length: 10 }, (_, i) => ({
  id: `audit-${i}`,
  admin_email: "admin@example.com",
  action: ["user_blocked", "user_unblocked", "tool_disabled", "rate_limit_updated", "setting_changed"][i % 5]!,
  entity_type: ["user", "tool", "rate_limit", "setting"][i % 4]!,
  entity_id: `entity-${i}`,
  details: JSON.stringify({ previous: {}, updated: {} }),
  created_at: new Date(2026, 4, 14 - i, 12, i * 5).toISOString(),
}));

type LogItem = ToolLog | SecurityLog | AuditEntry;

function isToolLog(item: LogItem): item is ToolLog { return "tool_name" in item; }
function isSecurityLog(item: LogItem): item is SecurityLog { return "event_type" in item; }

export default function AdminLogsPage() {
  const [tab, setTab] = useState<LogTab>("tool-executions");
  const [search, setSearch] = useState("");
  const [toolFilter, setToolFilter] = useState("all");
  const [autoRefresh, setAutoRefresh] = useState(false);
  const [offset, setOffset] = useState(0);
  const limit = 10;

  const data: LogItem[] = tab === "tool-executions" ? mockToolLogs : tab === "security-events" ? mockSecurityLogs : mockAuditLogs;

  const filtered = useMemo(() => {
    let items = data;
    if (search) items = items.filter((item) => JSON.stringify(item).toLowerCase().includes(search.toLowerCase()));
    if (toolFilter !== "all" && tab === "tool-executions") {
      items = items.filter((item) => isToolLog(item) && item.tool_name === toolFilter);
    }
    return items;
  }, [data, search, toolFilter, tab]);

  const paged = filtered.slice(offset, offset + limit);

  return (
    <AdminLayout title="Log Viewer">
      <div className="card p-4">
        <div className="flex flex-wrap items-center gap-3 mb-4">
          <div className="flex items-center gap-1 rounded bg-[var(--color-surface-alt)] p-0.5">
            {(["tool-executions", "security-events", "audit"] as LogTab[]).map((t) => (
              <button
                key={t}
                onClick={() => { setTab(t); setOffset(0); }}
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

          <TextInput
            placeholder="Search logs..."
            value={search}
            onChange={(e) => { setSearch(e.target.value); setOffset(0); }}
            className="w-40"
          />

          {tab === "tool-executions" && (
            <Select
              options={[{ value: "all", label: "All Tools" }, { value: "ping", label: "Ping" }, { value: "traceroute", label: "Traceroute" }, { value: "dns_lookup", label: "DNS" }, { value: "ssl_viewer", label: "TLS" }]}
              value={toolFilter}
              onChange={(v) => { setToolFilter(v); setOffset(0); }}
              ariaLabel="Filter by tool"
            />
          )}

          <ToggleSwitch checked={autoRefresh} onChange={setAutoRefresh} label="Auto-refresh" />
        </div>

        {tab === "tool-executions" && (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[var(--color-border)]">
                <th className="px-3 py-2 text-start text-xs font-semibold text-[var(--color-text-secondary)] uppercase">User</th>
                <th className="px-3 py-2 text-start text-xs font-semibold text-[var(--color-text-secondary)] uppercase">Tool</th>
                <th className="px-3 py-2 text-start text-xs font-semibold text-[var(--color-text-secondary)] uppercase">Target</th>
                <th className="px-3 py-2 text-start text-xs font-semibold text-[var(--color-text-secondary)] uppercase">Status</th>
                <th className="px-3 py-2 text-end text-xs font-semibold text-[var(--color-text-secondary)] uppercase">Duration</th>
                <th className="px-3 py-2 text-start text-xs font-semibold text-[var(--color-text-secondary)] uppercase">Date</th>
              </tr>
            </thead>
            <tbody>
              {paged.map((log) => isToolLog(log) && (
                <tr key={log.id} className="border-b border-[var(--color-border)] hover:bg-[var(--color-surface-alt)] cursor-pointer">
                  <td className="px-3 py-2 text-[var(--color-text)]">{log.user_email}</td>
                  <td className="px-3 py-2 text-[var(--color-text)] capitalize">{log.tool_name}</td>
                  <td className="px-3 py-2 font-mono text-[var(--color-text)]">{log.target}</td>
                  <td className="px-3 py-2"><Badge variant={log.status === "success" ? "success" : "error"}>{log.status}</Badge></td>
                  <td className="px-3 py-2 text-end font-mono text-[var(--color-text)]">{log.duration_ms}ms</td>
                  <td className="px-3 py-2 text-[var(--color-text-secondary)] text-xs">{new Date(log.created_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {tab === "security-events" && (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[var(--color-border)]">
                <th className="px-3 py-2 text-start text-xs font-semibold text-[var(--color-text-secondary)] uppercase">Event</th>
                <th className="px-3 py-2 text-start text-xs font-semibold text-[var(--color-text-secondary)] uppercase">User</th>
                <th className="px-3 py-2 text-start text-xs font-semibold text-[var(--color-text-secondary)] uppercase">IP</th>
                <th className="px-3 py-2 text-start text-xs font-semibold text-[var(--color-text-secondary)] uppercase">Date</th>
              </tr>
            </thead>
            <tbody>
              {paged.map((log) => isSecurityLog(log) && (() => {
                const eventV = log.event_type.includes("blocked") || log.event_type.includes("brute") ? "error" : log.event_type.includes("rate") ? "warning" : "info";
                return (
                  <tr key={log.id} className="border-b border-[var(--color-border)]">
                    <td className="px-3 py-2"><Badge variant={eventV as "error" | "warning" | "info"}>{log.event_type.replace(/_/g, " ")}</Badge></td>
                    <td className="px-3 py-2 text-[var(--color-text)]">{log.user_email || "—"}</td>
                    <td className="px-3 py-2 font-mono text-[var(--color-text)]">{log.ip_address}</td>
                    <td className="px-3 py-2 text-[var(--color-text-secondary)] text-xs">{new Date(log.created_at).toLocaleString()}</td>
                  </tr>
                );
              })())}
            </tbody>
          </table>
        )}

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
              {paged.map((log) => !isToolLog(log) && !isSecurityLog(log) && (
                <tr key={log.id} className="border-b border-[var(--color-border)]">
                  <td className="px-3 py-2 text-[var(--color-text)]">{log.admin_email}</td>
                  <td className="px-3 py-2 text-[var(--color-text)] capitalize">{log.action.replace(/_/g, " ")}</td>
                  <td className="px-3 py-2 text-[var(--color-text)] capitalize">{log.entity_type} #{log.entity_id.slice(-4)}</td>
                  <td className="px-3 py-2 text-[var(--color-text-secondary)] text-xs">{new Date(log.created_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        <div className="mt-4">
          <Pagination offset={offset} limit={limit} total={filtered.length} onChange={setOffset} />
        </div>
      </div>
    </AdminLayout>
  );
}

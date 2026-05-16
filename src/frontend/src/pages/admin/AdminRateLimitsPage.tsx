import { useState, useEffect, useCallback } from "react";
import AdminLayout from "@/components/admin/AdminLayout";
import { Spinner } from "@/components/ui";
import { listRateLimits, updateRateLimits } from "@/services/admin";
import type { RateLimit } from "@/types/admin";
import { toolDisplayName } from "@/types/admin";

interface EditState {
  id: string;
  field: "soft_limit" | "hard_limit";
  value: string;
}

export default function AdminRateLimitsPage() {
  const [limits, setLimits] = useState<RateLimit[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [edit, setEdit] = useState<EditState | null>(null);

  const fetchLimits = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listRateLimits();
      setLimits(data.rate_limits);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load rate limits");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchLimits();
  }, [fetchLimits]);

  const globalLimits = limits.filter((l) => l.tool_id === null);
  const perToolLimits = limits.filter((l) => l.tool_id !== null);

  const startEdit = (id: string, field: "soft_limit" | "hard_limit", currentValue: number) => {
    setEdit({ id, field, value: String(currentValue) });
  };

  const commitEdit = async () => {
    if (!edit) return;
    const val = parseInt(edit.value, 10);
    if (isNaN(val) || val < 0) {
      setEdit(null);
      return;
    }

    // Optimistic update
    const prevLimits = [...limits];
    setLimits((prev) =>
      prev.map((l) => (l.id === edit.id ? { ...l, [edit.field]: val } : l))
    );
    setEdit(null);

    try {
      const target = prevLimits.find((l) => l.id === edit.id);
      if (!target) return;
      const payload = {
        role: target.role,
        tool_id: target.tool_id,
        soft_limit: edit.field === "soft_limit" ? val : target.soft_limit,
        hard_limit: edit.field === "hard_limit" ? val : target.hard_limit,
        window_seconds: target.window_seconds,
      };
      await updateRateLimits([payload]);
      setSuccessMsg("Rate limits updated");
      setTimeout(() => setSuccessMsg(null), 2000);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to update rate limit");
      setLimits(prevLimits);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") commitEdit();
    if (e.key === "Escape") setEdit(null);
  };

  const EditableCell = ({
    id,
    field,
    value,
  }: {
    id: string;
    field: "soft_limit" | "hard_limit";
    value: number;
  }) => {
    const isEditing = edit?.id === id && edit?.field === field;
    return (
      <td
        className="px-3 py-2 text-end font-mono text-sm text-[var(--color-text)] cursor-pointer hover:bg-[var(--color-surface-alt)]"
        onClick={() => startEdit(id, field, value)}
      >
        {isEditing ? (
          <input
            type="number"
            min={0}
            value={edit!.value}
            onChange={(e) => setEdit({ ...edit!, value: e.target.value })}
            onBlur={commitEdit}
            onKeyDown={handleKeyDown}
            className="w-20 text-end bg-[var(--color-surface)] dark:[color-scheme:dark] border border-primary-500 rounded px-1 py-0.5 text-sm text-[var(--color-text)] focus:outline-none"
            autoFocus
          />
        ) : (
          value || "0 (unlimited)"
        )}
      </td>
    );
  };

  if (loading) {
    return (
      <AdminLayout title="Rate Limits">
        <div className="flex justify-center py-12"><Spinner /></div>
      </AdminLayout>
    );
  }

  return (
    <AdminLayout title="Rate Limits">
      <div className="space-y-6 max-w-2xl">
        {error && (
          <div className="p-3 rounded bg-red-50 dark:bg-red-950 text-sm text-red-700 dark:text-red-300">{error}</div>
        )}
        {successMsg && (
          <div className="p-3 rounded bg-green-50 dark:bg-green-950 text-sm text-green-700 dark:text-green-300">{successMsg}</div>
        )}

        {/* Global limits */}
        <div className="card p-4">
          <h2 className="text-sm font-semibold text-[var(--color-text)] mb-1">Global limits</h2>
          <p className="text-xs text-[var(--color-text-secondary)] mb-4">
            Soft limit: requests per second (1s window). Hard limit: requests per hour (3600s). 0 = no limit. Click a value to edit.
          </p>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[var(--color-border)]">
                <th scope="col" className="px-3 py-2 text-start text-xs font-semibold text-[var(--color-text-secondary)] uppercase">Role</th>
                <th scope="col" className="px-3 py-2 text-end text-xs font-semibold text-[var(--color-text-secondary)] uppercase">Soft limit (req/s)</th>
                <th scope="col" className="px-3 py-2 text-end text-xs font-semibold text-[var(--color-text-secondary)] uppercase">Hard limit (req/h)</th>
              </tr>
            </thead>
            <tbody>
              {globalLimits.map((limit) => (
                <tr key={limit.id || `global-${limit.role}`} className="border-b border-[var(--color-border)]">
                  <td className="px-3 py-2 font-medium text-[var(--color-text)] capitalize">{limit.role}</td>
                  <EditableCell id={limit.id || `${limit.role}-soft`} field="soft_limit" value={limit.soft_limit} />
                  <EditableCell id={limit.id || `${limit.role}-hard`} field="hard_limit" value={limit.hard_limit} />
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Per-tool limits */}
        {perToolLimits.length > 0 && (
          <div className="card p-4">
            <h2 className="text-sm font-semibold text-[var(--color-text)] mb-1">Per-tool limits</h2>
            <p className="text-xs text-[var(--color-text-secondary)] mb-4">
              Optional overrides for specific tools. Must be &le; the global limit for the same role. 0 = no limit.
            </p>
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[var(--color-border)]">
                  <th scope="col" className="px-3 py-2 text-start text-xs font-semibold text-[var(--color-text-secondary)] uppercase">Role</th>
                  <th scope="col" className="px-3 py-2 text-start text-xs font-semibold text-[var(--color-text-secondary)] uppercase">Tool</th>
                  <th scope="col" className="px-3 py-2 text-end text-xs font-semibold text-[var(--color-text-secondary)] uppercase">Soft limit</th>
                  <th scope="col" className="px-3 py-2 text-end text-xs font-semibold text-[var(--color-text-secondary)] uppercase">Hard limit</th>
                </tr>
              </thead>
              <tbody>
                {perToolLimits.map((limit) => (
                  <tr key={limit.id} className="border-b border-[var(--color-border)]">
                    <td className="px-3 py-2 text-[var(--color-text)] capitalize">{limit.role}</td>
                    <td className="px-3 py-2 font-medium text-[var(--color-text)] capitalize">{limit.tool_name ? toolDisplayName(limit.tool_name) : "-"}</td>
                    <EditableCell id={limit.id!} field="soft_limit" value={limit.soft_limit} />
                    <EditableCell id={limit.id!} field="hard_limit" value={limit.hard_limit} />
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </AdminLayout>
  );
}

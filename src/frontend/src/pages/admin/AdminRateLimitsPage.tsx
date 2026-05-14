import { useState } from "react";
import AdminLayout from "@/components/admin/AdminLayout";
import { Button, TextInput, Select } from "@/components/ui";

interface RateLimitEntry {
  role: string;
  soft: number;
  hard: number;
}

interface PerToolEntry {
  role: string;
  tool: string;
  soft: number;
  hard: number;
}

const defaultGlobal: RateLimitEntry[] = [
  { role: "Admin", soft: 0.5, hard: 10000 },
  { role: "Authenticated", soft: 0.1, hard: 500 },
  { role: "Visitor (session)", soft: 0.05, hard: 30 },
  { role: "Visitor (IP)", soft: 0.05, hard: 30 },
];

const defaultPerTool: PerToolEntry[] = [
  { role: "Authenticated", tool: "ping", soft: 0.1, hard: 100 },
  { role: "Authenticated", tool: "traceroute", soft: 0.05, hard: 15 },
  { role: "Authenticated", tool: "dns", soft: 0.1, hard: 200 },
  { role: "Visitor (IP)", tool: "ping", soft: 0.03, hard: 10 },
];

const ALL_ROLES = ["Admin", "Authenticated", "Visitor (session)", "Visitor (IP)"];
const ALL_TOOLS = ["ping", "traceroute", "dns", "ssl_viewer"];

export default function AdminRateLimitsPage() {
  const [globalLimits, setGlobalLimits] = useState<RateLimitEntry[]>(defaultGlobal);
  const [perToolLimits, setPerToolLimits] = useState<PerToolEntry[]>(defaultPerTool);
  const [editCell, setEditCell] = useState<{ table: "global" | "pertool"; row: number; col: "soft" | "hard"; value: number } | null>(null);
  const [editValue, setEditValue] = useState("");

  // New row form
  const [newRole, setNewRole] = useState("");
  const [newTool, setNewTool] = useState("");
  const [newSoft, setNewSoft] = useState("");
  const [newHard, setNewHard] = useState("");
  const [addError, setAddError] = useState("");

  const startEdit = (table: "global" | "pertool", row: number, col: "soft" | "hard", value: number) => {
    setEditCell({ table, row, col, value });
    setEditValue(String(value));
  };

  const commitEdit = () => {
    if (!editCell) return;
    const val = parseFloat(editValue);
    if (isNaN(val) || val < 0) return;
    if (editCell.table === "global") {
      setGlobalLimits((prev) =>
        prev.map((l, i) => (i === editCell.row ? { ...l, [editCell.col]: val } : l))
      );
    } else {
      setPerToolLimits((prev) =>
        prev.map((l, i) => (i === editCell.row ? { ...l, [editCell.col]: val } : l))
      );
    }
    setEditCell(null);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") commitEdit();
    if (e.key === "Escape") setEditCell(null);
  };

  const handleReset = () => {
    setGlobalLimits(defaultGlobal);
    setPerToolLimits(defaultPerTool);
  };

  const handleAdd = () => {
    setAddError("");
    if (!newRole || !newTool) {
      setAddError("Role and Tool are required.");
      return;
    }
    const exists = perToolLimits.some((l) => l.role === newRole && l.tool === newTool);
    if (exists) {
      setAddError("A limit for this role and tool already exists.");
      return;
    }
    setPerToolLimits((prev) => [
      ...prev,
      { role: newRole, tool: newTool, soft: parseFloat(newSoft) || 0.1, hard: parseFloat(newHard) || 10 },
    ]);
    setNewRole("");
    setNewTool("");
    setNewSoft("");
    setNewHard("");
  };

  const handleDelete = (role: string, tool: string) => {
    setPerToolLimits((prev) => prev.filter((l) => !(l.role === role && l.tool === tool)));
  };

  const EditableCell = ({ table, row, col, value }: { table: "global" | "pertool"; row: number; col: "soft" | "hard"; value: number }) => {
    const isEditing = editCell?.table === table && editCell?.row === row && editCell?.col === col;
    return (
      <td
        className="px-3 py-2 text-end font-mono text-sm text-[var(--color-text)] cursor-pointer hover:bg-[var(--color-surface-alt)]"
        onClick={() => startEdit(table, row, col, value)}
      >
        {isEditing ? (
          <input
            type="number"
            min={0}
            step={0.01}
            value={editValue}
            onChange={(e) => setEditValue(e.target.value)}
            onBlur={commitEdit}
            onKeyDown={handleKeyDown}
            className="w-20 text-end bg-[var(--color-surface)] dark:[color-scheme:dark] border border-primary-500 rounded px-1 py-0.5 text-sm text-[var(--color-text)] focus:outline-none"
            autoFocus
          />
        ) : (
          value
        )}
      </td>
    );
  };

  return (
    <AdminLayout title="Rate Limits">
      <div className="space-y-6 max-w-2xl">

        {/* Global limits */}
        <div className="card p-4">
          <h2 className="text-sm font-semibold text-[var(--color-text)] mb-1">Global limits</h2>
          <p className="text-xs text-[var(--color-text-secondary)] mb-4">
            Soft limit: requests per second (short window — 1s). Hard limit: requests per hour (long window — 1h). Exceeding either limit blocks the user. Changes are saved immediately.
          </p>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[var(--color-border)]">
                <th scope="col" className="px-3 py-2 text-start text-xs font-semibold text-[var(--color-text-secondary)] uppercase">Role</th>
                <th scope="col" className="px-3 py-2 text-end text-xs font-semibold text-[var(--color-text-secondary)] uppercase">Soft limit (/s)</th>
                <th scope="col" className="px-3 py-2 text-end text-xs font-semibold text-[var(--color-text-secondary)] uppercase">Hard limit (/h)</th>
              </tr>
            </thead>
            <tbody>
              {globalLimits.map((limit, rowIdx) => (
                <tr key={limit.role} className="border-b border-[var(--color-border)]">
                  <td className="px-3 py-2 font-medium text-[var(--color-text)]">{limit.role}</td>
                  <EditableCell table="global" row={rowIdx} col="soft" value={limit.soft} />
                  <EditableCell table="global" row={rowIdx} col="hard" value={limit.hard} />
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Per-tool overrides */}
        <div className="card p-4">
          <h2 className="text-sm font-semibold text-[var(--color-text)] mb-1">Per-tool limits</h2>
          <p className="text-xs text-[var(--color-text-secondary)] mb-4">
            Optional overrides for specific tools. Must be &le; the global limit for the same role. Each role + tool pair must be unique.
          </p>

          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[var(--color-border)]">
                <th scope="col" className="px-3 py-2 text-start text-xs font-semibold text-[var(--color-text-secondary)] uppercase">Role</th>
                <th scope="col" className="px-3 py-2 text-start text-xs font-semibold text-[var(--color-text-secondary)] uppercase">Tool</th>
                <th scope="col" className="px-3 py-2 text-end text-xs font-semibold text-[var(--color-text-secondary)] uppercase">Soft limit (/s)</th>
                <th scope="col" className="px-3 py-2 text-end text-xs font-semibold text-[var(--color-text-secondary)] uppercase">Hard limit (/h)</th>
                <th scope="col" className="px-3 py-2 w-10" />
              </tr>
            </thead>
            <tbody>
              {/* Add row */}
              <tr className="border-b border-[var(--color-border)] bg-blue-50/50 dark:bg-blue-900/10">
                <td className="px-2 py-1.5">
                  <Select
                    options={ALL_ROLES.map((r) => ({ value: r, label: r }))}
                    value={newRole}
                    onChange={(v) => { setNewRole(v); setAddError(""); }}
                    placeholder="Role…"
                    ariaLabel="Select role"
                  />
                </td>
                <td className="px-2 py-1.5">
                  <Select
                    options={ALL_TOOLS.map((t) => ({ value: t, label: t }))}
                    value={newTool}
                    onChange={(v) => { setNewTool(v); setAddError(""); }}
                    placeholder="Tool…"
                    ariaLabel="Select tool"
                  />
                </td>
                <td className="px-2 py-1.5">
                  <TextInput
                    type="number"
                    min={0}
                    step={0.01}
                    placeholder="0.1"
                    value={newSoft}
                    onChange={(e) => setNewSoft(e.target.value)}
                  />
                </td>
                <td className="px-2 py-1.5">
                  <TextInput
                    type="number"
                    min={0}
                    step={1}
                    placeholder="10"
                    value={newHard}
                    onChange={(e) => setNewHard(e.target.value)}
                  />
                </td>
                <td className="px-2 py-1.5">
                  <Button size="sm" onClick={handleAdd}>Add</Button>
                </td>
              </tr>
              {addError && (
                <tr>
                  <td colSpan={5} className="px-3 py-1 text-xs text-error-600 dark:text-error-500">{addError}</td>
                </tr>
              )}

              {/* Existing rows */}
              {perToolLimits.map((limit, rowIdx) => (
                <tr key={`${limit.role}-${limit.tool}`} className="border-b border-[var(--color-border)]">
                  <td className="px-3 py-2 text-[var(--color-text-secondary)]">{limit.role}</td>
                  <td className="px-3 py-2 font-medium text-[var(--color-text)] capitalize">{limit.tool}</td>
                  <EditableCell table="pertool" row={rowIdx} col="soft" value={limit.soft} />
                  <EditableCell table="pertool" row={rowIdx} col="hard" value={limit.hard} />
                  <td className="px-3 py-2 text-center">
                    <button
                      onClick={() => handleDelete(limit.role, limit.tool)}
                      className="text-xs text-error-600 hover:text-error-700 dark:text-error-500"
                      aria-label={`Delete ${limit.role} / ${limit.tool}`}
                    >
                      <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="flex items-center gap-3">
          <Button variant="secondary" size="sm" onClick={handleReset}>Reset to Defaults</Button>
        </div>
      </div>
    </AdminLayout>
  );
}

import { useState } from "react";
import AdminLayout from "@/components/admin/AdminLayout";
import { Button } from "@/components/ui";

interface RateLimitEntry {
  role: string;
  tool: string;
  soft: number;
  hard: number;
  window: number;
}

const defaultLimits: RateLimitEntry[] = [
  { role: "admin", tool: "Global", soft: 10, hard: 2000, window: 60 },
  { role: "authenticated", tool: "Global", soft: 1, hard: 500, window: 60 },
  { role: "visitor (session)", tool: "Global", soft: 0.5, hard: 30, window: 60 },
  { role: "visitor (IP)", tool: "Global", soft: 0.5, hard: 30, window: 60 },
  { role: "authenticated", tool: "ping", soft: 1, hard: 100, window: 60 },
  { role: "authenticated", tool: "traceroute", soft: 0.5, hard: 15, window: 60 },
  { role: "authenticated", tool: "dns", soft: 1, hard: 60, window: 60 },
  { role: "visitor (IP)", tool: "ping", soft: 0.3, hard: 10, window: 60 },
];

function getLimitValue(limit: RateLimitEntry, col: string): number {
  if (col === "soft") return limit.soft;
  if (col === "hard") return limit.hard;
  return limit.window;
}

export default function AdminRateLimitsPage() {
  const [limits, setLimits] = useState<RateLimitEntry[]>(defaultLimits);
  const [editCell, setEditCell] = useState<{ row: number; col: string } | null>(null);
  const [editValue, setEditValue] = useState("");
  const [saved, setSaved] = useState(false);

  const startEdit = (row: number, col: string, value: number) => {
    setEditCell({ row, col });
    setEditValue(String(value));
  };

  const commitEdit = () => {
    if (!editCell) return;
    const val = parseFloat(editValue);
    if (isNaN(val) || val < 0) return;
    setLimits((prev) =>
      prev.map((l, i) => {
        if (i !== editCell.row) return l;
        if (editCell.col === "soft") return { ...l, soft: val };
        if (editCell.col === "hard") return { ...l, hard: val };
        if (editCell.col === "window") return { ...l, window: Math.round(val) };
        return l;
      })
    );
    setEditCell(null);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") commitEdit();
    if (e.key === "Escape") setEditCell(null);
  };

  const handleSave = () => {
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  const handleReset = () => {
    setLimits(defaultLimits);
  };

  return (
    <AdminLayout title="Rate Limits">
      <div className="card p-4 max-w-2xl">
        <p className="text-sm text-[var(--color-text-secondary)] mb-4">
          Click any value to edit. Press Enter to save, Escape to cancel. Per-tool limits must be &le; global limits.
        </p>

        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[var(--color-border)]">
                <th scope="col" className="px-3 py-2 text-start text-xs font-semibold text-[var(--color-text-secondary)] uppercase">Role</th>
                <th scope="col" className="px-3 py-2 text-start text-xs font-semibold text-[var(--color-text-secondary)] uppercase">Tool</th>
                <th scope="col" className="px-3 py-2 text-end text-xs font-semibold text-[var(--color-text-secondary)] uppercase">Soft (/s)</th>
                <th scope="col" className="px-3 py-2 text-end text-xs font-semibold text-[var(--color-text-secondary)] uppercase">Hard (/s)</th>
                <th scope="col" className="px-3 py-2 text-end text-xs font-semibold text-[var(--color-text-secondary)] uppercase">Window (s)</th>
              </tr>
            </thead>
            <tbody>
              {limits.map((limit, rowIdx) => (
                <tr key={`${limit.role}-${limit.tool}`} className="border-b border-[var(--color-border)]">
                  <td className="px-3 py-2 text-[var(--color-text)] capitalize">{limit.role}</td>
                  <td className="px-3 py-2 font-medium text-[var(--color-text)]">{limit.tool}</td>
                  {["soft", "hard", "window"].map((col) => (
                    <td
                      key={col}
                      className="px-3 py-2 text-end font-mono text-[var(--color-text)] cursor-pointer hover:bg-[var(--color-surface-alt)]"
                      onClick={() => startEdit(rowIdx, col, getLimitValue(limit, col))}
                    >
                      {editCell?.row === rowIdx && editCell?.col === col ? (
                        <input
                          type="number"
                          min={0}
                          step={col === "window" ? 1 : 0.1}
                          value={editValue}
                          onChange={(e) => setEditValue(e.target.value)}
                          onBlur={commitEdit}
                          onKeyDown={handleKeyDown}
                          className="w-16 text-end bg-transparent border border-primary-500 rounded px-1 py-0.5 text-sm focus:outline-none"
                          autoFocus
                        />
                      ) : (
                        getLimitValue(limit, col)
                      )}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="flex items-center gap-3 mt-4">
          <Button size="sm" onClick={handleSave}>{saved ? "Saved" : "Save Changes"}</Button>
          <Button variant="secondary" size="sm" onClick={handleReset}>Reset to Defaults</Button>
        </div>
      </div>
    </AdminLayout>
  );
}

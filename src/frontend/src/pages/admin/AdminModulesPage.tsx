import { useState } from "react";
import AdminLayout from "@/components/admin/AdminLayout";
import { ToggleSwitch, Button, TextInput, Modal } from "@/components/ui";
import type { DnsServerPreset } from "@/types/admin";

interface ModuleEntry {
  name: string;
  display: string;
  enabled: boolean;
  hasSettings: boolean;
}

const initialModules: ModuleEntry[] = [
  { name: "ping", display: "Ping", enabled: true, hasSettings: false },
  { name: "traceroute", display: "Traceroute", enabled: true, hasSettings: false },
  { name: "dns_lookup", display: "DNS Lookup", enabled: true, hasSettings: true },
  { name: "ssl_viewer", display: "TLS/SSL Viewer", enabled: true, hasSettings: false },
];

const initialPresets: DnsServerPreset[] = [
  { id: "1", ip_address: "8.8.8.8", description: "Google DNS", sort_order: 0 },
  { id: "2", ip_address: "1.1.1.1", description: "Cloudflare DNS", sort_order: 1 },
  { id: "3", ip_address: "9.9.9.9", description: "Quad9 DNS", sort_order: 2 },
];

export default function AdminModulesPage() {
  const [modules, setModules] = useState<ModuleEntry[]>(initialModules);
  const [dnsPresets, setDnsPresets] = useState<DnsServerPreset[]>(initialPresets);
  const [showDnsEditor, setShowDnsEditor] = useState(false);
  const [editingPreset, setEditingPreset] = useState<DnsServerPreset | null>(null);
  const [presetIp, setPresetIp] = useState("");
  const [presetDesc, setPresetDesc] = useState("");

  const toggleModule = (name: string) => {
    setModules((prev) => prev.map((m) => (m.name === name ? { ...m, enabled: !m.enabled } : m)));
  };

  const openEditPreset = (preset: DnsServerPreset) => {
    setEditingPreset(preset);
    setPresetIp(preset.ip_address);
    setPresetDesc(preset.description);
    setShowDnsEditor(true);
  };

  const savePreset = () => {
    if (editingPreset) {
      setDnsPresets((prev) => prev.map((p) => (p.id === editingPreset.id ? { ...p, ip_address: presetIp, description: presetDesc } : p)));
    } else {
      const id = String(Date.now());
      setDnsPresets((prev) => [...prev, { id, ip_address: presetIp, description: presetDesc, sort_order: prev.length }]);
    }
    setShowDnsEditor(false);
  };

  const deletePreset = (id: string) => {
    setDnsPresets((prev) => prev.filter((p) => p.id !== id));
  };

  const movePreset = (id: string, direction: "up" | "down") => {
    setDnsPresets((prev) => {
      const idx = prev.findIndex((p) => p.id === id);
      if (idx < 0 || (direction === "up" && idx === 0) || (direction === "down" && idx === prev.length - 1)) return prev;
      const next = [...prev];
      const swapIdx = direction === "up" ? idx - 1 : idx + 1;
      const temp = next[idx]!;
      next[idx] = next[swapIdx]!;
      next[swapIdx] = temp;
      return next.map((p, i) => ({ ...p, sort_order: i }));
    });
  };

  return (
    <AdminLayout title="Module Activation">
      <div className="space-y-4 max-w-lg">
        <div className="card p-4">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[var(--color-border)]">
                <th scope="col" className="px-3 py-2 text-start text-xs font-semibold text-[var(--color-text-secondary)] uppercase">Module</th>
                <th scope="col" className="px-3 py-2 text-center text-xs font-semibold text-[var(--color-text-secondary)] uppercase w-20">Enabled</th>
                <th scope="col" className="px-3 py-2 text-center text-xs font-semibold text-[var(--color-text-secondary)] uppercase w-20">Settings</th>
              </tr>
            </thead>
            <tbody>
              {modules.map((mod) => (
                <tr key={mod.name} className="border-b border-[var(--color-border)]">
                  <td className="px-3 py-2 font-medium text-[var(--color-text)]">{mod.display}</td>
                  <td className="px-3 py-2 text-center">
                    <ToggleSwitch checked={mod.enabled} onChange={() => toggleModule(mod.name)} />
                  </td>
                  <td className="px-3 py-2 text-center">
                    {mod.hasSettings && (
                      <button onClick={() => setShowDnsEditor(true)} className="text-primary-600 hover:text-primary-700">
                        <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                          <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                        </svg>
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <Modal open={showDnsEditor} onClose={() => setShowDnsEditor(false)} title="DNS Server Presets">
          <div className="space-y-3">
            {dnsPresets.map((preset) => (
              <div key={preset.id} className="flex items-center gap-2 text-sm">
                <button onClick={() => movePreset(preset.id, "up")} className="text-[var(--color-text-secondary)] hover:text-[var(--color-text)]" aria-label="Move up">
                  <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M5 15l7-7 7 7" /></svg>
                </button>
                <button onClick={() => movePreset(preset.id, "down")} className="text-[var(--color-text-secondary)] hover:text-[var(--color-text)]" aria-label="Move down">
                  <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" /></svg>
                </button>
                <span className="font-mono flex-1">{preset.ip_address}</span>
                <span className="text-[var(--color-text-secondary)]">{preset.description}</span>
                <button onClick={() => openEditPreset(preset)} className="text-primary-600 hover:text-primary-700 text-xs">Edit</button>
                <button onClick={() => deletePreset(preset.id)} className="text-error-600 hover:text-error-700 text-xs">Delete</button>
              </div>
            ))}

            <hr className="border-[var(--color-border)]" />

            <div className="flex gap-2">
              <TextInput placeholder="IP Address" value={presetIp} onChange={(e) => setPresetIp(e.target.value)} />
              <TextInput placeholder="Description" value={presetDesc} onChange={(e) => setPresetDesc(e.target.value)} />
              <Button size="sm" onClick={savePreset}>{editingPreset ? "Update" : "Add"}</Button>
            </div>

            {editingPreset && (
              <p className="text-xs text-[var(--color-text-secondary)]">Editing: {editingPreset.ip_address}</p>
            )}
          </div>
        </Modal>
      </div>
    </AdminLayout>
  );
}

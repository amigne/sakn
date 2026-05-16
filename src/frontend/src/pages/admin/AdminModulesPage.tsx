import { useState, useEffect, useCallback } from "react";
import AdminLayout from "@/components/admin/AdminLayout";
import { ToggleSwitch, Button, TextInput, Modal, Spinner } from "@/components/ui";
import { api } from "@/services/api";
import { listModules, updateModule, listDnsServers, createDnsServer, updateDnsServer, deleteDnsServer, reorderDnsServers } from "@/services/admin";
import type { DnsServerPreset, ToolModule } from "@/types/admin";
import { toolDisplayName } from "@/types/admin";

export default function AdminModulesPage() {
  const [modules, setModules] = useState<ToolModule[]>([]);
  const [modulesLoading, setModulesLoading] = useState(true);
  const [modulesError, setModulesError] = useState<string | null>(null);
  const [dnsPresets, setDnsPresets] = useState<DnsServerPreset[]>([]);
  const [dnsLoading, setDnsLoading] = useState(false);
  const [showDnsEditor, setShowDnsEditor] = useState(false);
  const [editingPreset, setEditingPreset] = useState<DnsServerPreset | null>(null);
  const [presetIp, setPresetIp] = useState("");
  const [presetDesc, setPresetDesc] = useState("");
  const [presetError, setPresetError] = useState("");

  // Traceroute module settings
  const [showTracerouteSettings, setShowTracerouteSettings] = useState(false);
  const [showPrivateHops, setShowPrivateHops] = useState(true);
  const [settingsLoading, setSettingsLoading] = useState(false);
  const [settingsSaving, setSettingsSaving] = useState(false);
  const [settingsError, setSettingsError] = useState<string | null>(null);

  const fetchModules = useCallback(async () => {
    setModulesLoading(true);
    setModulesError(null);
    try {
      const data = await listModules();
      setModules(data.modules);
    } catch (e) {
      setModulesError(e instanceof Error ? e.message : "Failed to load modules");
    } finally {
      setModulesLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchModules();
  }, [fetchModules]);

  const toggleModule = async (name: string, currentEnabled: boolean) => {
    // Optimistic update
    setModules((prev) =>
      prev.map((m) => (m.name === name ? { ...m, enabled: !currentEnabled } : m))
    );
    try {
      await updateModule(name, { enabled: !currentEnabled });
    } catch (e) {
      setModulesError(e instanceof Error ? e.message : "Failed to update module");
      // Revert
      setModules((prev) =>
        prev.map((m) => (m.name === name ? { ...m, enabled: currentEnabled } : m))
      );
    }
  };

  const hasSettings = (name: string) => name === "dns_lookup" || name === "traceroute";

  const openSettings = useCallback((moduleName: string) => {
    if (moduleName === "dns_lookup") {
      setShowDnsEditor(true);
      loadDnsPresets();
    } else if (moduleName === "traceroute") {
      setShowTracerouteSettings(true);
      loadTracerouteSettings();
    }
  }, []);

  // ── Traceroute settings ──────────────────────────────────────────

  const loadTracerouteSettings = useCallback(async () => {
    setSettingsLoading(true);
    setSettingsError(null);
    try {
      const data: { settings?: { show_private_hops?: string } } = await api("/admin/modules/traceroute/settings");
      const val = data?.settings?.show_private_hops;
      if (val !== undefined) {
        setShowPrivateHops(val === "true");
      }
    } catch {
      setSettingsError("Failed to load settings.");
    } finally {
      setSettingsLoading(false);
    }
  }, []);

  const saveTracerouteSettings = useCallback(async (value: boolean) => {
    setSettingsSaving(true);
    setSettingsError(null);
    try {
      await api("/admin/modules/traceroute/settings", {
        method: "PUT",
        body: { settings: { show_private_hops: value } },
      });
      setShowPrivateHops(value);
    } catch {
      setSettingsError("Failed to save settings.");
    } finally {
      setSettingsSaving(false);
    }
  }, []);

  const handleShowPrivateToggle = (value: boolean) => {
    setShowPrivateHops(value);
    saveTracerouteSettings(value);
  };

  // ── DNS presets ──────────────────────────────────────────────────

  const loadDnsPresets = useCallback(async () => {
    setDnsLoading(true);
    try {
      const data = await listDnsServers("dns_lookup");
      setDnsPresets(data.presets ?? []);
    } catch {
      setPresetError("Failed to load DNS presets.");
    } finally {
      setDnsLoading(false);
    }
  }, []);

  const openEditPreset = (preset: DnsServerPreset) => {
    setEditingPreset(preset);
    setPresetIp(preset.ip_address);
    setPresetDesc(preset.description);
    setPresetError("");
    setShowDnsEditor(true);
  };

  const isValidIp = (ip: string): boolean => {
    const ipv4Re = /^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$/;
    const m = ipv4Re.exec(ip);
    if (!m) return false;
    return m.slice(1).every((o) => parseInt(o, 10) <= 255);
  };

  const savePreset = async () => {
    setPresetError("");
    if (!isValidIp(presetIp.trim())) {
      setPresetError("Invalid IPv4 address.");
      return;
    }
    if (!presetDesc.trim()) {
      setPresetError("Description is required.");
      return;
    }
    try {
      if (editingPreset) {
        await updateDnsServer("dns_lookup", editingPreset.id, {
          ip_address: presetIp.trim(),
          description: presetDesc.trim(),
        });
        setEditingPreset(null);
      } else {
        await createDnsServer("dns_lookup", {
          ip_address: presetIp.trim(),
          description: presetDesc.trim(),
        });
      }
      setPresetIp("");
      setPresetDesc("");
      await loadDnsPresets();
    } catch {
      setPresetError("Failed to save preset.");
    }
  };

  const deletePreset = async (id: string) => {
    try {
      await deleteDnsServer("dns_lookup", id);
      await loadDnsPresets();
    } catch {
      setPresetError("Failed to delete preset.");
    }
  };

  const movePreset = async (id: string, direction: "up" | "down") => {
    const idx = dnsPresets.findIndex((p) => p.id === id);
    if (idx < 0 || (direction === "up" && idx === 0) || (direction === "down" && idx === dnsPresets.length - 1)) return;
    const reordered = [...dnsPresets];
    const swapIdx = direction === "up" ? idx - 1 : idx + 1;
    [reordered[idx], reordered[swapIdx]] = [reordered[swapIdx]!, reordered[idx]!];
    setDnsPresets(reordered);
    try {
      await reorderDnsServers("dns_lookup", reordered.map((p) => p.id));
    } catch {
      await loadDnsPresets();
    }
  };

  if (modulesLoading) {
    return (
      <AdminLayout title="Module Activation">
        <div className="flex justify-center py-12"><Spinner /></div>
      </AdminLayout>
    );
  }

  return (
    <AdminLayout title="Module Activation">
      <div className="space-y-4 max-w-lg">
        {modulesError && (
          <div className="p-3 rounded bg-red-50 dark:bg-red-950 text-sm text-red-700 dark:text-red-300">{modulesError}</div>
        )}

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
                  <td className="px-3 py-2 font-medium text-[var(--color-text)] capitalize">{toolDisplayName(mod.name)}</td>
                  <td className="px-3 py-2">
                    <div className="flex justify-center">
                      <ToggleSwitch checked={mod.enabled} onChange={() => toggleModule(mod.name, mod.enabled)} />
                    </div>
                  </td>
                  <td className="px-3 py-2">
                    <div className="flex justify-center">
                      {hasSettings(mod.name) && (
                        <button onClick={() => openSettings(mod.name)} className="text-primary-600 hover:text-primary-700">
                          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                            <path strokeLinecap="round" strokeLinejoin="round" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                            <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                          </svg>
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* DNS Server Presets Modal */}
        <Modal open={showDnsEditor} onClose={() => setShowDnsEditor(false)} title="DNS Server Presets">
          <div className="space-y-3">
            {dnsLoading ? (
              <div className="flex justify-center py-4"><Spinner /></div>
            ) : dnsPresets.map((preset) => (
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

            {presetError && <p className="text-xs text-error-600 dark:text-error-500">{presetError}</p>}

            <div className="flex gap-2">
              <TextInput placeholder="IP Address" value={presetIp} onChange={(e) => { setPresetIp(e.target.value); setPresetError(""); }} />
              <TextInput placeholder="Description" value={presetDesc} onChange={(e) => { setPresetDesc(e.target.value); setPresetError(""); }} />
              <Button size="sm" onClick={savePreset}>{editingPreset ? "Update" : "Add"}</Button>
            </div>

            {editingPreset && <p className="text-xs text-[var(--color-text-secondary)]">Editing: {editingPreset.ip_address}</p>}
          </div>
        </Modal>

        {/* Traceroute Settings Modal */}
        <Modal open={showTracerouteSettings} onClose={() => setShowTracerouteSettings(false)} title="Traceroute Settings">
          {settingsLoading ? (
            <div className="flex justify-center py-4"><Spinner /></div>
          ) : (
            <div className="space-y-4">
              {settingsError && <p className="text-xs text-error-600 dark:text-error-500">{settingsError}</p>}
              <label className="flex items-center justify-between gap-4">
                <div>
                  <p className="text-sm font-medium text-[var(--color-text)]">Show Private Hops</p>
                  <p className="text-xs text-[var(--color-text-secondary)]">Display private IP addresses in traceroute results.</p>
                </div>
                <span className="flex items-center gap-2">
                  {settingsSaving && <Spinner size="sm" />}
                  <ToggleSwitch checked={showPrivateHops} onChange={handleShowPrivateToggle} />
                </span>
              </label>
            </div>
          )}
        </Modal>
      </div>
    </AdminLayout>
  );
}

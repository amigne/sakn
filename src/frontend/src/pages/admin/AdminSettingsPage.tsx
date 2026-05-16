import { useState, useEffect, useCallback } from "react";
import AdminLayout from "@/components/admin/AdminLayout";
import { TextInput, Spinner, ToggleSwitch } from "@/components/ui";
import { getSettings, updateSettings } from "@/services/admin";
import type { GlobalSettings } from "@/types/admin";

const defaults: GlobalSettings = {
  log_retention_days: "90",
  session_duration_hours: "24",
  max_concurrent_sessions: "10",
};

export default function AdminSettingsPage() {
  const [settings, setSettings] = useState<GlobalSettings>({ ...defaults });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savedKey, setSavedKey] = useState<string | null>(null);

  const fetchSettings = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getSettings();
      setSettings({ ...defaults, ...data.settings });
    } catch {
      setError("Failed to load settings.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchSettings();
  }, [fetchSettings]);

  const update = async (key: keyof GlobalSettings, value: string) => {
    const newSettings = { ...settings, [key]: value };
    setSettings(newSettings);

    setSaving(true);
    setError(null);
    try {
      await updateSettings({ [key]: value });
      setSavedKey(key);
      setTimeout(() => setSavedKey(null), 1500);
    } catch {
      setError("Failed to save setting.");
      setSettings(settings); // revert
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <AdminLayout title="Global Settings">
        <div className="flex justify-center py-12"><Spinner /></div>
      </AdminLayout>
    );
  }

  return (
    <AdminLayout title="Global Settings">
      <div className="card p-4 max-w-md space-y-4">
        {error && (
          <div className="p-3 rounded bg-red-50 dark:bg-red-950 text-sm text-red-700 dark:text-red-300">{error}</div>
        )}

        <label className="flex flex-col gap-1">
          <span className="text-sm font-medium text-[var(--color-text)]">Log Retention (days)</span>
          <span className="text-xs text-[var(--color-text-secondary)]">Logs older than this will be automatically deleted.</span>
          <div className="flex items-center gap-2">
            <TextInput
              type="number"
              min={1}
              value={settings.log_retention_days}
              onChange={(e) => update("log_retention_days", e.target.value)}
              className="w-24"
            />
            {saving && <Spinner size="sm" />}
            {savedKey === "log_retention_days" && <span className="text-xs text-success-600">Saved</span>}
          </div>
        </label>

        <label className="flex flex-col gap-1">
          <span className="text-sm font-medium text-[var(--color-text)]">Session Duration (hours)</span>
          <div className="flex items-center gap-2">
            <TextInput
              type="number"
              min={1}
              value={settings.session_duration_hours}
              onChange={(e) => update("session_duration_hours", e.target.value)}
              className="w-24"
            />
            {savedKey === "session_duration_hours" && <span className="text-xs text-success-600">Saved</span>}
          </div>
        </label>

        <label className="flex flex-col gap-1">
          <span className="text-sm font-medium text-[var(--color-text)]">Max Concurrent Sessions</span>
          <div className="flex items-center gap-2">
            <TextInput
              type="number"
              min={1}
              max={100}
              value={settings.max_concurrent_sessions}
              onChange={(e) => update("max_concurrent_sessions", e.target.value)}
              className="w-24"
            />
            {savedKey === "max_concurrent_sessions" && <span className="text-xs text-success-600">Saved</span>}
          </div>
        </label>

        <label className="flex items-center justify-between gap-4">
          <div>
            <span className="text-sm font-medium text-[var(--color-text)]">Email Verification Required</span>
            <p className="text-xs text-[var(--color-text-secondary)]">Require email verification before users can log in.</p>
          </div>
          <ToggleSwitch
            checked={settings.email_verification_required !== "false"}
            onChange={(v) => update("email_verification_required" as keyof GlobalSettings, v ? "true" : "false")}
          />
        </label>
      </div>
    </AdminLayout>
  );
}

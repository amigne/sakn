import { useState } from "react";
import AdminLayout from "@/components/admin/AdminLayout";
import { TextInput } from "@/components/ui";

interface Settings {
  log_retention_days: string;
  session_duration_hours: string;
  max_concurrent_sessions: string;
}

const defaults: Settings = {
  log_retention_days: "90",
  session_duration_hours: "24",
  max_concurrent_sessions: "10",
};

export default function AdminSettingsPage() {
  const [settings, setSettings] = useState<Settings>({ ...defaults });
  const [savedKey, setSavedKey] = useState<string | null>(null);

  const update = (key: keyof Settings, value: string) => {
    setSettings((s) => ({ ...s, [key]: value }));
    setSavedKey(key);
    setTimeout(() => setSavedKey(null), 1500);
  };

  return (
    <AdminLayout title="Global Settings">
      <div className="card p-4 max-w-md space-y-4">
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
      </div>
    </AdminLayout>
  );
}

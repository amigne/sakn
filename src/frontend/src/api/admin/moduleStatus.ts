import { api } from "@/services/api";

// ── Types ─────────────────────────────────────────────────────────────

export interface OuiSyncLastRun {
  started_at: string;
  finished_at: string | null;
  triggered_by: "scheduler" | "admin";
  added: number;
  changed: number;
  confirmed: number;
  files_failed: string[];
}

export interface OuiSyncHistoryEntry {
  started_at: string;
  finished_at: string | null;
  triggered_by: string;
  status: string;
  added: number;
  changed: number;
  confirmed: number;
  files_failed: string[];
  error_message: string | null;
}

export type ModuleStatusKind = "running" | "success" | "partial" | "alert" | "idle";

export interface ModuleStatus {
  status: ModuleStatusKind;
  last_run: OuiSyncLastRun | null;
  next_scheduled_run: string;
  consecutive_failures: Record<string, number>;
  total_records: number;
  history: OuiSyncHistoryEntry[];
}

export interface ModuleSettings {
  module: string;
  settings: Record<string, string>;
}

// ── API calls ──────────────────────────────────────────────────────────

/** Get the status for a specific module. Returns null if has_status=false. */
export async function getModuleStatus(toolName: string): Promise<ModuleStatus | null> {
  return api<ModuleStatus | null>(`/admin/modules/${toolName}/status`);
}

/** Get the settings for a specific module. */
export async function getModuleSettings(toolName: string): Promise<ModuleSettings> {
  return api<ModuleSettings>(`/admin/modules/${toolName}/settings`);
}

/** Update the settings for a specific module. */
export async function updateModuleSettings(
  toolName: string,
  settings: Record<string, string | number>,
): Promise<ModuleSettings> {
  return api<ModuleSettings>(`/admin/modules/${toolName}/settings`, {
    method: "PUT",
    body: { settings },
  });
}

/** Trigger a manual MAC OUI sync. */
export async function triggerOuiSync(): Promise<{ task_id: string; started_at: string }> {
  return api<{ task_id: string; started_at: string }>("/admin/oui/sync", {
    method: "POST",
  });
}

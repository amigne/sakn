import type {
  AccessPermission,
  AdminUser,
  AdminUserDetail,
  AuditLog,
  DnsServerPreset,
  GlobalSettings,
  Pagination,
  RateLimit,
  SecurityEventLog,
  ToolExecutionLog,
  ToolModule,
} from "@/types/admin";
import { api } from "./api";

// ── Users ──────────────────────────────────────────────────────────────────

export interface ListUsersParams {
  offset?: number;
  limit?: number;
  status?: string;
  search?: string;
  sort?: string;
  order?: string;
}

export async function listUsers(params: ListUsersParams = {}): Promise<{ users: AdminUser[]; pagination: Pagination }> {
  const sp = new URLSearchParams();
  if (params.offset !== undefined) sp.set("offset", String(params.offset));
  if (params.limit !== undefined) sp.set("limit", String(params.limit));
  if (params.status) sp.set("status", params.status);
  if (params.search) sp.set("search", params.search);
  if (params.sort) sp.set("sort", params.sort);
  if (params.order) sp.set("order", params.order);
  const qs = sp.toString();
  return api(`/admin/users${qs ? `?${qs}` : ""}`);
}

export async function getUser(userId: string): Promise<{ user: AdminUserDetail; sessions: unknown[] }> {
  return api(`/admin/users/${userId}`);
}

export async function blockUser(userId: string): Promise<{ user: AdminUser }> {
  return api(`/admin/users/${userId}/block`, { method: "PUT" });
}

export async function unblockUser(userId: string): Promise<{ user: AdminUser }> {
  return api(`/admin/users/${userId}/unblock`, { method: "PUT" });
}

export async function lockUser(userId: string): Promise<{ user: AdminUser }> {
  return api(`/admin/users/${userId}/lock`, { method: "PUT" });
}

export async function unlockUser(userId: string): Promise<{ user: AdminUser }> {
  return api(`/admin/users/${userId}/unlock`, { method: "PUT" });
}

export async function updateUserNotes(userId: string, notes: string): Promise<{ user: AdminUser }> {
  return api(`/admin/users/${userId}/notes`, { method: "PUT", body: { notes } });
}

export async function promoteUser(userId: string): Promise<{ user: AdminUser }> {
  return api(`/admin/users/${userId}/promote`, { method: "PUT" });
}

export async function demoteUser(userId: string): Promise<{ user: AdminUser }> {
  return api(`/admin/users/${userId}/demote`, { method: "PUT" });
}

export async function adminVerifyEmail(userId: string): Promise<{ user: AdminUser }> {
  return api(`/admin/users/${userId}/verify-email`, { method: "PUT" });
}

export async function getUserRateLimitStatus(userId: string): Promise<{
  role: string;
  soft_count: number;
  soft_limit: number;
  soft_window_s: number;
  hard_count: number;
  hard_limit: number;
  hard_window_s: number;
}> {
  return api(`/admin/users/${userId}/rate-limit-status`);
}

export async function deleteUser(userId: string): Promise<{ message_key: string }> {
  return api(`/admin/users/${userId}`, { method: "DELETE" });
}

// ── Tools ──────────────────────────────────────────────────────────────────

export async function listAdminTools(): Promise<{ tools: ToolModule[] }> {
  return api("/admin/tools");
}

export async function updateTool(toolName: string, body: { enabled: boolean }): Promise<{ tool: ToolModule }> {
  return api(`/admin/tools/${toolName}`, { method: "PUT", body });
}

// ── Permissions ────────────────────────────────────────────────────────────

export async function listRolePermissions(): Promise<{ permissions: AccessPermission[] }> {
  return api("/admin/role-permissions");
}

export async function updateRolePermissions(
  permissions: { id: string; allowed: boolean }[],
): Promise<{ permissions: AccessPermission[] }> {
  return api("/admin/role-permissions", { method: "PUT", body: { permissions } });
}

// ── Rate Limits ────────────────────────────────────────────────────────────

export async function listRateLimits(): Promise<{ rate_limits: RateLimit[] }> {
  return api("/admin/rate-limits");
}

export async function updateRateLimits(rateLimits: Partial<RateLimit>[]): Promise<{ rate_limits: RateLimit[] }> {
  return api("/admin/rate-limits", { method: "PUT", body: { rate_limits: rateLimits } });
}

// ── Modules ────────────────────────────────────────────────────────────────

export async function listModules(): Promise<{ modules: ToolModule[] }> {
  return api("/admin/modules");
}

export async function updateModule(moduleName: string, body: { enabled: boolean }): Promise<{ module: ToolModule }> {
  return api(`/admin/modules/${moduleName}`, { method: "PUT", body });
}

// ── DNS Server Presets ─────────────────────────────────────────────────────

export async function listDnsServers(toolName: string): Promise<{ tool: string; presets: DnsServerPreset[] }> {
  return api(`/admin/modules/${toolName}/dns-servers`);
}

export async function createDnsServer(
  toolName: string,
  body: { ip_address: string; description: string },
): Promise<{ preset: DnsServerPreset }> {
  return api(`/admin/modules/${toolName}/dns-servers`, { method: "POST", body });
}

export async function updateDnsServer(
  toolName: string,
  presetId: string,
  body: { ip_address?: string; description?: string },
): Promise<{ preset: DnsServerPreset }> {
  return api(`/admin/modules/${toolName}/dns-servers/${presetId}`, { method: "PUT", body });
}

export async function deleteDnsServer(toolName: string, presetId: string): Promise<{ deleted: boolean }> {
  return api(`/admin/modules/${toolName}/dns-servers/${presetId}`, { method: "DELETE" });
}

export async function reorderDnsServers(toolName: string, order: string[]): Promise<{ reordered: boolean }> {
  return api(`/admin/modules/${toolName}/dns-servers/reorder`, { method: "PUT", body: { order } });
}

// ── Logs ───────────────────────────────────────────────────────────────────

export interface LogQueryParams {
  offset?: number;
  limit?: number;
  tool?: string;
  user_id?: string;
  result?: string;
  event_type?: string;
  admin_id?: string;
  action?: string;
  entity_type?: string;
  from_date?: string;
  to_date?: string;
}

function buildLogParams(params: LogQueryParams): string {
  const sp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null) sp.set(k, String(v));
  }
  const qs = sp.toString();
  return qs ? `?${qs}` : "";
}

export async function listToolExecutions(params: LogQueryParams = {}): Promise<{
  tool_executions: ToolExecutionLog[];
  pagination: Pagination;
}> {
  return api(`/admin/logs/tool-executions${buildLogParams(params)}`);
}

export async function listSecurityEvents(params: LogQueryParams = {}): Promise<{
  security_events: SecurityEventLog[];
  pagination: Pagination;
}> {
  return api(`/admin/logs/security-events${buildLogParams(params)}`);
}

export async function listAuditLogs(params: LogQueryParams = {}): Promise<{
  audit_logs: AuditLog[];
  pagination: Pagination;
}> {
  return api(`/admin/logs/audit${buildLogParams(params)}`);
}

// ── Settings ───────────────────────────────────────────────────────────────

export async function getSettings(): Promise<{ settings: GlobalSettings }> {
  return api("/admin/settings");
}

export async function updateSettings(settings: Record<string, string>): Promise<{ settings: Record<string, string> }> {
  return api("/admin/settings", { method: "PUT", body: { settings } });
}

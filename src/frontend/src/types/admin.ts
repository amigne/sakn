import type { UserRole, UserStatus } from "./user";

export interface AdminUser {
  id: string;
  email: string;
  first_name: string | null;
  last_name: string | null;
  role: UserRole;
  status: UserStatus;
  email_verified: boolean;
  failed_login_attempts: number;
  locked_until: string | null;
  admin_notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface AdminUserDetail extends AdminUser {
  sessions: {
    id: string;
    ip_address: string;
    user_agent: string;
    created_at: string;
    last_activity_at: string;
  }[];
}

export function toolDisplayName(name: string): string {
  const map: Record<string, string> = {
    ping: "Ping",
    traceroute: "Traceroute",
    dns_lookup: "DNS Lookup",
    ssl_viewer: "TLS Certificate Viewer",
  };
  return map[name] ?? name.replace(/_/g, " ");
}

export interface AccessPermission {
  id?: string;
  tool_id?: string;
  tool_name: string;
  role: UserRole;
  allowed: boolean;
}

export interface RateLimit {
  id?: string;
  role: UserRole;
  tool_id: string | null;
  tool_name: string | null;
  soft_limit: number;
  hard_limit: number;
  window_seconds: number;
}

export interface DnsServerPreset {
  id: string;
  ip_address: string;
  description: string;
  sort_order: number;
}

export interface ToolModule {
  name: string;
  enabled: boolean;
  has_settings?: boolean;
}

export interface GlobalSettings {
  log_retention_days: string;
  session_duration_hours: string;
  max_concurrent_sessions: string;
  email_verification_required?: string;
}

export interface ToolExecutionLog {
  id: string;
  user_id: string | null;
  user_email: string | null;
  session_id: string | null;
  source_ip: string;
  tool_name: string;
  query: string;
  parameters: unknown;
  result: string;
  duration_ms: number;
  error_message: string | null;
  created_at: string;
}

export interface SecurityEventLog {
  id: string;
  event_type: string;
  source_ip: string;
  ip_address?: string;
  user_id: string | null;
  user_email: string | null;
  details: unknown;
  created_at: string;
}

export interface AuditLog {
  id: string;
  admin_id: string;
  admin_email: string | null;
  action: string;
  entity_type: string;
  entity_id: string;
  old_value: unknown;
  new_value: unknown;
  created_at: string;
}

export function auditActionLabel(action: string): string {
  const map: Record<string, string> = {
    "user.block": "Block User",
    "user.unblock": "Unblock User",
    "user.lock": "Lock User",
    "user.unlock": "Unlock User",
    "user.promote": "Promote to Admin",
    "user.demote": "Demote from Admin",
    "user.delete": "Delete User",
    "user.notes": "Update Notes",
    "user.verify_email": "Verify Email",
    "tool.update": "Toggle Tool",
    "module.update": "Toggle Module",
    "permission.update": "Update Permission",
    "rate_limit.update": "Update Rate Limit",
    "settings.update": "Update Setting",
  };
  return map[action] ?? action.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export function auditDetail(log: AuditLog): string {
  const action = log.action;
  const nv = log.new_value as Record<string, unknown> | null;
  const ov = log.old_value as Record<string, unknown> | null;
  if (action === "rate_limit.update" && nv) {
    const role = nv.role ?? "?";
    return `Role ${role}: soft=${nv.soft_limit ?? "?"}/s hard=${nv.hard_limit ?? "?"}/h${ov ? ` (was soft=${ov.soft_limit}/s hard=${ov.hard_limit}/h)` : ""}`;
  }
  if (action === "permission.update" && nv) {
    return `Role ${nv.role} tool ${nv.tool_id?.toString().slice(-8)} allowed=${nv.allowed}`;
  }
  if (
    (action === "user.block" ||
      action === "user.unblock" ||
      action === "user.lock" ||
      action === "user.unlock" ||
      action === "user.promote" ||
      action === "user.demote") &&
    nv
  ) {
    const changed = Object.entries(nv)
      .filter(([k, v]) => ov && ov[k] !== v)
      .map(([k, v]) => `${k}=${v}`)
      .join(", ");
    return changed || `${action.replace("user.", "")} user`;
  }
  if (action === "settings.update" && nv) {
    return Object.entries(nv)
      .map(([k, v]) => `${k}=${v}`)
      .join(", ");
  }
  if (nv && Object.keys(nv).length > 0) {
    return JSON.stringify(nv);
  }
  return "";
}

export interface Pagination {
  offset: number;
  limit: number;
  total: number;
}

import type { UserRole, UserStatus } from "./user";

export interface AdminUser {
  id: string;
  email: string;
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

export interface AccessPermission {
  tool_name: string;
  role: UserRole;
  allowed: boolean;
}

export interface RateLimit {
  role: UserRole;
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
}

export interface GlobalSettings {
  log_retention_days: string;
  session_duration_hours: string;
  max_concurrent_sessions: string;
}

export interface ToolExecutionLog {
  id: string;
  user_id: string;
  user_email: string;
  tool_name: string;
  target: string;
  status: string;
  duration_ms: number;
  created_at: string;
}

export interface SecurityEventLog {
  id: string;
  event_type: string;
  user_id: string | null;
  user_email: string | null;
  ip_address: string;
  details: string;
  created_at: string;
}

export interface AuditLog {
  id: string;
  admin_id: string;
  admin_email: string;
  action: string;
  entity_type: string;
  entity_id: string;
  details: string;
  created_at: string;
}

export interface Pagination {
  offset: number;
  limit: number;
  total: number;
}

export type UserRole = "visitor" | "authenticated" | "administrator";
export type UserStatus = "pending" | "active" | "blocked" | "locked";
export type ThemeMode = "light" | "dark" | "system";

export interface User {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  role: UserRole;
  status: UserStatus;
  email_verified: boolean;
  locale: string;
  created_at: string;
}

export interface Session {
  id: string;
  ip_address: string;
  user_agent: string;
  created_at: string;
  last_activity_at: string;
  current: boolean;
}

export interface Preferences {
  language: string;
  locale: string;
  theme: ThemeMode;
  display_mode: "table" | "text";
}

import type { User } from "@/types/user";
import { api } from "./api";

interface RegisterParams {
  email: string;
  password: string;
  password_confirm: string;
  first_name: string;
  last_name: string;
  locale?: string;
}

interface LoginResult {
  user: User;
}

export async function register(params: RegisterParams): Promise<{ message_key: string; message: string }> {
  return api("/auth/register", { method: "POST", body: params });
}

export async function login(email: string, password: string): Promise<LoginResult> {
  return api("/auth/login", { method: "POST", body: { email, password } });
}

export async function logout(): Promise<{ message_key: string; message: string }> {
  return api("/auth/logout", { method: "POST" });
}

export async function verifyEmail(token: string): Promise<{ message_key: string; message: string }> {
  return api("/auth/verify-email", { method: "POST", body: { token } });
}

export async function resendVerification(): Promise<{ message_key: string; message: string }> {
  return api("/auth/resend-verification", { method: "POST" });
}

export async function requestPasswordReset(email: string): Promise<{ message_key: string; message: string }> {
  return api("/auth/request-password-reset", { method: "POST", body: { email } });
}

export async function resetPassword(
  token: string,
  password: string,
  password_confirm: string,
): Promise<{ message_key: string; message: string }> {
  return api("/auth/reset-password", { method: "POST", body: { token, password, password_confirm } });
}

export async function fetchCsrfToken(): Promise<{ message_key: string; message: string }> {
  return api("/auth/csrf");
}

interface ProfileUpdate {
  first_name?: string | null;
  last_name?: string | null;
}

export async function updateProfile(updates: ProfileUpdate): Promise<{ user: User }> {
  return api("/account/profile", { method: "PUT", body: updates });
}

export async function fetchCurrentUser(): Promise<User | null> {
  try {
    const result = await api<{ user: User }>("/auth/me");
    return result.user;
  } catch {
    return null;
  }
}

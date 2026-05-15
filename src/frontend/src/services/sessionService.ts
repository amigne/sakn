import { api } from "./api";
import type { Session } from "@/types/user";

export async function listSessions(): Promise<{ sessions: Session[] }> {
  return api("/sessions");
}

export async function revokeSession(sessionId: string): Promise<{ message_key: string; message: string }> {
  return api(`/sessions/${sessionId}`, { method: "DELETE" });
}

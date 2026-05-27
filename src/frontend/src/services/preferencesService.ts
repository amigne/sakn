import type { Preferences } from "@/types/user";
import { api } from "./api";

export async function getPreferences(): Promise<{ preferences: Preferences }> {
  return api("/preferences");
}

export async function updatePreferences(updates: Partial<Preferences>): Promise<{ preferences: Preferences }> {
  return api("/preferences", { method: "PUT", body: updates });
}

import { api } from "@/services/api";

// ── Types ─────────────────────────────────────────────────────────────

export interface MacOuiExecuteRequest {
  ouis: string[];
}

export interface MacOuiHistoryEntry {
  previous_organization: string;
  new_organization: string;
  previous_address: string | null;
  new_address: string | null;
  change_type: "name_change" | "address_change" | "revoked";
  detected_at: string;
}

export interface MacOuiResultRow {
  input: string;
  oui_display: string;
  result: {
    oui_type: "MA-L" | "MA-M" | "MA-S";
    organization: string;
    address: string;
    first_seen: string;
    last_seen: string;
  } | null;
  ambiguous_extends_ma_m: boolean;
  ambiguous_extends_ma_s: boolean;
  history: MacOuiHistoryEntry[];
}

export interface MacOuiRejected {
  index: number;
  sample: string;
  reason: "invalid_format" | "invalid_length" | "non_hex_characters";
}

export interface MacOuiParseStats {
  total_inputs: number;
  valid: number;
  rejected: number;
  unique: number;
}

export interface MacOuiExecuteResponse {
  results: MacOuiResultRow[];
  rejected: MacOuiRejected[];
  parse_stats: MacOuiParseStats;
}

export interface MacOuiHistoryPage {
  items: MacOuiHistoryEntry[];
  total: number;
  offset: number;
  limit: number;
  has_more: boolean;
}

interface MacOuiEnvelope {
  result: {
    success: boolean;
    data: MacOuiExecuteResponse;
    error: string | null;
    duration_ms: number;
    module_deployed_at?: string;
  };
}

// ── API calls ─────────────────────────────────────────────────────────

export async function executeMacOuiLookup(req: MacOuiExecuteRequest): Promise<{
  data: MacOuiExecuteResponse;
  module_deployed_at?: string;
}> {
  const envelope = await api<MacOuiEnvelope>("/tools/mac_oui/execute", {
    method: "POST",
    body: req,
  });

  if (!envelope.result.success) {
    throw new Error(envelope.result.error ?? "Unknown error");
  }

  return {
    data: envelope.result.data,
    module_deployed_at: envelope.result.module_deployed_at,
  };
}

/** Fetch a paginated page of history entries for a specific OUI. */
export async function fetchMacOuiHistory(
  oui: string,
  oui_type: string,
  offset: number,
  limit: number,
): Promise<MacOuiHistoryPage> {
  return api<MacOuiHistoryPage>(
    `/tools/mac_oui/history?oui=${encodeURIComponent(oui)}&oui_type=${encodeURIComponent(oui_type)}&offset=${offset}&limit=${limit}`,
  );
}

export { api };

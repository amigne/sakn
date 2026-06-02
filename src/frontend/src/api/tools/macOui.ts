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

interface MacOuiEnvelope {
  result: {
    success: boolean;
    data: MacOuiExecuteResponse;
    error: string | null;
    duration_ms: number;
  };
}

// ── API call ──────────────────────────────────────────────────────────

export async function executeMacOuiLookup(req: MacOuiExecuteRequest): Promise<MacOuiExecuteResponse> {
  const envelope = await api<MacOuiEnvelope>("/tools/mac_oui/execute", {
    method: "POST",
    body: req,
  });

  if (!envelope.result.success) {
    // Backend returned soft error (success=false in 200 OK).
    // HTTP 4xx/5xx errors are already thrown as ApiError by api<…>().
    throw new Error(envelope.result.error ?? "Unknown error");
  }

  return envelope.result.data;
}

export { api };

export interface PingParams {
  target: string;
  count: number;
  timeout: number;
  packet_size: number;
  df_bit: boolean;
  dscp: number;
  max_duration: number;
}

export interface TracerouteParams {
  target: string;
  protocol: "udp" | "icmp" | "tcp";
  port: number;
  probes_per_hop: number;
  timeout: number;
  max_distance: number;
  dns_resolution: boolean;
}

export interface DnsLookupParams {
  domain: string;
  record_types: string[];
  resolver: string;
  recursive_cname: boolean;
}

export interface SslViewerParams {
  url: string;
  sni: string;
}

export type ToolParams = PingParams | TracerouteParams | DnsLookupParams | SslViewerParams;

export interface PingResult {
  seq: number;
  status: "ok" | "timeout" | "error";
  rtt_ms?: number;
  ttl?: number;
  bytes?: number;
  error_type?: string;
  from_ip?: string;
}

export interface PingSummary {
  transmitted: number;
  received: number;
  lost: number;
  loss_pct: number;
  rtt_min_ms: number | null;
  rtt_avg_ms: number | null;
  rtt_max_ms: number | null;
}

export interface TracerouteProbe {
  rtt_ms: number | null;
  status: "ok" | "timeout";
}

export interface TracerouteHop {
  ip: string | null;
  hostname: string | null;
  probes: TracerouteProbe[];
  multipath?: boolean;
  paths?: { ip: string; hostname: string | null; probes: TracerouteProbe[] }[];
  reached?: boolean;
}

export interface DnsRecord {
  type: string;
  value: string;
  ttl: number;
  owner?: string;
}

export interface DnsResult {
  domain: string;
  records: Record<string, DnsRecord[]>;
  cname_chain: string[] | null;
  cname_records: Record<string, Record<string, DnsRecord[]>> | null;
}

export interface SslCertInfo {
  subject: string;
  issuer: string;
  valid_from: string;
  valid_until: string;
  sans: string[];
  key_algorithm: string;
  key_size: number;
  signature_algorithm: string;
  fingerprint_sha256: string;
  fingerprint_sha1: string;
  extended_key_usage: string[];
  is_expired: boolean;
  is_self_signed: boolean;
  name_mismatch: boolean;
  is_weak_key: boolean;
  is_untrusted: boolean;
  is_trusted_root: boolean;
  missing_issuer: boolean;
  missing_issuer_name: string | null;
  no_common_name: boolean;
  empty_subject: boolean;
  revocation_status: string;
  revocation_detail: string;
  serial_number: string;
  key_usage: string[];
  is_ca: boolean;
  bc_path_length: number | null;
  aia_entries: { method: string; url: string }[];
  crl_urls: string[];
  ski: string;
  aki: string;
  policy_oids: string[];
}

export interface SslResult {
  url: string;
  tls_version: string;
  cipher_suite: string;
  certificates: SslCertInfo[];
  chain_valid: boolean;
  warnings: { message: string; variant: "error" | "warning" }[];
}

export type ToolName = "ping" | "traceroute" | "dns_lookup" | "ssl_viewer";

export type ExecutionStatus = "idle" | "running" | "completed" | "stopped" | "error";

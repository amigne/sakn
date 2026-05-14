import { useState, useCallback, useRef } from "react";
import type { PingResult, TracerouteHop, DnsResult, SslResult, ExecutionStatus } from "@/types/tool";

// ── Fake data generators ──────────────────────────────────────────

function fakeDnsResults(): DnsResult {
  return {
    domain: "example.com",
    records: {
      A: [
        { type: "A", value: "93.184.216.34", ttl: 300 },
        { type: "A", value: "93.184.216.35", ttl: 300 },
      ],
      AAAA: [
        { type: "AAAA", value: "2606:2800:220:1:248:1893:25c8:1946", ttl: 300 },
      ],
      MX: [
        { type: "MX", value: "0 mail.example.com.", ttl: 3600 },
      ],
      NS: [
        { type: "NS", value: "ns1.example.com.", ttl: 86400 },
        { type: "NS", value: "ns2.example.com.", ttl: 86400 },
      ],
      TXT: [
        { type: "TXT", value: '"v=spf1 -all"', ttl: 300 },
      ],
      SOA: [
        { type: "SOA", value: "ns1.example.com. admin.example.com. 2026051401 7200 3600 604800 86400", ttl: 86400 },
      ],
    },
    cname_chain: ["www.example.com.", "example.com."],
  };
}

function fakeSslResults(): SslResult {
  return {
    url: "https://example.com",
    tls_version: "TLS 1.3",
    cipher_suite: "TLS_AES_256_GCM_SHA384",
    certificates: [
      {
        subject: "CN=example.com",
        issuer: "CN=DigiCert Global G2 TLS RSA SHA256 2020 CA1",
        valid_from: "2026-01-15T00:00:00Z",
        valid_until: "2027-01-15T23:59:59Z",
        sans: ["example.com", "www.example.com"],
        key_algorithm: "RSA",
        key_size: 2048,
        signature_algorithm: "SHA256withRSA",
        fingerprint_sha256: "AB:CD:EF:01:23:45:67:89:AB:CD:EF:01:23:45:67:89:AB:CD:EF:01:23:45:67:89:AB:CD:EF:01:23:45:AB",
        fingerprint_sha1: "AB:CD:EF:01:23:45:67:89:AB:CD:EF:01:23:45:67:89:AB:CD:EF:01",
        extended_key_usage: ["TLS Web Server Authentication", "TLS Web Client Authentication"],
        is_expired: false,
        is_self_signed: false,
        name_mismatch: false,
        is_weak_key: false,
      },
      {
        subject: "CN=DigiCert Global G2 TLS RSA SHA256 2020 CA1",
        issuer: "CN=DigiCert Global Root CA",
        valid_from: "2021-04-14T00:00:00Z",
        valid_until: "2031-04-13T23:59:59Z",
        sans: [],
        key_algorithm: "RSA",
        key_size: 2048,
        signature_algorithm: "SHA256withRSA",
        fingerprint_sha256: "CD:EF:01:23:45:67:89:AB:CD:EF:01:23:45:67:89:AB:CD:EF:01:23:45:67:89:AB:CD:EF:01:23:45:CD",
        fingerprint_sha1: "CD:EF:01:23:45:67:89:AB:CD:EF:01:23:45:67:89:AB:CD:EF:01:CD",
        extended_key_usage: ["TLS Web Server Authentication", "TLS Web Client Authentication"],
        is_expired: false,
        is_self_signed: false,
        name_mismatch: false,
        is_weak_key: false,
      },
    ],
    chain_valid: true,
    warnings: [],
  };
}

function fakePingResults(count: number): PingResult[] {
  const results: PingResult[] = [];
  for (let i = 1; i <= count; i++) {
    if (Math.random() > 0.15) {
      results.push({
        seq: i,
        status: "ok",
        rtt_ms: +(10 + Math.random() * 20).toFixed(1),
        ttl: 50 + Math.floor(Math.random() * 15),
        bytes: 64,
      });
    } else {
      results.push({ seq: i, status: "timeout" });
    }
  }
  return results;
}

function fakeTracerouteHops(maxHops: number): TracerouteHop[] {
  const hops: TracerouteHop[] = [];
  const gateways = [
    { ip: "192.168.1.1", hostname: "router.home" },
    { ip: "10.0.0.1", hostname: "gw.isp.net" },
    { ip: "72.14.237.1", hostname: null },
    { ip: "142.251.37.1", hostname: null },
    { ip: "8.8.8.8", hostname: "dns.google" },
  ];

  for (let i = 0; i < Math.min(maxHops, gateways.length + 2); i++) {
    const gw = gateways[i];
    if (i === 2 && Math.random() > 0.5) {
      hops.push({
        ip: null, hostname: null,
        probes: Array(3).fill(null).map(() => ({ rtt_ms: null, status: "timeout" as const })),
      });
    } else if (gw) {
      hops.push({
        ip: gw.ip,
        hostname: gw.hostname,
        probes: Array(3).fill(null).map(() => ({ rtt_ms: +(2 + Math.random() * 30).toFixed(1), status: "ok" as const })),
        reached: i === gateways.length - 1,
      });
    }
  }
  return hops;
}

// ── Hooks ─────────────────────────────────────────────────────────

export function useMockToolExecution() {
  const [status, setStatus] = useState<ExecutionStatus>("idle");
  const [error, setError] = useState<string | null>(null);
  const [duration, setDuration] = useState<number | null>(null);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const execute = useCallback(async (toolName: string, _params: Record<string, unknown>) => {
    if (timeoutRef.current) clearTimeout(timeoutRef.current);
    setStatus("running");
    setError(null);
    setDuration(null);

    const start = performance.now();

    return new Promise<{ data: DnsResult | SslResult }>((resolve) => {
      timeoutRef.current = setTimeout(() => {
        setStatus("completed");
        setDuration(performance.now() - start);
        if (toolName === "dns_lookup") {
          resolve({ data: fakeDnsResults() });
        } else {
          resolve({ data: fakeSslResults() });
        }
      }, 400 + Math.random() * 400);
    });
  }, []);

  const reset = useCallback(() => {
    if (timeoutRef.current) clearTimeout(timeoutRef.current);
    setStatus("idle");
    setError(null);
    setDuration(null);
  }, []);

  return { status, error, duration, execute, reset };
}

export function useMockPingWebSocket() {
  const [status, setStatus] = useState<ExecutionStatus>("idle");
  const [results, setResults] = useState<PingResult[]>([]);
  const [summary, setSummary] = useState<Record<string, unknown> | null>(null);
  const [terminatedBy, setTerminatedBy] = useState<string | null>(null);
  const [duration, setDuration] = useState<number | null>(null);
  const [currentSeq, setCurrentSeq] = useState(0);
  const timersRef = useRef<ReturnType<typeof setTimeout>[]>([]);
  const cancelledRef = useRef(false);

  const clearTimers = useCallback(() => {
    timersRef.current.forEach(clearTimeout);
    timersRef.current = [];
  }, []);

  const start = useCallback((params: Record<string, unknown>) => {
    clearTimers();
    cancelledRef.current = false;
    setStatus("running");
    setResults([]);
    setSummary(null);
    setTerminatedBy(null);
    setDuration(null);
    setCurrentSeq(0);

    const startTime = performance.now();
    const count = (params.count as number) || 4;
    const allResults: PingResult[] = fakePingResults(count);

    allResults.forEach((result, i) => {
      const timer = setTimeout(() => {
        if (cancelledRef.current) return;
        setCurrentSeq(i + 1);
        setResults((prev) => [...prev, result]);

        if (i === count - 1) {
          const d = performance.now() - startTime;
          setDuration(d);
          if (!cancelledRef.current) {
            setStatus("completed");
            setTerminatedBy("completed");
            const finalResults = [...allResults.slice(0, i), result];
            const received = finalResults.filter((r) => r.status === "ok").length;
            const rtts = finalResults.filter((r) => r.rtt_ms != null).map((r) => r.rtt_ms!);
            setSummary({
              transmitted: count,
              received,
              lost: count - received,
              loss_pct: +(((count - received) / count) * 100).toFixed(1),
              rtt_min_ms: rtts.length ? Math.min(...rtts) : null,
              rtt_avg_ms: rtts.length ? +(rtts.reduce((a, b) => a + b, 0) / rtts.length).toFixed(1) : null,
              rtt_max_ms: rtts.length ? Math.max(...rtts) : null,
              rtt_stddev_ms: null,
            });
          }
        }
      }, (i + 1) * 600);
      timersRef.current.push(timer);
    });
  }, [clearTimers]);

  const cancel = useCallback(() => {
    cancelledRef.current = true;
    clearTimers();
    setStatus("stopped");
    setTerminatedBy("user");
  }, [clearTimers]);

  const reset = useCallback(() => {
    clearTimers();
    setStatus("idle");
    setResults([]);
    setSummary(null);
    setTerminatedBy(null);
    setDuration(null);
    setCurrentSeq(0);
  }, [clearTimers]);

  return { status, results, summary, terminatedBy, duration, currentSeq, start, cancel, reset };
}

export function useMockTracerouteWebSocket() {
  const [status, setStatus] = useState<ExecutionStatus>("idle");
  const [results, setResults] = useState<TracerouteHop[]>([]);
  const [summary, setSummary] = useState<Record<string, unknown> | null>(null);
  const [terminatedBy, setTerminatedBy] = useState<string | null>(null);
  const [duration, setDuration] = useState<number | null>(null);
  const [currentSeq, setCurrentSeq] = useState(0);
  const timersRef = useRef<ReturnType<typeof setTimeout>[]>([]);
  const cancelledRef = useRef(false);

  const clearTimers = useCallback(() => {
    timersRef.current.forEach(clearTimeout);
    timersRef.current = [];
  }, []);

  const start = useCallback((params: Record<string, unknown>) => {
    clearTimers();
    cancelledRef.current = false;
    setStatus("running");
    setResults([]);
    setSummary(null);
    setTerminatedBy(null);
    setDuration(null);
    setCurrentSeq(0);

    const startTime = performance.now();
    const maxHops = (params.max_distance as number) || 30;
    const hops = fakeTracerouteHops(maxHops);

    hops.forEach((hop, idx) => {
      const timer = setTimeout(() => {
        if (cancelledRef.current) return;
        setCurrentSeq(idx + 1);
        setResults((prev) => [...prev, hop]);
        if (idx === hops.length - 1 || hop.reached) {
          const d = performance.now() - startTime;
          setDuration(d);
          if (!cancelledRef.current) {
            setStatus("completed");
            setTerminatedBy("completed");
            setSummary({ hops_probed: idx + 1, destination_reached: !!hop.reached, total_time_ms: d });
          }
        }
      }, (idx + 1) * 800);
      timersRef.current.push(timer);
    });
  }, [clearTimers]);

  const cancel = useCallback(() => {
    cancelledRef.current = true;
    clearTimers();
    setStatus("stopped");
    setTerminatedBy("user");
  }, [clearTimers]);

  const reset = useCallback(() => {
    clearTimers();
    setStatus("idle");
    setResults([]);
    setSummary(null);
    setTerminatedBy(null);
    setDuration(null);
    setCurrentSeq(0);
  }, [clearTimers]);

  return { status, results, summary, terminatedBy, duration, currentSeq, start, cancel, reset };
}

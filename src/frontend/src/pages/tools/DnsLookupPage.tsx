import { useState, useCallback, useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";
import PageLayout from "@/components/layout/PageLayout";
import ToolForm from "@/components/tool/ToolForm";
import ToolOutput from "@/components/tool/ToolOutput";
import { useToolExecution } from "@/hooks/useToolExecution";
import { useToolStore } from "@/stores/toolStore";
import { TextInput, Checkbox } from "@/components/ui";
import { api } from "@/services/api";
import type { DnsResult, DnsRecord } from "@/types/tool";

interface DnsFormData {
  domain: string;
  record_types: string[];
  resolver: string;
  recursive_cname: boolean;
}

interface DnsServerOption {
  value: string;
  label: string;
}

const defaults: DnsFormData = {
  domain: "",
  record_types: ["A", "AAAA", "CNAME"],
  resolver: "__system__",
  recursive_cname: true,
};

const RECORD_TYPES = ["A", "AAAA", "CNAME", "MX", "NS", "TXT", "SRV", "SOA", "PTR", "CAA"];

// ── DNS Server combobox ───────────────────────────────────────────

interface DnsServerInputProps {
  servers: { value: string; label: string }[];
  value: string;
  onChange: (v: string) => void;
  onEnter: () => void;
}

function DnsServerInput({ servers, value, onChange, onEnter }: DnsServerInputProps) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [focusedIdx, setFocusedIdx] = useState(-1);
  const inputRef = useRef<HTMLInputElement>(null);
  const displayValue = value === "__system__" ? "" : value;
  const presets = servers.filter(s => s.value !== "__system__");
  const filtered = displayValue ? presets.filter(s => s.value.includes(displayValue)) : presets;

  const select = (v: string) => { onChange(v); setOpen(false); setFocusedIdx(-1); inputRef.current?.focus(); };

  return (
    <label className="flex flex-col gap-1 relative">
      <span className="text-xs font-medium text-[var(--color-text-secondary)]">{t("tools.dns.resolver_label")}</span>
      <input
        ref={inputRef}
        type="text"
        className="focus-ring w-full rounded-md border bg-[var(--color-surface)] px-3 py-2 text-sm text-[var(--color-text)] placeholder:text-[var(--color-text-secondary)] border-[var(--color-border)] dark:[color-scheme:dark]"
        placeholder={t("tools.dns.system_default_or_enter_ip")}
        value={displayValue}
        onChange={(e) => { onChange(e.target.value || "__system__"); setOpen(true); setFocusedIdx(-1); }}
        onFocus={() => { setOpen(true); setFocusedIdx(-1); }}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
        onKeyDown={(e) => {
          if (e.key === "Enter") { setOpen(false); inputRef.current?.blur(); if (!displayValue || filtered.length === 0) onEnter(); }
          else if (e.key === "ArrowDown") { e.preventDefault(); setFocusedIdx(i => Math.min(i + 1, filtered.length - 1)); }
          else if (e.key === "ArrowUp") { e.preventDefault(); setFocusedIdx(i => Math.max(i - 1, -1)); }
          else if (e.key === "Escape") { setOpen(false); setFocusedIdx(-1); }
        }}
      />
      {open && filtered.length > 0 && (
        <ul className="absolute top-full left-0 right-0 z-50 mt-1 max-h-48 overflow-y-auto rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] shadow-lg text-sm">
          {filtered.map((s, i) => (
            <li
              key={s.value}
              className={`px-3 py-1.5 cursor-pointer font-mono text-[var(--color-text)] ${i === focusedIdx ? "bg-primary-100 dark:bg-primary-800" : "hover:bg-[var(--color-surface-alt)]"}`}
              onMouseDown={() => select(s.value)}
              onMouseEnter={() => setFocusedIdx(i)}
            >
              <span>{s.value}</span>
              <span className="ml-2 text-[var(--color-text-secondary)] text-xs">{s.label}</span>
            </li>
          ))}
        </ul>
      )}
    </label>
  );
}

export default function DnsLookupPage() {
  const { t } = useTranslation();
  const [form, setForm] = useState<DnsFormData>({ ...defaults });
  const [errors, setErrors] = useState<Partial<Record<keyof DnsFormData, string>>>({});
  const { status, data, error, duration, execute, reset } = useToolExecution();
  const [dnsServers, setDnsServers] = useState<DnsServerOption[]>([
    { value: "__system__", label: "" },
  ]);

  useEffect(() => {
    useToolStore.getState().setActiveTool("dns_lookup");
  }, []);

  useEffect(() => {
    api<{ servers?: DnsServerOption[] }>("/tools/dns_lookup/dns-servers")
      .then((res) => {
        if (res.servers?.length) setDnsServers([{ value: "__system__", label: "" }, ...res.servers]);
      })
      .catch(() => {});
  }, []);

  const validate = (): boolean => {
    const errs: typeof errors = {};
    if (!form.domain.trim()) errs.domain = t("tools.dns.domain_required");
    if (form.record_types.length === 0) errs.record_types = t("tools.dns.select_record_type");
    setErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const handleStart = useCallback(async () => {
    if (!validate()) return;
    await execute("dns_lookup", { ...form, target: form.domain });
  }, [form, execute]);

  const handleReset = useCallback(() => {
    setForm({ ...defaults });
    setErrors({});
    reset();
  }, [reset]);

  const update = (field: keyof DnsFormData, value: unknown) => {
    setForm((f) => ({ ...f, [field]: value }));
    setErrors((e) => ({ ...e, [field]: undefined }));
  };

  const toggleRecordType = (rt: string, checked: boolean | "indeterminate") => {
    if (checked === "indeterminate") return;
    const newTypes = checked
      ? [...form.record_types, rt]
      : form.record_types.filter((t) => t !== rt);
    update("record_types", newTypes);
  };

  const isRunning = status === "running";

  const dnsResult = (data ?? null) as DnsResult | null;

  /** Records from the original query that belong to the queried domain. */
  const ownRecords = (type: string): DnsRecord[] =>
    (dnsResult?.records[type] ?? []).filter(r => !r.owner || r.owner === dnsResult?.domain);

  /** Sorted record type entries: non-empty first, then empty. */
  const sortedOwnEntries = (): [string, DnsRecord[]][] => {
    if (!dnsResult) return [];
    return (Object.keys(dnsResult.records) as string[])
      .map(type => [type, ownRecords(type)] as [string, DnsRecord[]])
      .sort(([, a], [, b]) => {
        if (a.length === 0 && b.length > 0) return 1;
        if (a.length > 0 && b.length === 0) return -1;
        return 0;
      });
  };

  /** Sorted record types for a CNAME hop section. */
  const sortedHopEntries = (hopRecords: Record<string, DnsRecord[]>) =>
    Object.entries(hopRecords).sort(([, a], [, b]) => {
      if (a.length === 0 && b.length > 0) return 1;
      if (a.length > 0 && b.length === 0) return -1;
      return 0;
    });

  const renderRecords = (records: DnsRecord[], ownerLabel?: string) => {
    if (records.length === 0) {
      return <p className="text-xs text-error-600 dark:text-error-500 font-mono">{t("tools.dns.no_records")}</p>;
    }
    return records.map((r: DnsRecord, i: number) => {
      const showOwner = r.owner && r.owner !== ownerLabel;
      return (
        <div key={i} className="font-mono text-sm text-[var(--color-text)] flex flex-wrap gap-x-4">
          {showOwner && <span className="text-orange-600 dark:text-orange-400">{r.owner}.</span>}
          <span className="text-primary-600 dark:text-primary-400">{r.type}</span>
          <span>{r.value}</span>
          <span className="text-[var(--color-text-secondary)]">TTL: {r.ttl}</span>
        </div>
      );
    });
  };

  const copyResults = () => {
    if (!dnsResult) return;
    const lines: string[] = [];

    // Original domain's own records
    lines.push(`;; ${dnsResult.domain}`);
    for (const [type, recs] of sortedOwnEntries()) {
      lines.push(`  ${type}:`);
      if (recs.length === 0) lines.push("    (no records)");
      else recs.forEach(r => {
        const pfx = r.owner && r.owner !== dnsResult.domain ? `${r.owner}. ` : "";
        lines.push(`    ${pfx}${r.value}  TTL: ${r.ttl}`);
      });
    }

    if (dnsResult.cname_chain) {
      lines.push("\n;; CNAME Chain:");
      dnsResult.cname_chain.forEach(c => lines.push(c));
    }

    if (dnsResult.cname_records) {
      for (const [hop, hopRecords] of Object.entries(dnsResult.cname_records)) {
        lines.push(`\n;; ${hop} (CNAME chain)`);
        for (const [type, recs] of sortedHopEntries(hopRecords)) {
          lines.push(`  ${type}:`);
          if (recs.length === 0) lines.push("    (no records)");
          else recs.forEach(r => {
            const pfx = r.owner && r.owner !== hop ? `${r.owner}. ` : "";
            lines.push(`    ${pfx}${r.value}  TTL: ${r.ttl}`);
          });
        }
      }
    }

    navigator.clipboard.writeText(lines.join("\n")).catch(() => {});
  };

  return (
    <PageLayout>
      <ToolForm
        title={t("tools.dns.name")}
        advancedOpen={false}
        isRunning={isRunning}
        onStart={handleStart}
        onReset={handleReset}
        startLabel={t("tools.dns.start_label")}
        outputControls={
          <span className="text-xs text-[var(--color-text-secondary)]">
            {duration !== null ? `${(duration / 1000).toFixed(1)}s` : ""}
          </span>
        }
      >
        <label className="flex flex-col gap-1">
          <span className="text-xs font-medium text-[var(--color-text-secondary)]">{t("tools.dns.target_label")}</span>
          <TextInput type="text" placeholder="example.com" value={form.domain} onChange={(e) => update("domain", e.target.value)} error={errors.domain} onKeyDown={(e) => { if (e.key === "Enter") handleStart(); }} />
        </label>
        <DnsServerInput
          servers={dnsServers}
          value={form.resolver}
          onChange={(v) => update("resolver", v)}
          onEnter={handleStart}
        />
        <label className="flex flex-col gap-1">
          <span className="text-xs font-medium text-[var(--color-text-secondary)]">{t("tools.dns.cname_label")}</span>
          <Checkbox checked={form.recursive_cname} onChange={(v) => update("recursive_cname", v === true)} label={t("tools.dns.cname_desc")} />
        </label>
        <div className="sm:col-span-2 lg:col-span-4">
          <span className="text-xs font-medium text-[var(--color-text-secondary)]">{t("tools.dns.record_type_label")}</span>
          {errors.record_types && <p className="text-xs text-error-600 dark:text-error-500">{errors.record_types}</p>}
          <div className="flex flex-wrap gap-3 mt-1">
            {RECORD_TYPES.map((rt) => (
              <Checkbox
                key={rt}
                checked={form.record_types.includes(rt)}
                onChange={(c) => toggleRecordType(rt, c)}
                label={rt}
              />
            ))}
          </div>
        </div>
      </ToolForm>

      <ToolOutput
        status={status}
        error={error}
        onCopy={dnsResult ? copyResults : undefined}
      >
        {dnsResult && status === "completed" && (
          <div className="space-y-3">
            {dnsResult.dnssec_ad_flag && (
              <div className="card p-2 bg-success-50 dark:bg-success-50/10 border-success-500">
                <span className="text-xs font-mono text-success-600 dark:text-success-500">{t("tools.dns.dnssec_ad_flag")}</span>
              </div>
            )}
            {dnsResult.cname_chain && (
              <div className="card p-3">
                <h3 className="text-xs font-semibold text-[var(--color-text-secondary)] uppercase mb-2">{t("tools.dns.cname_chain_title")}</h3>
                <div className="font-mono text-sm text-[var(--color-text)]">
                  {dnsResult.cname_chain.map((hop, i) => (
                    <span key={i} className="text-primary-600 dark:text-primary-400">
                      {i > 0 && " -> "}{hop}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Original domain section */}
            <div className="card p-3">
              <h3 className="text-xs font-semibold text-primary-600 dark:text-primary-400 uppercase mb-3">
                {dnsResult.domain}
              </h3>
              <div className="space-y-2">
                {sortedOwnEntries().map(([type, recs]) => (
                  <div key={type}>
                    <h4 className="text-[11px] font-semibold text-[var(--color-text-secondary)] uppercase mb-1">{t("tools.dns.records_section", { type })}</h4>
                    {renderRecords(recs, dnsResult.domain)}
                  </div>
                ))}
              </div>
            </div>

            {/* CNAME chain hop sections */}
            {dnsResult.cname_records && Object.entries(dnsResult.cname_records).map(([hop, hopRecords]) => {
              const allRecs = Object.values(hopRecords).flat();
              if (allRecs.length === 0) return null;
              return (
              <div key={hop} className="card p-3 border-l-2 border-primary-400">
                <h3 className="text-xs font-semibold text-primary-600 dark:text-primary-400 uppercase mb-2">
                  {hop} <span className="text-[var(--color-text-secondary)] font-normal normal-case">{t("tools.dns.cname_chain_suffix")}</span>
                </h3>
                <div className="font-mono text-sm text-[var(--color-text)] space-y-0.5">
                  {allRecs.map((r: DnsRecord, i: number) => {
                    const showOwner = r.owner && r.owner !== hop;
                    return (
                      <div key={i} className="flex flex-wrap gap-x-4">
                        {showOwner && <span className="text-orange-600 dark:text-orange-400">{r.owner}.</span>}
                        <span className="text-primary-600 dark:text-primary-400">{r.type}</span>
                        <span>{r.value}</span>
                        <span className="text-[var(--color-text-secondary)]">TTL: {r.ttl}</span>
                      </div>
                    );
                  })}
                </div>
              </div>
              );
            })}

            {/* Authority section */}
            {dnsResult.authority && Object.keys(dnsResult.authority).length > 0 && (
              <div className="card p-3 border-l-2 border-warning-500">
                <h3 className="text-xs font-semibold text-warning-600 dark:text-warning-500 uppercase mb-2">{t("tools.dns.authority_section")}</h3>
                <div className="font-mono text-sm text-[var(--color-text)] space-y-0.5">
                  {Object.entries(dnsResult.authority).flatMap(([type, records]) =>
                    (records as DnsRecord[]).map((r: DnsRecord, i: number) => (
                      <div key={`${type}-${i}`} className="flex flex-wrap gap-x-4">
                        <span className="text-warning-600 dark:text-warning-500">{r.type}</span>
                        <span>{r.value}</span>
                        <span className="text-[var(--color-text-secondary)]">TTL: {r.ttl}</span>
                      </div>
                    ))
                  )}
                </div>
              </div>
            )}

            {/* Additional section */}
            {dnsResult.additional && Object.keys(dnsResult.additional).length > 0 && (
              <div className="card p-3 border-l-2 border-info-500">
                <h3 className="text-xs font-semibold text-info-600 dark:text-info-500 uppercase mb-2">{t("tools.dns.additional_section")}</h3>
                <div className="font-mono text-sm text-[var(--color-text)] space-y-0.5">
                  {Object.entries(dnsResult.additional).flatMap(([type, records]) =>
                    (records as DnsRecord[]).map((r: DnsRecord, i: number) => (
                      <div key={`${type}-${i}`} className="flex flex-wrap gap-x-4">
                        <span className="text-info-600 dark:text-info-500">{r.type}</span>
                        <span>{r.value}</span>
                        <span className="text-[var(--color-text-secondary)]">TTL: {r.ttl}</span>
                      </div>
                    ))
                  )}
                </div>
              </div>
            )}
          </div>
        )}
      </ToolOutput>
    </PageLayout>
  );
}

import { useState, useCallback, useEffect } from "react";
import PageLayout from "@/components/layout/PageLayout";
import ToolForm from "@/components/tool/ToolForm";
import ToolOutput from "@/components/tool/ToolOutput";
import { useToolExecution } from "@/hooks/useToolExecution";
import { useToolStore } from "@/stores/toolStore";
import { TextInput, Select, Checkbox } from "@/components/ui";
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

export default function DnsLookupPage() {
  const [form, setForm] = useState<DnsFormData>({ ...defaults });
  const [errors, setErrors] = useState<Partial<Record<keyof DnsFormData, string>>>({});
  const { status, data, error, duration, execute, reset } = useToolExecution();
  const [dnsServers, setDnsServers] = useState<DnsServerOption[]>([
    { value: "__system__", label: "System Default" },
  ]);

  useEffect(() => {
    useToolStore.getState().setActiveTool("dns_lookup");
  }, []);

  useEffect(() => {
    api<{ servers?: DnsServerOption[] }>("/tools/dns_lookup/dns-servers")
      .then((res) => {
        if (res.servers?.length) setDnsServers([{ value: "__system__", label: "System Default" }, ...res.servers]);
      })
      .catch(() => {});
  }, []);

  const validate = (): boolean => {
    const errs: typeof errors = {};
    if (!form.domain.trim()) errs.domain = "Domain is required.";
    if (form.record_types.length === 0) errs.record_types = "Select at least one record type.";
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
      return <p className="text-xs text-error-600 dark:text-error-500 font-mono">No records found</p>;
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
        title="DNS Lookup"
        advancedOpen={false}
        isRunning={isRunning}
        onStart={handleStart}
        onReset={handleReset}
        startLabel="Lookup"
        outputControls={
          <span className="text-xs text-[var(--color-text-secondary)]">
            {duration !== null ? `${(duration / 1000).toFixed(1)}s` : ""}
          </span>
        }
      >
        <label className="flex flex-col gap-1">
          <span className="text-xs font-medium text-[var(--color-text-secondary)]">Domain</span>
          <TextInput type="text" placeholder="example.com" value={form.domain} onChange={(e) => update("domain", e.target.value)} error={errors.domain} onKeyDown={(e) => { if (e.key === "Enter") handleStart(); }} />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-xs font-medium text-[var(--color-text-secondary)]">DNS Server</span>
          <Select
            options={dnsServers}
            value={form.resolver}
            onChange={(v) => update("resolver", v)}
            placeholder="System Default"
          />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-xs font-medium text-[var(--color-text-secondary)]">Recursive CNAME</span>
          <Checkbox checked={form.recursive_cname} onChange={(v) => update("recursive_cname", v === true)} label="Follow CNAME chain" />
        </label>
        <div className="sm:col-span-2 lg:col-span-4">
          <span className="text-xs font-medium text-[var(--color-text-secondary)]">Record Types</span>
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
            {dnsResult.cname_chain && (
              <div className="card p-3">
                <h3 className="text-xs font-semibold text-[var(--color-text-secondary)] uppercase mb-2">CNAME Chain (Recursive)</h3>
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
                    <h4 className="text-[11px] font-semibold text-[var(--color-text-secondary)] uppercase mb-1">{type} Records</h4>
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
                  {hop} <span className="text-[var(--color-text-secondary)] font-normal normal-case">(CNAME chain)</span>
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
          </div>
        )}
      </ToolOutput>
    </PageLayout>
  );
}

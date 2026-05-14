import { useState, useCallback, useEffect } from "react";
import PageLayout from "@/components/layout/PageLayout";
import ToolForm from "@/components/tool/ToolForm";
import ToolOutput from "@/components/tool/ToolOutput";
import { useMockToolExecution } from "@/hooks/useMockToolExecution";
import { useToolStore } from "@/stores/toolStore";
import { TextInput, Select, Checkbox } from "@/components/ui";
import type { DnsResult, DnsRecord } from "@/types/tool";

interface DnsFormData {
  domain: string;
  record_types: string[];
  resolver: string;
  recursive_cname: boolean;
}

const defaults: DnsFormData = {
  domain: "example.com",
  record_types: ["A", "AAAA", "MX", "NS", "TXT", "SOA"],
  resolver: "__system__",
  recursive_cname: true,
};

const RECORD_TYPES = ["A", "AAAA", "CNAME", "MX", "NS", "TXT", "SRV", "SOA", "PTR", "CAA"];

const DNS_SERVERS = [
  { value: "__system__", label: "System Default" },
  { value: "8.8.8.8", label: "Google (8.8.8.8)" },
  { value: "1.1.1.1", label: "Cloudflare (1.1.1.1)" },
  { value: "9.9.9.9", label: "Quad9 (9.9.9.9)" },
];

export default function DnsLookupPage() {
  const [form, setForm] = useState<DnsFormData>({ ...defaults });
  const [errors, setErrors] = useState<Partial<Record<keyof DnsFormData, string>>>({});
  const [dnsResult, setDnsResult] = useState<DnsResult | null>(null);
  const { status, error, duration, execute, reset } = useMockToolExecution();

  useEffect(() => {
    useToolStore.getState().setActiveTool("dns_lookup");
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
    const result = await execute("dns_lookup", { ...form, target: form.domain });
    setDnsResult(result.data as DnsResult);
  }, [form, execute]);

  const handleReset = useCallback(() => {
    setForm({ ...defaults });
    setErrors({});
    setDnsResult(null);
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

  const copyResults = () => {
    if (!dnsResult) return;
    const lines: string[] = [];
    for (const [type, records] of Object.entries(dnsResult.records)) {
      lines.push(`;; ${type} Records`);
      records.forEach((r: DnsRecord) => lines.push(`${r.value}  TTL: ${r.ttl}`));
      lines.push("");
    }
    if (dnsResult.cname_chain) {
      lines.push(";; CNAME Chain:");
      dnsResult.cname_chain.forEach((c) => lines.push(c));
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
          <TextInput type="text" placeholder="example.com" value={form.domain} onChange={(e) => update("domain", e.target.value)} error={errors.domain} />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-xs font-medium text-[var(--color-text-secondary)]">DNS Server</span>
          <Select
            options={DNS_SERVERS}
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
                  <span className="text-[var(--color-text-secondary)]"> (terminal)</span>
                </div>
              </div>
            )}

            {dnsResult.records && Object.entries(dnsResult.records).map(([type, records]) => (
              <div key={type} className="card p-3">
                <h3 className="text-xs font-semibold text-[var(--color-text-secondary)] uppercase mb-2">{type} Records</h3>
                {records.map((r: DnsRecord, i: number) => (
                  <div key={i} className="font-mono text-sm text-[var(--color-text)] flex flex-wrap gap-x-4">
                    <span className="text-primary-600 dark:text-primary-400">{r.type}</span>
                    <span>{r.value}</span>
                    <span className="text-[var(--color-text-secondary)]">TTL: {r.ttl}</span>
                  </div>
                ))}
              </div>
            ))}

            {Object.keys(dnsResult.records).length === 0 && (
              <p className="text-sm text-[var(--color-text-secondary)]">No records found.</p>
            )}
          </div>
        )}
      </ToolOutput>
    </PageLayout>
  );
}

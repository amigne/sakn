import { useState, useCallback, useEffect } from "react";
import PageLayout from "@/components/layout/PageLayout";
import ToolForm from "@/components/tool/ToolForm";
import ToolOutput from "@/components/tool/ToolOutput";
import { useToolExecution } from "@/hooks/useToolExecution";
import { useToolStore } from "@/stores/toolStore";
import { TextInput, Accordion, Badge, Alert } from "@/components/ui";
import type { SslResult, SslCertInfo } from "@/types/tool";

interface SslFormData {
  url: string;
  sni: string;
}

const defaults: SslFormData = {
  url: "example.com",
  sni: "",
};

export default function SslViewerPage() {
  const [form, setForm] = useState<SslFormData>({ ...defaults });
  const [errors, setErrors] = useState<Partial<Record<keyof SslFormData, string>>>({});
  const { status, data, error, duration, execute, reset } = useToolExecution();

  useEffect(() => {
    useToolStore.getState().setActiveTool("ssl_viewer");
  }, []);

  const validate = (): boolean => {
    const errs: typeof errors = {};
    if (!form.url.trim()) errs.url = "URL is required.";
    setErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const handleStart = useCallback(async () => {
    if (!validate()) return;
    await execute("ssl_viewer", { ...form, target: form.url });
  }, [form, execute]);

  const handleReset = useCallback(() => {
    setForm({ ...defaults });
    setErrors({});
    reset();
  }, [reset]);

  const update = (field: keyof SslFormData, value: string) => {
    setForm((f) => ({ ...f, [field]: value }));
    setErrors((e) => ({ ...e, [field]: undefined }));
  };

  const isRunning = status === "running";

  const sslResult = (data ?? null) as SslResult | null;

  const formatDate = (d: string) => {
    try { return new Date(d).toLocaleDateString(); } catch { return d; }
  };

  const copyResults = () => {
    if (!sslResult) return;
    const lines: string[] = [];
    lines.push(`URL: ${sslResult.url}`);
    lines.push(`TLS: ${sslResult.tls_version}`);
    lines.push(`Cipher: ${sslResult.cipher_suite}`);
    lines.push("");
    sslResult.certificates.forEach((cert, i) => {
      lines.push(`Certificate ${i + 1}:`);
      lines.push(`  Subject: ${cert.subject}`);
      lines.push(`  Issuer: ${cert.issuer}`);
      lines.push(`  Valid: ${cert.valid_from} - ${cert.valid_until}`);
      lines.push(`  SANs: ${cert.sans.join(", ")}`);
      lines.push("");
    });
    navigator.clipboard.writeText(lines.join("\n")).catch(() => {});
  };

  const certIssues = (cert: SslCertInfo): string[] => {
    const issues: string[] = [];
    if (cert.is_expired) issues.push("Expired");
    if (cert.is_self_signed) issues.push("Self-signed");
    if (cert.name_mismatch) issues.push("Name mismatch");
    if (cert.is_weak_key) issues.push("Weak key");
    return issues;
  };

  return (
    <PageLayout>
      <ToolForm
        title="TLS/SSL Certificate Viewer"
        advancedOpen={false}
        isRunning={isRunning}
        onStart={handleStart}
        onReset={handleReset}
        startLabel="Fetch Certificate"
        outputControls={
          <span className="text-xs text-[var(--color-text-secondary)]">
            {duration !== null ? `${(duration / 1000).toFixed(1)}s` : ""}
          </span>
        }
      >
        <label className="flex flex-col gap-1">
          <span className="text-xs font-medium text-[var(--color-text-secondary)]">URL</span>
          <TextInput type="text" placeholder="example.com" value={form.url} onChange={(e) => update("url", e.target.value)} error={errors.url} />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-xs font-medium text-[var(--color-text-secondary)]">SNI (optional)</span>
          <TextInput type="text" placeholder="Server Name Indication" value={form.sni} onChange={(e) => update("sni", e.target.value)} />
        </label>
      </ToolForm>

      <ToolOutput
        status={status}
        error={error}
        onCopy={sslResult ? copyResults : undefined}
      >
        {sslResult && status === "completed" && (
          <div className="space-y-3">
            <div className="card p-3 flex flex-wrap items-center gap-3">
              <div className="flex flex-wrap gap-2">
                <span className="text-xs font-semibold text-[var(--color-text-secondary)]">TLS Version:</span>
                <span className="font-mono text-sm text-[var(--color-text)]">{sslResult.tls_version}</span>
              </div>
              <div className="flex flex-wrap gap-2">
                <span className="text-xs font-semibold text-[var(--color-text-secondary)]">Cipher:</span>
                <span className="font-mono text-sm text-[var(--color-text)]">{sslResult.cipher_suite}</span>
              </div>
              <Badge variant={sslResult.chain_valid ? "success" : "error"}>
                {sslResult.chain_valid ? "Chain valid" : "Chain invalid"}
              </Badge>
            </div>

            {sslResult.warnings.length > 0 && (
              <div className="space-y-2">
                {sslResult.warnings.map((w, i) => <Alert key={i} variant="warning">{w}</Alert>)}
              </div>
            )}
            <Alert variant="info">Certificate revocation status was not checked.</Alert>

            <Accordion
              items={sslResult.certificates.map((cert, i) => {
                const issues = certIssues(cert);
                return {
                  value: `cert-${i}`,
                  trigger: (
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-mono text-xs">{cert.subject}</span>
                      {issues.map((iss) => <Badge key={iss} variant="error" className="text-[10px]">{iss}</Badge>)}
                      {issues.length === 0 && <Badge variant="success">Valid</Badge>}
                    </div>
                  ),
                  content: (
                    <div className="space-y-2">
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                        <div>
                          <span className="text-xs font-semibold text-[var(--color-text-secondary)]">Subject</span>
                          <p className="font-mono text-xs text-[var(--color-text)]">{cert.subject}</p>
                        </div>
                        <div>
                          <span className="text-xs font-semibold text-[var(--color-text-secondary)]">Issuer</span>
                          <p className="font-mono text-xs text-[var(--color-text)]">{cert.issuer}</p>
                        </div>
                        <div>
                          <span className="text-xs font-semibold text-[var(--color-text-secondary)]">Valid From</span>
                          <p className="font-mono text-xs text-[var(--color-text)]">{formatDate(cert.valid_from)}</p>
                        </div>
                        <div>
                          <span className="text-xs font-semibold text-[var(--color-text-secondary)]">Valid Until</span>
                          <p className="font-mono text-xs text-[var(--color-text)]">{formatDate(cert.valid_until)}</p>
                        </div>
                        <div>
                          <span className="text-xs font-semibold text-[var(--color-text-secondary)]">Key Algorithm</span>
                          <p className="font-mono text-xs text-[var(--color-text)]">{cert.key_algorithm} {cert.key_size} bits</p>
                        </div>
                        <div>
                          <span className="text-xs font-semibold text-[var(--color-text-secondary)]">Signature</span>
                          <p className="font-mono text-xs text-[var(--color-text)]">{cert.signature_algorithm}</p>
                        </div>
                      </div>
                      {cert.sans.length > 0 && (
                        <div>
                          <span className="text-xs font-semibold text-[var(--color-text-secondary)]">Subject Alternative Names</span>
                          <div className="flex flex-wrap gap-1 mt-1">
                            {cert.sans.map((san) => <Badge key={san} variant="neutral">{san}</Badge>)}
                          </div>
                        </div>
                      )}
                      {cert.extended_key_usage.length > 0 && (
                        <div>
                          <span className="text-xs font-semibold text-[var(--color-text-secondary)]">Extended Key Usage</span>
                          <div className="flex flex-wrap gap-1 mt-1">
                            {cert.extended_key_usage.map((eku) => <Badge key={eku} variant="neutral">{eku}</Badge>)}
                          </div>
                        </div>
                      )}
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                        <div>
                          <span className="text-xs font-semibold text-[var(--color-text-secondary)]">SHA-256 Fingerprint</span>
                          <p className="font-mono text-[10px] text-[var(--color-text)] break-all">{cert.fingerprint_sha256}</p>
                        </div>
                        <div>
                          <span className="text-xs font-semibold text-[var(--color-text-secondary)]">SHA-1 Fingerprint</span>
                          <p className="font-mono text-[10px] text-[var(--color-text)] break-all">{cert.fingerprint_sha1}</p>
                        </div>
                      </div>
                    </div>
                  ),
                };
              })}
              type="single"
            />
          </div>
        )}
      </ToolOutput>
    </PageLayout>
  );
}

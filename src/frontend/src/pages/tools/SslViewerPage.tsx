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
  url: "",
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
    if (cert.is_untrusted) issues.push("Untrusted");
    if (cert.is_trusted_root) issues.push("Trusted");
    if (cert.missing_issuer) issues.push("Missing issuer");
    if (cert.no_common_name) issues.push("No CN");
    if (cert.empty_subject) issues.push("Empty subject");
    if (cert.revocation_status === "revoked") issues.push("Revoked");
    if (cert.revocation_status === "unknown") issues.push("OCSP unknown");
    return issues;
  };

  const isWarning = (issue: string) => issue === "No CN" || issue === "Empty subject" || issue === "OCSP unknown";

  /** Red-text class for fields flagged by a certificate issue. */
  const errColor = "text-error-600 dark:text-error-500";
  const okColor = "text-[var(--color-text)]";

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
          <TextInput type="text" placeholder="example.com" value={form.url} onChange={(e) => update("url", e.target.value)} error={errors.url} onKeyDown={(e) => { if (e.key === "Enter") handleStart(); }} />
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
                {sslResult.warnings.map((w, i) => <Alert key={i} variant={w.variant}>{w.message}</Alert>)}
              </div>
            )}
            <Accordion
              items={sslResult.certificates.map((cert, i) => {
                const issues = certIssues(cert);
                return {
                  value: `cert-${i}`,
                  trigger: (
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-mono text-xs">{cert.subject}</span>
                      {issues.map((iss) => {
                        const variant = iss === "Trusted" ? "success" : isWarning(iss) ? "warning" : "error";
                        return <Badge key={iss} variant={variant} className="text-[10px]">{iss}</Badge>;
                      })}
                      {issues.length === 0 && <Badge variant="success" className="text-[10px]">Valid</Badge>}
                    </div>
                  ),
                  content: (
                    <div className="space-y-2">
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                        <div>
                          <span className="text-xs font-semibold text-[var(--color-text-secondary)]">Subject</span>
                          <p className={`font-mono text-xs ${cert.is_self_signed || cert.name_mismatch || cert.is_untrusted ? errColor : cert.is_trusted_root ? 'text-success-600 dark:text-success-500' : cert.no_common_name || cert.empty_subject ? 'text-warning-600 dark:text-warning-500' : okColor}`}>{cert.subject}</p>
                        </div>
                        <div>
                          <span className="text-xs font-semibold text-[var(--color-text-secondary)]">Issuer</span>
                          <p className={`font-mono text-xs ${cert.is_self_signed || cert.is_untrusted || cert.missing_issuer ? errColor : okColor}`}>
                            {cert.issuer}
                            {cert.missing_issuer && cert.missing_issuer_name && (
                              <span className="text-error-600 dark:text-error-500"> — root not found: {cert.missing_issuer_name}</span>
                            )}
                          </p>
                        </div>
                        <div>
                          <span className="text-xs font-semibold text-[var(--color-text-secondary)]">Valid From</span>
                          <p className={`font-mono text-xs ${cert.is_expired ? errColor : okColor}`}>{formatDate(cert.valid_from)}</p>
                        </div>
                        <div>
                          <span className="text-xs font-semibold text-[var(--color-text-secondary)]">Valid Until</span>
                          <p className={`font-mono text-xs ${cert.is_expired ? errColor : okColor}`}>{formatDate(cert.valid_until)}</p>
                        </div>
                        {cert.revocation_status && (
                        <div>
                          <span className="text-xs font-semibold text-[var(--color-text-secondary)]">Revocation</span>
                          <p className={`font-mono text-xs ${cert.revocation_status === "revoked" ? errColor : cert.revocation_status === "good" ? "text-success-600 dark:text-success-500" : "text-warning-600 dark:text-warning-500"}`}>
                            {cert.revocation_status === "good" && "Not revoked"}
                            {cert.revocation_status === "revoked" && cert.revocation_detail}
                            {cert.revocation_status === "unknown" && "Could not verify revocation status"}
                          </p>
                        </div>
                        )}
                        <div>
                          <span className="text-xs font-semibold text-[var(--color-text-secondary)]">Key Algorithm</span>
                          <p className={`font-mono text-xs ${cert.is_weak_key ? errColor : okColor}`}>{cert.key_algorithm} {cert.key_size} bits</p>
                        </div>
                        <div>
                          <span className="text-xs font-semibold text-[var(--color-text-secondary)]">Signature</span>
                          <p className="font-mono text-xs text-[var(--color-text)]">{cert.signature_algorithm}</p>
                        </div>
                      </div>
                      {cert.sans.length > 0 && (
                        <div>
                          <span className={`text-xs font-semibold ${cert.name_mismatch ? errColor : 'text-[var(--color-text-secondary)]'}`}>Subject Alternative Names</span>
                          <div className="flex flex-wrap gap-1 mt-1">
                            {cert.sans.map((san) => <Badge key={san} variant={cert.name_mismatch ? "error" : "neutral"}>{san}</Badge>)}
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
                      {/* ── Certificate Extensions ── */}
                      <div className="border-t border-[var(--color-border)] pt-2 mt-2">
                        <h4 className="text-xs font-semibold text-[var(--color-text-secondary)] uppercase mb-2">Extensions</h4>
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                          <div>
                            <span className="text-xs font-semibold text-[var(--color-text-secondary)]">Serial Number</span>
                            <p className="font-mono text-xs text-[var(--color-text)]">{cert.serial_number}</p>
                          </div>
                          <div>
                            <span className="text-xs font-semibold text-[var(--color-text-secondary)]">Basic Constraints</span>
                            <p className="font-mono text-xs text-[var(--color-text)]">
                              CA: {cert.is_ca ? "Yes" : "No"}{cert.bc_path_length != null ? `, pathlen:${cert.bc_path_length}` : ""}
                            </p>
                          </div>
                          {cert.ski && (
                          <div>
                            <span className="text-xs font-semibold text-[var(--color-text-secondary)]">Subject Key Identifier</span>
                            <p className="font-mono text-[10px] text-[var(--color-text)] break-all">{cert.ski}</p>
                          </div>
                          )}
                          {cert.aki && (
                          <div>
                            <span className="text-xs font-semibold text-[var(--color-text-secondary)]">Authority Key Identifier</span>
                            <p className="font-mono text-[10px] text-[var(--color-text)] break-all">{cert.aki}</p>
                          </div>
                          )}
                          {cert.key_usage.length > 0 && (
                          <div className="sm:col-span-2">
                            <span className="text-xs font-semibold text-[var(--color-text-secondary)]">Key Usage</span>
                            <div className="flex flex-wrap gap-1 mt-1">
                              {cert.key_usage.map((ku) => <Badge key={ku} variant="neutral" className="text-[10px]">{ku}</Badge>)}
                            </div>
                          </div>
                          )}
                          {cert.aia_entries.length > 0 && (
                          <div className="sm:col-span-2">
                            <span className="text-xs font-semibold text-[var(--color-text-secondary)]">Authority Info Access</span>
                            {cert.aia_entries.map((a, i) => (
                              <p key={i} className="font-mono text-[10px] text-[var(--color-text)] break-all">{a.method}: {a.url}</p>
                            ))}
                          </div>
                          )}
                          {cert.crl_urls.length > 0 && (
                          <div className="sm:col-span-2">
                            <span className="text-xs font-semibold text-[var(--color-text-secondary)]">CRL Distribution Points</span>
                            {cert.crl_urls.map((u, i) => (
                              <p key={i} className="font-mono text-[10px] text-[var(--color-text)] break-all">{u}</p>
                            ))}
                          </div>
                          )}
                          {cert.policy_oids.length > 0 && (
                          <div className="sm:col-span-2">
                            <span className="text-xs font-semibold text-[var(--color-text-secondary)]">Certificate Policies</span>
                            {cert.policy_oids.map((oid, i) => (
                              <p key={i} className="font-mono text-[10px] text-[var(--color-text)]">{oid}</p>
                            ))}
                          </div>
                          )}
                        </div>
                      </div>

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

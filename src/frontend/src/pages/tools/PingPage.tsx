import { useState, useCallback, useEffect } from "react";
import { useTranslation } from "react-i18next";
import PageLayout from "@/components/layout/PageLayout";
import ToolForm from "@/components/tool/ToolForm";
import ToolOutput from "@/components/tool/ToolOutput";
import { useWebSocket } from "@/hooks/useWebSocket";
import { useToolStore } from "@/stores/toolStore";
import { TextInput, ToggleSwitch, Badge, ProgressBar } from "@/components/ui";
import type { PingResult, PingSummary } from "@/types/tool";

interface PingFormData {
  target: string;
  count: number;
  timeout: number;
  packet_size: number;
  df_bit: boolean;
  dscp: number;
  max_duration: number;
}

const defaults: PingFormData = {
  target: "",
  count: 4,
  timeout: 10,
  packet_size: 56,
  df_bit: false,
  dscp: 0,
  max_duration: 30,
};

export default function PingPage() {
  const { t } = useTranslation();
  const displayMode = useToolStore((s) => s.displayMode.ping);
  const setDisplayMode = useToolStore((s) => s.setDisplayMode);

  const [form, setForm] = useState<PingFormData>({ ...defaults });
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [errors, setErrors] = useState<Partial<Record<keyof PingFormData, string>>>({});
  const [runCount, setRunCount] = useState(defaults.count);
  const { status, results, summary, terminatedBy, duration, error, connect, cancel, reset: resetOutput } = useWebSocket({ toolName: "ping" });

  const pingResults = results as PingResult[];
  const pingSummary = summary as PingSummary | null;

  useEffect(() => {
    useToolStore.getState().setActiveTool("ping");
  }, []);

  const validate = (): boolean => {
    const errs: typeof errors = {};
    if (!form.target.trim()) errs.target = t("tools.ping.target_required");
    if (form.count < 0 || form.count > 100) errs.count = "1-100";
    if (form.timeout < 1 || form.timeout > 60) errs.timeout = "1-60";
    if (form.packet_size < 8 || form.packet_size > 65507) errs.packet_size = "8-65507";
    if (form.dscp < 0 || form.dscp > 63) errs.dscp = "0-63";
    setErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const handleStart = useCallback(() => {
    if (!validate()) return;
    resetOutput();
    setRunCount(form.count);
    connect({ ...form });
  }, [form, connect, resetOutput]);

  const handleReset = useCallback(() => {
    setForm({ ...defaults });
    setErrors({});
    resetOutput();
  }, [resetOutput]);

  const update = (field: keyof PingFormData, value: string | number | boolean) => {
    setForm((f) => ({ ...f, [field]: value }));
    setErrors((e) => ({ ...e, [field]: undefined }));
  };

  const isRunning = status === "running";

  const copyResults = () => {
    let text: string;
    if (displayMode === "table") {
      const header = "| Seq | Status | RTT (ms) | TTL |";
      const sep = "|-----|--------|----------|-----|";
      const rows = pingResults.map((r) => {
        if (r.status === "timeout") return `| ${r.seq} | timeout | — | — |`;
        return `| ${r.seq} | ok | ${r.rtt_ms} | ${r.ttl} |`;
      });
      const summaryRows = pingSummary ? [
        "",
        `| Sent | Received | Lost | Loss % |`,
        `|------|----------|------|--------|`,
        `| ${pingSummary.transmitted} | ${pingSummary.received} | ${pingSummary.lost} | ${pingSummary.loss_pct}% |`,
      ] : [];
      text = [header, sep, ...rows, ...summaryRows].join("\n");
    } else {
      text = pingResults.map((r) => {
        if (r.status === "timeout") return `Request timeout for icmp_seq ${r.seq}`;
        return `Reply from ${form.target}: bytes=${r.bytes} time=${r.rtt_ms}ms TTL=${r.ttl}`;
      }).join("\n");
    }
    navigator.clipboard.writeText(text).catch(() => {});
  };

  return (
    <PageLayout>
      <ToolForm
        title={t("tools.ping.name")}
        advanced={
          <>
            <label className="flex flex-col gap-1">
              <span className="text-xs font-medium text-[var(--color-text-secondary)]">{t("tools.ping.df_bit_label")}</span>
              <ToggleSwitch checked={form.df_bit} onChange={(v) => update("df_bit", v)} />
            </label>
            <label className="flex flex-col gap-1">
              <span className="text-xs font-medium text-[var(--color-text-secondary)]">{t("tools.ping.dscp_label")} (0-63)</span>
              <TextInput type="number" min={0} max={63} value={form.dscp} onChange={(e) => update("dscp", Number(e.target.value))} error={errors.dscp} />
            </label>
            <label className="flex flex-col gap-1">
              <span className="text-xs font-medium text-[var(--color-text-secondary)]">{t("tools.ping.max_duration_label")}</span>
              <TextInput type="number" min={1} max={300} value={form.max_duration} onChange={(e) => update("max_duration", Number(e.target.value))} />
            </label>
          </>
        }
        advancedOpen={advancedOpen}
        onToggleAdvanced={() => setAdvancedOpen(!advancedOpen)}
        isRunning={isRunning}
        onStart={handleStart}
        onReset={handleReset}
        onStop={cancel}
        startLabel={(form.count ?? 0) > 0 ? t("tools.ping.execute_n_pings", { count: form.count }) : t("tools.ping.execute_label")}
        outputControls={
          <div className="flex items-center gap-2 text-sm">
            <button
              onClick={() => setDisplayMode("ping", "table")}
              className={`px-2 py-1 rounded text-xs ${displayMode === "table" ? "bg-primary-100 dark:bg-primary-900/30 text-primary-700 dark:text-primary-400" : "text-[var(--color-text-secondary)]"}`}
            >{t("common.table")}</button>
            <button
              onClick={() => setDisplayMode("ping", "text")}
              className={`px-2 py-1 rounded text-xs ${displayMode === "text" ? "bg-primary-100 dark:bg-primary-900/30 text-primary-700 dark:text-primary-400" : "text-[var(--color-text-secondary)]"}`}
            >{t("common.text")}</button>
          </div>
        }
      >
        <label className="flex flex-col gap-1">
          <span className="text-xs font-medium text-[var(--color-text-secondary)]">{t("tools.ping.target_label")}</span>
          <TextInput type="text" placeholder="8.8.8.8" value={form.target} onChange={(e) => update("target", e.target.value)} error={errors.target} onKeyDown={(e) => { if (e.key === "Enter") handleStart(); }} />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-xs font-medium text-[var(--color-text-secondary)]">{t("tools.ping.count_label")} (0 = unlimited)</span>
          <TextInput type="number" min={0} max={100} value={form.count} onChange={(e) => update("count", Number(e.target.value))} error={errors.count} />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-xs font-medium text-[var(--color-text-secondary)]">{t("tools.ping.timeout_label")}</span>
          <TextInput type="number" min={1} max={60} value={form.timeout} onChange={(e) => update("timeout", Number(e.target.value))} error={errors.timeout} />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-xs font-medium text-[var(--color-text-secondary)]">{t("tools.ping.packet_size_label")}</span>
          <TextInput type="number" min={8} max={65507} value={form.packet_size} onChange={(e) => update("packet_size", Number(e.target.value))} error={errors.packet_size} />
        </label>
      </ToolForm>

      <ToolOutput
        status={status}
        error={error}
        onCopy={pingResults.length > 0 ? copyResults : undefined}
        viewToggle={undefined}
      >
        {status !== "idle" && (
          <>
            {isRunning && <ProgressBar value={pingResults.length} max={runCount || pingResults.length + 5} className="mb-3" />}
            {displayMode === "table" ? (
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-[var(--color-border)]">
                    <th scope="col" className="px-3 py-1 text-start text-xs font-semibold text-[var(--color-text-secondary)] uppercase">{t("tools.ping.table_header_seq")}</th>
                    <th scope="col" className="px-3 py-1 text-start text-xs font-semibold text-[var(--color-text-secondary)] uppercase">{t("tools.ping.table_header_status")}</th>
                    <th scope="col" className="px-3 py-1 text-start text-xs font-semibold text-[var(--color-text-secondary)] uppercase">{t("tools.ping.table_header_rtt")}</th>
                    <th scope="col" className="px-3 py-1 text-start text-xs font-semibold text-[var(--color-text-secondary)] uppercase">{t("tools.ping.table_header_ttl")}</th>
                  </tr>
                </thead>
                <tbody>
                  {pingResults.map((r) => (
                    <tr key={r.seq} className="border-b border-[var(--color-border)]">
                      <td className="px-3 py-1 text-[var(--color-text)]">{r.seq}</td>
                      <td className="px-3 py-1">
                        <Badge variant={r.status === "ok" ? "success" : r.status === "timeout" ? "warning" : "error"}>
                          {r.status}
                        </Badge>
                      </td>
                      <td className="px-3 py-1 font-mono text-[var(--color-text)]">{r.rtt_ms ?? "-"}</td>
                      <td className="px-3 py-1 font-mono text-[var(--color-text)]">{r.ttl ?? "-"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <pre className="font-mono text-sm text-[var(--color-text)] whitespace-pre-wrap">
                {pingResults.map((r) => {
                  if (r.status === "timeout") return `Request timeout for icmp_seq ${r.seq}`;
                  return `Reply from ${form.target}: bytes=${r.bytes} time=${r.rtt_ms}ms TTL=${r.ttl}`;
                }).join("\n")}
              </pre>
            )}

            {(status === "completed" || status === "stopped") && (
              <>
                <hr className="my-3 border-[var(--color-border)]" />
                <div className="text-sm">
                  <h3 className="font-semibold text-[var(--color-text)] mb-2">{t("common.summary")}</h3>
                  {terminatedBy === "user" && (
                    <p className="text-sm text-warning-600 dark:text-warning-500 mb-2">{t("common.execution_stopped_by_user")}</p>
                  )}
                  {pingSummary && (
                    <>
                      {displayMode === "table" ? (
                        <>
                          <h4 className="text-xs font-semibold text-[var(--color-text-secondary)] uppercase mb-1">{t("tools.ping.section_packets")}</h4>
                          <table className="w-full max-w-xs mb-3 text-sm">
                            <thead>
                              <tr className="border-b border-[var(--color-border)]">
                                <th className="px-3 py-1 text-start text-xs font-semibold text-[var(--color-text-secondary)] uppercase">{t("tools.ping.table_header_sent")}</th>
                                <th className="px-3 py-1 text-start text-xs font-semibold text-[var(--color-text-secondary)] uppercase">{t("tools.ping.table_header_received")}</th>
                                <th className="px-3 py-1 text-start text-xs font-semibold text-[var(--color-text-secondary)] uppercase">{t("tools.ping.table_header_lost")}</th>
                              </tr>
                            </thead>
                            <tbody>
                              <tr>
                                <td className="px-3 py-1 font-mono text-[var(--color-text)]">{pingSummary.transmitted}</td>
                                <td className="px-3 py-1 font-mono text-[var(--color-text)]">{pingSummary.received}</td>
                                <td className="px-3 py-1 font-mono text-[var(--color-text)]">{pingSummary.lost}</td>
                              </tr>
                              <tr>
                                <td className="px-3 py-1 font-mono text-[var(--color-text-secondary)]">100%</td>
                                <td className="px-3 py-1 font-mono text-[var(--color-text-secondary)]">{(100 - pingSummary.loss_pct).toFixed(1)}%</td>
                                <td className="px-3 py-1 font-mono text-[var(--color-text-secondary)]">{pingSummary.loss_pct}%</td>
                              </tr>
                            </tbody>
                          </table>
                        </>
                      ) : (
                        <pre className="font-mono text-sm text-[var(--color-text)] mb-3">
                          {`Packets: sent = ${pingSummary.transmitted}, received = ${pingSummary.received} (${(100 - pingSummary.loss_pct).toFixed(1)}%), lost = ${pingSummary.lost} (${pingSummary.loss_pct}%)`}
                        </pre>
                      )}

                      {pingSummary.rtt_min_ms !== null ? (
                        displayMode === "table" ? (
                          <>
                            <h4 className="text-xs font-semibold text-[var(--color-text-secondary)] uppercase mb-1 mt-3">{t("tools.ping.section_rtt")}</h4>
                            <table className="w-full max-w-xs text-sm">
                              <thead>
                                <tr className="border-b border-[var(--color-border)]">
                                  <th className="px-3 py-1 text-start text-xs font-semibold text-[var(--color-text-secondary)] uppercase">{t("tools.ping.table_header_min")}</th>
                                  <th className="px-3 py-1 text-start text-xs font-semibold text-[var(--color-text-secondary)] uppercase">{t("tools.ping.table_header_avg")}</th>
                                  <th className="px-3 py-1 text-start text-xs font-semibold text-[var(--color-text-secondary)] uppercase">{t("tools.ping.table_header_max")}</th>
                                  <th className="px-3 py-1 text-start text-xs font-semibold text-[var(--color-text-secondary)] uppercase">{t("tools.ping.table_header_stddev")}</th>
                                </tr>
                              </thead>
                              <tbody>
                                <tr>
                                  <td className="px-3 py-1 font-mono text-[var(--color-text)]">{pingSummary.rtt_min_ms} ms</td>
                                  <td className="px-3 py-1 font-mono text-[var(--color-text)]">{pingSummary.rtt_avg_ms} ms</td>
                                  <td className="px-3 py-1 font-mono text-[var(--color-text)]">{pingSummary.rtt_max_ms} ms</td>
                                  <td className="px-3 py-1 font-mono text-[var(--color-text)]">{pingSummary.rtt_mdev_ms} ms</td>
                                </tr>
                              </tbody>
                            </table>
                          </>
                        ) : (
                          <pre className="font-mono text-sm text-[var(--color-text)]">
                            {`Approximate round trip times in milliseconds:
	    Min=${pingSummary.rtt_min_ms}ms, Avg=${pingSummary.rtt_avg_ms}ms, Max=${pingSummary.rtt_max_ms}ms, StdDev=${pingSummary.rtt_mdev_ms}ms`}
                          </pre>
                        )
                      ) : (
                        <p className="text-sm text-[var(--color-text-secondary)]">{t("tools.ping.no_rtt_stats")}</p>
                      )}
                    </>
                  )}
                  {duration && <p className="text-xs text-[var(--color-text-secondary)] mt-2">{t("common.duration")}: {(duration / 1000).toFixed(1)}s</p>}
                </div>
              </>
            )}
          </>
        )}
      </ToolOutput>
    </PageLayout>
  );
}

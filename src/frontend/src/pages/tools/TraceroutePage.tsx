import { useState, useCallback, useEffect } from "react";
import PageLayout from "@/components/layout/PageLayout";
import ToolForm from "@/components/tool/ToolForm";
import ToolOutput from "@/components/tool/ToolOutput";
import { useWebSocket } from "@/hooks/useWebSocket";
import { useToolStore } from "@/stores/toolStore";
import { TextInput, Select, ToggleSwitch, Badge, ProgressBar } from "@/components/ui";
import type { TracerouteHop } from "@/types/tool";

interface TracerouteFormData {
  target: string;
  protocol: "udp" | "icmp" | "tcp";
  port: number;
  probes_per_hop: number;
  timeout: number;
  max_distance: number;
  dns_resolution: boolean;
}

interface TracerouteSummary {
  hops_probed: number;
  destination_reached: boolean;
  total_time_ms: number;
}

const defaults: TracerouteFormData = {
  target: "",
  protocol: "udp",
  port: 33434,
  probes_per_hop: 3,
  timeout: 1,
  max_distance: 30,
  dns_resolution: true,
};

export default function TraceroutePage() {
  const displayMode = useToolStore((s) => s.displayMode.traceroute);
  const setDisplayMode = useToolStore((s) => s.setDisplayMode);

  const [form, setForm] = useState<TracerouteFormData>({ ...defaults });
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [errors, setErrors] = useState<Partial<Record<keyof TracerouteFormData, string>>>({});
  const [runConfig, setRunConfig] = useState<{ probes_per_hop: number; max_distance: number }>({ probes_per_hop: defaults.probes_per_hop, max_distance: defaults.max_distance });
  const { status, results, summary, terminatedBy, duration, error, connect, cancel, reset: resetOutput } = useWebSocket<TracerouteHop, TracerouteSummary>({ toolName: "traceroute" });

  const hops = results as TracerouteHop[];
  const tracerouteSummary = summary as TracerouteSummary | null;

  useEffect(() => {
    useToolStore.getState().setActiveTool("traceroute");
  }, []);

  const validate = (): boolean => {
    const errs: typeof errors = {};
    if (!form.target.trim()) errs.target = "Target is required.";
    if (form.port < 1 || form.port > 65535) errs.port = "1-65535";
    if (form.timeout < 1 || form.timeout > 30) errs.timeout = "1-30";
    if (form.max_distance < 1 || form.max_distance > 64) errs.max_distance = "1-64";
    if (form.probes_per_hop < 1 || form.probes_per_hop > 10) errs.probes_per_hop = "1-10";
    setErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const handleStart = useCallback(() => {
    if (!validate()) return;
    resetOutput();
    setRunConfig({ probes_per_hop: form.probes_per_hop, max_distance: form.max_distance });
    connect({ ...form });
  }, [form, connect, resetOutput]);

  const handleReset = useCallback(() => {
    setForm({ ...defaults });
    setErrors({});
    resetOutput();
  }, [resetOutput]);

  const update = (field: keyof TracerouteFormData, value: string | number | boolean) => {
    setForm((f) => ({ ...f, [field]: value }));
    setErrors((e) => ({ ...e, [field]: undefined }));
  };

  const isRunning = status === "running";
  const isIdle = status === "idle";

  const copyResults = () => {
    let text: string;
    if (displayMode === "table") {
      const headers = ["Hop", "IP", "Hostname", ...Array(runConfig.probes_per_hop).fill(null).map((_, i) => `Probe ${i + 1}`)];
      const sep = headers.map(() => "---");
      const rows = hops.map((h, idx) => {
        const hop = String(idx + 1);
        if (h.multipath && h.paths) {
          return h.paths.map((p, pi) => {
            const cells = [
              pi === 0 ? hop : "",
              p.ip ?? "*",
              p.hostname || "",
              ...p.probes.map((pr) => pr.rtt_ms ? `${pr.rtt_ms}ms` : "*"),
            ];
            return `| ${cells.join(" | ")} |`;
          }).join("\n");
        }
        const cells = [
          hop,
          h.ip ?? "*",
          h.hostname || "",
          ...h.probes.map((pr) => pr.rtt_ms ? `${pr.rtt_ms}ms` : "*"),
        ];
        return `| ${cells.join(" | ")} |`;
      });
      text = [
        `| ${headers.join(" | ")} |`,
        `| ${sep.join(" | ")} |`,
        ...rows,
        "",
        summary ? `**${tracerouteSummary?.destination_reached ? "Destination reached" : "Destination not reached"}** — ${tracerouteSummary?.hops_probed} hops, ${duration ? (duration / 1000).toFixed(1) + "s" : ""}` : "",
      ].join("\n");
    } else {
      text = hops.map((h, idx) => {
        if (h.multipath && h.paths) {
          return h.paths.map((p) => {
            const probeStr = p.probes.map((pr) => pr.rtt_ms ? `${pr.rtt_ms}ms` : "*").join("  ");
            return `${idx + 1}  ${p.ip ?? "*"}${p.hostname ? ` (${p.hostname})` : ""}  ${probeStr}`;
          }).join("\n");
        }
        if (!h.ip) return `${idx + 1}  * * *`;
        const probeStr = h.probes.map((p) => p.rtt_ms ? `${p.rtt_ms}ms` : "*").join("  ");
        const label = h.ip === "[hidden]" ? "[hidden]" : `${h.ip}${h.hostname ? ` (${h.hostname})` : ""}`;
        return `${idx + 1}  ${label}  ${probeStr}${h.reached ? "  <- Destination" : ""}`;
      }).join("\n");
    }
    navigator.clipboard.writeText(text).catch(() => {});
  };

  return (
    <PageLayout>
      <ToolForm
        title="Traceroute"
        advanced={
          <>
            <label className={`flex flex-col gap-1 ${form.protocol === "icmp" ? "opacity-50" : ""}`}>
              <span className="text-xs font-medium text-[var(--color-text-secondary)]">
                Port {form.protocol === "icmp" && <span className="font-normal">(unused for ICMP)</span>}
              </span>
              <TextInput type="number" min={1} max={65535} value={form.port} onChange={(e) => update("port", Number(e.target.value))} error={errors.port} disabled={form.protocol === "icmp"} />
            </label>
          </>
        }
        advancedOpen={advancedOpen}
        onToggleAdvanced={() => setAdvancedOpen(!advancedOpen)}
        isRunning={isRunning}
        onStart={handleStart}
        onReset={handleReset}
        onStop={cancel}
        startLabel="Trace"
        outputControls={
          <div className="flex items-center gap-2 text-sm">
            <button
              onClick={() => setDisplayMode("traceroute", "table")}
              className={`px-2 py-1 rounded text-xs ${displayMode === "table" ? "bg-primary-100 dark:bg-primary-900/30 text-primary-700 dark:text-primary-400" : "text-[var(--color-text-secondary)]"}`}
            >Table</button>
            <button
              onClick={() => setDisplayMode("traceroute", "text")}
              className={`px-2 py-1 rounded text-xs ${displayMode === "text" ? "bg-primary-100 dark:bg-primary-900/30 text-primary-700 dark:text-primary-400" : "text-[var(--color-text-secondary)]"}`}
            >Text</button>
          </div>
        }
      >
        <label className="flex flex-col gap-1">
          <span className="text-xs font-medium text-[var(--color-text-secondary)]">Target</span>
          <TextInput type="text" placeholder="8.8.8.8" value={form.target} onChange={(e) => update("target", e.target.value)} error={errors.target} onKeyDown={(e) => { if (e.key === "Enter") handleStart(); }} />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-xs font-medium text-[var(--color-text-secondary)]">Protocol</span>
          <Select
            options={[{ value: "udp", label: "UDP" }, { value: "icmp", label: "ICMP" }, { value: "tcp", label: "TCP" }]}
            value={form.protocol}
            onChange={(v) => update("protocol", v as "udp" | "icmp" | "tcp")}
          />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-xs font-medium text-[var(--color-text-secondary)]">Probes per Hop</span>
          <TextInput type="number" min={1} max={10} value={form.probes_per_hop} onChange={(e) => update("probes_per_hop", Number(e.target.value))} error={errors.probes_per_hop} />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-xs font-medium text-[var(--color-text-secondary)]">Timeout (s)</span>
          <TextInput type="number" min={1} max={30} value={form.timeout} onChange={(e) => update("timeout", Number(e.target.value))} error={errors.timeout} />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-xs font-medium text-[var(--color-text-secondary)]">Max Hops</span>
          <TextInput type="number" min={1} max={64} value={form.max_distance} onChange={(e) => update("max_distance", Number(e.target.value))} error={errors.max_distance} />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-xs font-medium text-[var(--color-text-secondary)]">DNS Resolution</span>
          <ToggleSwitch checked={form.dns_resolution} onChange={(v) => update("dns_resolution", v)} label="Resolve hostnames" />
        </label>
      </ToolForm>

      <ToolOutput
        status={status}
        error={error}
        onCopy={hops.length > 0 ? copyResults : undefined}
      >
        {!isIdle && hops.length > 0 && (
          <>
            {isRunning && <ProgressBar value={hops.length} max={runConfig.max_distance} className="mb-3" />}
            {displayMode === "table" ? (
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-[var(--color-border)]">
                    <th scope="col" className="px-3 py-1 text-start text-xs font-semibold text-[var(--color-text-secondary)] uppercase w-12">Hop</th>
                    <th scope="col" className="px-3 py-1 text-start text-xs font-semibold text-[var(--color-text-secondary)] uppercase">IP</th>
                    <th scope="col" className="px-3 py-1 text-start text-xs font-semibold text-[var(--color-text-secondary)] uppercase">Hostname</th>
                    {Array(runConfig.probes_per_hop).fill(null).map((_, i) => (
                      <th key={i} scope="col" className="px-3 py-1 text-start text-xs font-semibold text-[var(--color-text-secondary)] uppercase">Probe {i + 1}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {hops.map((h, idx) => {
                    if (h.multipath && h.paths) {
                      return h.paths.map((p, pi) => (
                        <tr key={`${idx}-${pi}`} className={`border-b border-[var(--color-border)] ${h.reached ? "bg-success-50 dark:bg-success-700/10" : ""}`}>
                          <td className="px-3 py-1 font-mono text-[var(--color-text)]">{pi === 0 ? idx + 1 : ""}</td>
                          <td className="px-3 py-1 font-mono text-[var(--color-text)]">{p.ip}</td>
                          <td className="px-3 py-1 text-[var(--color-text)]">
                            {p.hostname ?? ""}
                            {h.reached && pi === 0 && <Badge variant="success" className="ms-2">Destination</Badge>}
                          </td>
                          {p.probes.map((pr, pri) => (
                            <td key={pri} className="px-3 py-1 font-mono text-[var(--color-text)]">
                              {pr.status === "ok" ? `${pr.rtt_ms} ms` : <span className="text-[var(--color-text-secondary)]">*</span>}
                            </td>
                          ))}
                        </tr>
                      ));
                    }
                    return (
                      <tr key={idx} className={`border-b border-[var(--color-border)] ${h.reached ? "bg-success-50 dark:bg-success-700/10" : ""}`}>
                        <td className="px-3 py-1 font-mono text-[var(--color-text)]">{idx + 1}</td>
                        <td className="px-3 py-1 font-mono text-[var(--color-text)]">{h.ip ?? "*"}</td>
                        <td className="px-3 py-1 text-[var(--color-text)]">
                          {h.hostname ?? ((h.ip && h.ip !== '[hidden]') ? "*" : "")}
                          {h.reached && <Badge variant="success" className="ms-2">Destination</Badge>}
                        </td>
                        {h.probes.map((p, pi) => (
                          <td key={pi} className="px-3 py-1 font-mono text-[var(--color-text)]">
                            {p.status === "ok" ? `${p.rtt_ms} ms` : <span className="text-[var(--color-text-secondary)]">*</span>}
                          </td>
                        ))}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            ) : (
              <pre className="font-mono text-sm text-[var(--color-text)] whitespace-pre-wrap">
                {hops.map((h, idx) => {
                  if (h.multipath && h.paths) {
                    return h.paths.map((p) => {
                      const probeStr = p.probes.map((pr) => pr.rtt_ms ? `${pr.rtt_ms}ms` : "*").join("  ");
                      return `${idx + 1}  ${p.ip}${p.hostname ? ` (${p.hostname})` : ""}  ${probeStr}`;
                    }).join("\n");
                  }
                  const probeStr = h.probes.map((p) => p.rtt_ms ? `${p.rtt_ms}ms` : "*").join("  ");
                  const label = h.ip
                    ? `${h.ip}${h.hostname ? ` (${h.hostname})` : ""}`
                    : "*";
                  return `${idx + 1}  ${label}  ${probeStr}${h.reached ? "  <- Destination" : ""}`;
                }).join("\n")}
              </pre>
            )}

            {(status === "completed" || status === "stopped") && (
              <>
                <hr className="my-3 border-[var(--color-border)]" />
                <div className="text-sm">
                  <h3 className="font-semibold text-[var(--color-text)] mb-2">Summary</h3>
                  {terminatedBy === "user" && (
                    <p className="text-sm text-warning-600 dark:text-warning-500 mb-2">Execution stopped by user.</p>
                  )}
                  {tracerouteSummary && (
                    <div className="flex flex-wrap gap-x-8 gap-y-1 text-sm text-[var(--color-text)]">
                      <span>Hops probed: <strong>{tracerouteSummary.hops_probed}</strong></span>
                      <span>Destination: <Badge variant={tracerouteSummary.destination_reached ? "success" : "warning"}>{tracerouteSummary.destination_reached ? "Reached" : "Not reached"}</Badge></span>
                      {duration && <span>Duration: {(duration / 1000).toFixed(1)}s</span>}
                    </div>
                  )}
                </div>
              </>
            )}
          </>
        )}
      </ToolOutput>
    </PageLayout>
  );
}

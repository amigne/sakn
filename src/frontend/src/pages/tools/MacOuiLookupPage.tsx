import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import PageLayout from "@/components/layout/PageLayout";
import ToolForm from "@/components/tool/ToolForm";
import ToolOutput from "@/components/tool/ToolOutput";
import { Spinner } from "@/components/ui";
import { useToolExecution } from "@/hooks/useToolExecution";
import { useToolStore } from "@/stores/toolStore";
import { extractOuis } from "@/lib/macOuiExtractor";
import type { MacOuiExecuteResponse } from "@/api/tools/macOui";
import type { ExtractedOui } from "@/lib/macOuiExtractor";
import MacOuiRejectedBanner from "./components/MacOuiRejectedBanner";
import MacOuiParseStats from "./components/MacOuiParseStats";
import MacOuiResultsTable from "./components/MacOuiResultsTable";

const MAX_CHARS = 50_000;
const WARN_THRESHOLD = 0.9; // 90%

function localeFromI18n(lng: string): string {
  if (lng === "fr") return "fr-FR";
  return "en-US";
}

export default function MacOuiLookupPage() {
  const { t, i18n } = useTranslation();
  const [text, setText] = useState("");
  const { status, data, error, duration, execute, reset } = useToolExecution();
  const [extraction, setExtraction] = useState<{
    extracted: ExtractedOui[];
    matchesBeforeDedup: number;
    truncated: boolean;
  } | null>(null);
  const resultsRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    useToolStore.getState().setActiveTool("mac_oui");
  }, []);

  const isRunning = status === "running";
  const isCompleted = status === "completed";
  const hasText = text.trim().length > 0;

  const response = (data ?? null) as MacOuiExecuteResponse | null;

  const charCount = text.length;
  const isApproachingLimit = charCount >= MAX_CHARS * WARN_THRESHOLD;

  const handleTextChange = (value: string) => {
    // Enforce maxLength via JS as well (belt + suspenders).
    if (value.length > MAX_CHARS) {
      value = value.slice(0, MAX_CHARS);
    }
    setText(value);
    // Clear previous extraction/response when text changes.
    if (extraction) setExtraction(null);
    if (data) reset();
  };

  const handleStart = useCallback(async () => {
    if (!hasText || isRunning) return;

    // 1. Extract OUIs from text.
    const ext = extractOuis(text, { maxChars: MAX_CHARS });
    setExtraction({
      extracted: ext.unique,
      matchesBeforeDedup: ext.totalMatchesBeforeDedup,
      truncated: ext.truncated,
    });

    // 2. If nothing extracted, show empty result.
    if (ext.unique.length === 0) {
      return;
    }

    // 3. Send normalized list to backend.
    const ouis = ext.unique.map((e) => e.normalized);
    try {
      await execute("mac_oui", { ouis });
      // Focus results area after submit.
      setTimeout(() => {
        resultsRef.current?.focus();
      }, 100);
    } catch {
      // Error already handled by useToolExecution.
    }
  }, [text, hasText, isRunning, execute, reset, data]);

  const handleReset = useCallback(() => {
    setText("");
    setExtraction(null);
    reset();
  }, [reset]);

  // Show empty state when extraction found nothing.
  const showEmpty = extraction !== null && extraction.extracted.length === 0 && status === "idle";

  return (
    <PageLayout>
      <ToolForm
        title={t("tools.mac_oui.name")}
        isRunning={isRunning}
        onStart={handleStart}
        onReset={handleReset}
        startLabel={t("tools.mac_oui.execute_button")}
        outputControls={
          <span className="text-xs text-[var(--color-text-secondary)]">
            {duration !== null ? `${(duration / 1000).toFixed(1)}s` : ""}
          </span>
        }
      >
        <div className="sm:col-span-2 lg:col-span-4 flex flex-col gap-1">
          <label htmlFor="mac-oui-textarea" className="text-xs font-medium text-[var(--color-text-secondary)]">
            {t("tools.mac_oui.param_text_label")}
          </label>
          <textarea
            id="mac-oui-textarea"
            rows={8}
            maxLength={MAX_CHARS}
            className="focus-ring w-full rounded-md border bg-[var(--color-surface)] px-3 py-2 text-sm text-[var(--color-text)] placeholder:text-[var(--color-text-secondary)] border-[var(--color-border)] resize-y font-mono dark:[color-scheme:dark]"
            placeholder={t("tools.mac_oui.param_text_desc")}
            value={text}
            onChange={(e) => handleTextChange(e.target.value)}
            readOnly={isRunning}
            aria-label={t("tools.mac_oui.param_text_label")}
            aria-describedby="mac-oui-charcount"
          />
          <div id="mac-oui-charcount" className="flex items-center justify-between">
            <span
              className={`text-xs ${
                isApproachingLimit
                  ? "text-warning-600 dark:text-warning-500 font-medium"
                  : "text-[var(--color-text-secondary)]"
              }`}
              aria-live="polite"
            >
              {t("tools.mac_oui.input_chars_count", {
                current: charCount.toLocaleString(),
                max: MAX_CHARS.toLocaleString(),
              })}
              {isApproachingLimit && ` — ${t("tools.mac_oui.input_approaching_limit", { max: MAX_CHARS.toLocaleString() })}`}
            </span>
            {extraction?.truncated && (
              <span className="text-xs text-warning-600 dark:text-warning-500">
                {t("tools.mac_oui.input_truncation_warning", { max: MAX_CHARS.toLocaleString() })}
              </span>
            )}
          </div>
        </div>
      </ToolForm>

      <ToolOutput
        status={showEmpty ? "completed" : status}
        emptyMessage={t("tools.mac_oui.no_results")}
        error={error}
        onCopy={
          response?.results?.length
            ? () => {
                const header = ["OUI", "Vendor", "Type", "First seen", "Last seen", "Address"].join("\t");
                const lines = response.results.map((r) => {
                  const vendor = r.result?.organization ?? t("tools.mac_oui.unknown_vendor");
                  const type = r.result?.oui_type ?? "—";
                  const first = r.result?.first_seen ?? "—";
                  const last = r.result?.last_seen ?? "—";
                  const addr = r.result?.address ?? "—";
                  return [r.oui_display, vendor, type, first, last, addr].join("\t");
                });
                navigator.clipboard.writeText(`${header}\n${lines.join("\n")}`).catch(() => {});
              }
            : undefined
        }
      >
        {/* Submitting state */}
        {isRunning && (
          <div className="flex items-center gap-2 text-sm text-primary-600" aria-live="polite">
            <Spinner size="sm" />
            <span>
              {extraction
                ? t("tools.mac_oui.parse_stats", {
                    found: extraction.matchesBeforeDedup,
                    unique: extraction.extracted.length,
                  })
                : ""}
            </span>
          </div>
        )}

        {/* Success state */}
        {isCompleted && response && (
          <div ref={resultsRef} tabIndex={-1}>
            <MacOuiRejectedBanner rejected={response.rejected} />
            <MacOuiParseStats stats={response.parse_stats} />
            <MacOuiResultsTable
              results={response.results}
              locale={localeFromI18n(i18n.language)}
            />
          </div>
        )}

        {/* Empty state: extraction ran but found nothing */}
        {showEmpty && (
          <p className="py-8 text-center text-sm text-[var(--color-text-secondary)]">
            {t("tools.mac_oui.no_results")}
          </p>
        )}
      </ToolOutput>
    </PageLayout>
  );
}

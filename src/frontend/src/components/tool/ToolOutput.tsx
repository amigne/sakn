import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Spinner, Alert } from "@/components/ui";
import type { ExecutionStatus } from "@/types/tool";

interface ToolOutputProps {
  status: ExecutionStatus;
  emptyMessage?: string;
  error?: string | null;
  children: ReactNode;
  onCopy?: () => void;
  viewToggle?: ReactNode;
}

export default function ToolOutput({
  status,
  emptyMessage,
  error,
  children,
  onCopy,
  viewToggle,
}: ToolOutputProps) {
  const { t } = useTranslation();
  const defaultEmpty = t("common.enter_target_and_start");
  const displayEmpty = emptyMessage ?? defaultEmpty;

  return (
    <div className="card mt-4 p-4">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-sm font-semibold text-[var(--color-text)]">{t("common.output")}</h2>
        <div className="flex items-center gap-2">
          {viewToggle}
          {onCopy && status !== "idle" && (
            <button
              onClick={onCopy}
              className="focus-ring flex items-center gap-1 rounded px-2 py-1 text-xs text-[var(--color-text-secondary)] hover:text-[var(--color-text)]"
              aria-label="Copy results"
            >
              <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
              </svg>
              Copy
            </button>
          )}
        </div>
      </div>

      {error && (
        <Alert variant="error" className="mb-3">{error}</Alert>
      )}

      {status === "idle" && !error && (
        <p className="py-8 text-center text-sm text-[var(--color-text-secondary)]">{displayEmpty}</p>
      )}

      {status === "running" && (
        <div className="mb-3 flex items-center gap-2 text-sm text-primary-600">
          <Spinner size="sm" />
          <span aria-live="polite">Running...</span>
        </div>
      )}

      {(status === "running" || status === "completed" || status === "stopped") && (
        <div aria-live="polite" aria-atomic="false">
          {children}
        </div>
      )}
    </div>
  );
}

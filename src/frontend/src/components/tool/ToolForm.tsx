import type { ReactNode } from "react";
import { Button } from "@/components/ui";

interface ToolFormProps {
  title: string;
  children: ReactNode;
  advanced?: ReactNode;
  advancedOpen?: boolean;
  onToggleAdvanced?: () => void;
  isRunning: boolean;
  onStart: () => void;
  onReset: () => void;
  onStop?: () => void;
  startLabel?: string;
  outputControls?: ReactNode;
}

export default function ToolForm({
  title,
  children,
  advanced,
  advancedOpen = false,
  onToggleAdvanced,
  isRunning,
  onStart,
  onReset,
  onStop,
  startLabel = "Start",
  outputControls,
}: ToolFormProps) {
  return (
    <div className="card p-4">
      <h1 className="mb-3 text-lg font-semibold text-[var(--color-text)]">{title}</h1>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 mb-3">
        {children}
      </div>

      {advanced && (
        <>
          <button
            onClick={onToggleAdvanced}
            className="mb-2 flex items-center gap-1 text-xs font-medium text-[var(--color-text-secondary)] hover:text-[var(--color-text)]"
          >
            <svg className={`h-3 w-3 transition-transform ${advancedOpen ? "rotate-90" : ""}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
            </svg>
            Advanced
          </button>
          {advancedOpen && (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 mb-3 border-t border-[var(--color-border)] pt-3">
              {advanced}
            </div>
          )}
        </>
      )}

      <div className="flex flex-wrap items-center gap-2">
        {isRunning ? (
          onStop && <Button variant="danger" onClick={onStop}>Stop</Button>
        ) : (
          <Button onClick={onStart}>{startLabel}</Button>
        )}
        <Button variant="secondary" onClick={onReset} disabled={isRunning}>Reset</Button>
        {outputControls}
      </div>
    </div>
  );
}

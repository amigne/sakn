interface ProgressBarProps {
  value: number;
  max?: number;
  className?: string;
}

export default function ProgressBar({ value, max = 100, className = "" }: ProgressBarProps) {
  const pct = max > 0 ? Math.min(Math.round((value / max) * 100), 100) : 0;

  return (
    <div
      className={`h-2 w-full overflow-hidden rounded-full bg-[var(--color-border)] ${className}`}
      role="progressbar"
      aria-valuenow={value}
      aria-valuemin={0}
      aria-valuemax={max}
    >
      <div className="h-full rounded-full bg-primary-600 transition-all duration-300" style={{ width: `${pct}%` }} />
    </div>
  );
}

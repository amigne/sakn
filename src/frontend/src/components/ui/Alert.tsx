interface AlertProps {
  variant: "success" | "warning" | "error" | "info";
  title?: string;
  children: React.ReactNode;
  dismissible?: boolean;
  onDismiss?: () => void;
  className?: string;
}

const variantIcons: Record<string, string> = {
  success: "M5 13l4 4L19 7",
  warning: "M12 9v2m0 4h.01M12 3l9.66 16.5H2.34L12 3z",
  error: "M6 18L18 6M6 6l12 12",
  info: "M13 16h-1v-4h-1m1-4h.01M12 2a10 10 0 100 20 10 10 0 000-20z",
};

const variantClasses: Record<string, string> = {
  success: "border-success-500 bg-success-50 dark:bg-success-700/10 dark:border-success-600",
  warning: "border-warning-500 bg-warning-50 dark:bg-warning-700/10 dark:border-warning-600",
  error: "border-error-500 bg-error-50 dark:bg-error-700/10 dark:border-error-600",
  info: "border-info-500 bg-info-50 dark:bg-info-700/10 dark:border-info-600",
};

const iconClasses: Record<string, string> = {
  success: "text-success-600 dark:text-success-500",
  warning: "text-warning-600 dark:text-warning-500",
  error: "text-error-600 dark:text-error-500",
  info: "text-info-600 dark:text-info-500",
};

export default function Alert({ variant, title, children, dismissible, onDismiss, className = "" }: AlertProps) {
  return (
    <div className={`flex items-start gap-3 rounded-md border p-3 ${variantClasses[variant]} ${className}`} role="alert">
      <svg className={`h-5 w-5 mt-0.5 shrink-0 ${iconClasses[variant]}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d={variantIcons[variant]} />
      </svg>
      <div className="flex-1 min-w-0">
        {title && <p className="text-sm font-semibold text-[var(--color-text)]">{title}</p>}
        <div className="text-sm text-[var(--color-text-secondary)]">{children}</div>
      </div>
      {dismissible && (
        <button onClick={onDismiss} className="focus-ring shrink-0 rounded p-0.5 text-[var(--color-text-secondary)] hover:text-[var(--color-text)]" aria-label="Dismiss">
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      )}
    </div>
  );
}

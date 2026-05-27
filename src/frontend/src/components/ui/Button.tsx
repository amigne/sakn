import type { ButtonHTMLAttributes, ReactNode } from "react";

type ButtonVariant = "primary" | "secondary" | "danger" | "ghost";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  loading?: boolean;
  size?: "sm" | "md" | "lg";
  children: ReactNode;
}

const variantClasses: Record<ButtonVariant, string> = {
  primary:
    "bg-primary-600 text-white hover:bg-primary-700 active:bg-primary-800 disabled:bg-primary-300 dark:disabled:bg-primary-800",
  secondary:
    "border border-[var(--color-border)] bg-[var(--color-surface)] text-[var(--color-text)] hover:bg-[var(--color-surface-alt)] active:bg-gray-200 dark:active:bg-gray-700",
  danger:
    "bg-error-600 text-white hover:bg-error-700 active:bg-error-800 disabled:bg-error-300 dark:disabled:bg-error-800",
  ghost:
    "text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-alt)] active:bg-gray-200 dark:active:bg-gray-700",
};

const sizeClasses = {
  sm: "px-2.5 py-1 text-xs rounded",
  md: "px-4 py-2 text-sm rounded-md",
  lg: "px-6 py-3 text-base rounded-lg",
};

export default function Button({
  variant = "primary",
  loading = false,
  size = "md",
  children,
  disabled,
  className = "",
  ...props
}: ButtonProps) {
  return (
    <button
      className={`focus-ring inline-flex items-center justify-center gap-2 font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-60 ${variantClasses[variant]} ${sizeClasses[size]} ${className}`}
      disabled={disabled || loading}
      {...props}
    >
      {loading && (
        <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
        </svg>
      )}
      {children}
    </button>
  );
}

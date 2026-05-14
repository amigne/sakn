import { type InputHTMLAttributes, forwardRef, type ReactNode } from "react";

interface TextInputProps extends InputHTMLAttributes<HTMLInputElement> {
  error?: string;
  icon?: ReactNode;
  iconPosition?: "start" | "end";
}

const TextInput = forwardRef<HTMLInputElement, TextInputProps>(
  ({ error, icon, iconPosition = "start", className = "", ...props }, ref) => {
    return (
      <div className="flex flex-col gap-1">
        <div className="relative flex items-center">
          {icon && iconPosition === "start" && (
            <span className="pointer-events-none absolute start-3 text-[var(--color-text-secondary)]">{icon}</span>
          )}
          <input
            ref={ref}
            className={`focus-ring w-full rounded-md border bg-[var(--color-surface)] px-3 py-2 text-sm text-[var(--color-text)] placeholder:text-[var(--color-text-secondary)] disabled:cursor-not-allowed disabled:opacity-50 dark:[color-scheme:dark]
              ${icon && iconPosition === "start" ? "ps-10" : ""}
              ${icon && iconPosition === "end" ? "pe-10" : ""}
              ${error ? "border-error-500 focus:border-error-500" : "border-[var(--color-border)]"}
              ${className}`}
            aria-invalid={!!error}
            aria-describedby={error ? `${props.id}-error` : undefined}
            {...props}
          />
          {icon && iconPosition === "end" && (
            <span className="pointer-events-none absolute end-3 text-[var(--color-text-secondary)]">{icon}</span>
          )}
        </div>
        {error && (
          <p id={`${props.id}-error`} className="text-xs text-error-600 dark:text-error-500" role="alert">
            {error}
          </p>
        )}
      </div>
    );
  },
);

TextInput.displayName = "TextInput";

export default TextInput;

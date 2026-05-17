import * as RadixSelect from "@radix-ui/react-select";
import { forwardRef } from "react";
import i18n from "@/i18n/i18n";

interface SelectOption {
  value: string;
  label: string;
}

interface SelectProps {
  options: SelectOption[];
  value?: string;
  defaultValue?: string;
  onChange?: (value: string) => void;
  placeholder?: string;
  disabled?: boolean;
  error?: string;
  className?: string;
  ariaLabel?: string;
}

const Select = forwardRef<HTMLButtonElement, SelectProps>(
  ({ options, value, defaultValue, onChange, placeholder = i18n.t("common.select"), disabled, error, className = "", ariaLabel }, ref) => {
    return (
      <div className="flex flex-col gap-1">
        <RadixSelect.Root value={value} defaultValue={defaultValue} onValueChange={onChange} disabled={disabled}>
          <RadixSelect.Trigger
            ref={ref}
            className={`focus-ring flex w-full items-center justify-between rounded-md border bg-[var(--color-surface)] px-3 py-2 text-sm text-[var(--color-text)] disabled:cursor-not-allowed disabled:opacity-50 ${error ? "border-error-500" : "border-[var(--color-border)]"} ${className}`}
            aria-label={ariaLabel}
          >
            <RadixSelect.Value placeholder={placeholder} />
            <RadixSelect.Icon>
              <svg className="h-4 w-4 text-[var(--color-text-secondary)]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </RadixSelect.Icon>
          </RadixSelect.Trigger>
          <RadixSelect.Portal>
            <RadixSelect.Content
              className="z-50 max-h-60 overflow-auto rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] shadow-lg"
              position="popper"
              sideOffset={4}
            >
              <RadixSelect.Viewport>
                {options.map((opt) => (
                  <RadixSelect.Item
                    key={opt.value}
                    value={opt.value}
                    className="cursor-pointer px-3 py-2 text-sm text-[var(--color-text)] outline-none hover:bg-primary-50 dark:hover:bg-primary-900/20 radix-disabled:opacity-50 radix-highlighted:bg-primary-50 dark:radix-highlighted:bg-primary-900/20"
                  >
                    <RadixSelect.ItemText>{opt.label}</RadixSelect.ItemText>
                  </RadixSelect.Item>
                ))}
              </RadixSelect.Viewport>
            </RadixSelect.Content>
          </RadixSelect.Portal>
        </RadixSelect.Root>
        {error && (
          <p className="text-xs text-error-600 dark:text-error-500" role="alert">
            {error}
          </p>
        )}
      </div>
    );
  },
);

Select.displayName = "Select";

export default Select;

import * as RadixCheckbox from "@radix-ui/react-checkbox";

interface CheckboxProps {
  checked: boolean | "indeterminate";
  onChange: (checked: boolean | "indeterminate") => void;
  disabled?: boolean;
  label?: string;
}

export default function Checkbox({ checked, onChange, disabled, label }: CheckboxProps) {
  return (
    <label className="flex items-center gap-2 cursor-pointer">
      <RadixCheckbox.Root
        checked={checked}
        onCheckedChange={onChange}
        disabled={disabled}
        className={`focus-ring flex h-4 w-4 items-center justify-center rounded border border-[var(--color-border)] bg-[var(--color-surface)] radix-state-checked:bg-primary-600 radix-state-checked:border-primary-600 disabled:cursor-not-allowed disabled:opacity-50`}
      >
        <RadixCheckbox.Indicator>
          {checked === "indeterminate" ? (
            <svg className="h-3 w-3 text-white" fill="currentColor" viewBox="0 0 16 16">
              <rect x="3" y="7" width="10" height="2" />
            </svg>
          ) : (
            <svg className="h-3 w-3 text-white" fill="none" viewBox="0 0 16 16" stroke="currentColor" strokeWidth={3}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M3 8l3 3 7-7" />
            </svg>
          )}
        </RadixCheckbox.Indicator>
      </RadixCheckbox.Root>
      {label && <span className="text-sm text-[var(--color-text)]">{label}</span>}
    </label>
  );
}

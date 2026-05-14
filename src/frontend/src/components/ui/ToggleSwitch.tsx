import * as RadixSwitch from "@radix-ui/react-switch";

interface ToggleSwitchProps {
  checked: boolean;
  onChange: (checked: boolean) => void;
  disabled?: boolean;
  label?: string;
}

export default function ToggleSwitch({ checked, onChange, disabled, label }: ToggleSwitchProps) {
  return (
    <label className="flex items-center gap-2 cursor-pointer">
      <RadixSwitch.Root
        checked={checked}
        onCheckedChange={onChange}
        disabled={disabled}
        className={`focus-ring relative h-5 w-9 rounded-full border border-[var(--color-border)] bg-[var(--color-border)] transition-colors data-[state=checked]:bg-primary-600 disabled:cursor-not-allowed disabled:opacity-50`}
      >
        <RadixSwitch.Thumb className="block h-4 w-4 translate-x-0.5 rounded-full bg-white shadow transition-transform data-[state=checked]:translate-x-[18px]" />
      </RadixSwitch.Root>
      {label && <span className="text-sm text-[var(--color-text)]">{label}</span>}
    </label>
  );
}

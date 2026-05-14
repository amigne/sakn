interface RadioButtonProps {
  checked: boolean;
  onChange: () => void;
  disabled?: boolean;
  label?: string;
  name?: string;
}

export default function RadioButton({ checked, onChange, disabled, label, name }: RadioButtonProps) {
  return (
    <label className="flex items-center gap-2 cursor-pointer">
      <input
        type="radio"
        checked={checked}
        onChange={onChange}
        disabled={disabled}
        name={name}
        className="focus-ring h-4 w-4 border-[var(--color-border)] text-primary-600 accent-primary-600 disabled:cursor-not-allowed disabled:opacity-50"
      />
      {label && <span className="text-sm text-[var(--color-text)]">{label}</span>}
    </label>
  );
}

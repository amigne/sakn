interface PasswordStrengthProps {
  password: string;
}

interface CheckItem {
  label: string;
  passed: boolean;
}

export default function PasswordStrengthIndicator({ password }: PasswordStrengthProps) {
  const checks: CheckItem[] = [
    { label: "Min 8 characters", passed: password.length >= 8 },
    { label: "At least one uppercase letter", passed: /[A-Z]/.test(password) },
    { label: "At least one lowercase letter", passed: /[a-z]/.test(password) },
    { label: "At least one digit", passed: /[0-9]/.test(password) },
  ];

  const allPassed = checks.every((c) => c.passed) && password.length > 0;

  return (
    <div className="mt-2 space-y-1">
      <div className="h-1.5 rounded-full bg-[var(--color-border)] overflow-hidden">
        <div
          className={`h-full rounded-full transition-all ${allPassed ? "bg-success-500 w-full" : "bg-warning-500"}`}
          style={{ width: `${(checks.filter((c) => c.passed).length / checks.length) * 100}%` }}
        />
      </div>
      <ul className="text-xs space-y-0.5">
        {checks.map((check, i) => (
          <li key={i} className={`flex items-center gap-1 ${check.passed ? "text-success-600 dark:text-success-500" : "text-[var(--color-text-secondary)]"}`}>
            <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={check.passed ? 3 : 1.5}>
              {check.passed ? (
                <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
              ) : (
                <circle cx="12" cy="12" r="10" />
              )}
            </svg>
            {check.label}
          </li>
        ))}
      </ul>
    </div>
  );
}

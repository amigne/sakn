import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { TextInput, Button, Alert } from "@/components/ui";
import PasswordStrengthIndicator from "@/components/auth/PasswordStrengthIndicator";
import { useAuthStore } from "@/stores/authStore";
import { ApiError } from "@/services/api";

interface RegisterFormProps {
  className?: string;
}

export default function RegisterForm({ className = "" }: RegisterFormProps) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const register = useAuthStore((s) => s.register);
  const [email, setEmail] = useState("");
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [password, setPassword] = useState("");
  const [passwordConfirm, setPasswordConfirm] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setFieldErrors({});
    if (!email || !firstName || !lastName || !password || !passwordConfirm) {
      setError(t("errors.all_fields_required"));
      return;
    }
    if (password !== passwordConfirm) {
      setError(t("errors.password_mismatch"));
      return;
    }
    setLoading(true);
    try {
      await register(email, password, passwordConfirm, firstName, lastName);
      navigate("/verify-email-sent", { state: { email } });
    } catch (err) {
      if (err instanceof ApiError && err.fields) {
        const mapped: Record<string, string> = {};
        for (const [field, info] of Object.entries(err.fields)) {
          mapped[field] = info.message_key ? t(info.message_key) : info.message;
        }
        setFieldErrors(mapped);
      } else {
        setError(err instanceof ApiError ? err.message : t("errors.unexpected_error"));
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className={`w-full max-w-sm ${className}`}>
      <h1 className="mb-6 text-center text-xl font-semibold text-[var(--color-text)]">{t("auth.create_account")}</h1>

      {error && <Alert variant="error" className="mb-4">{error}</Alert>}

      <form onSubmit={handleSubmit} className="space-y-4">
        <label className="flex flex-col gap-1">
          <span className="text-sm font-medium text-[var(--color-text)]">{t("auth.email")}</span>
          <TextInput type="email" placeholder="user@example.com" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" error={fieldErrors.email} />
        </label>

        <div className="grid grid-cols-2 gap-3">
          <label className="flex flex-col gap-1">
            <span className="text-sm font-medium text-[var(--color-text)]">{t("auth.first_name")} *</span>
            <TextInput type="text" value={firstName} onChange={(e) => setFirstName(e.target.value)} autoComplete="given-name" required error={fieldErrors.first_name} />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-sm font-medium text-[var(--color-text)]">{t("auth.last_name")} *</span>
            <TextInput type="text" value={lastName} onChange={(e) => setLastName(e.target.value)} autoComplete="family-name" required error={fieldErrors.last_name} />
          </label>
        </div>

        <label className="flex flex-col gap-1">
          <span className="text-sm font-medium text-[var(--color-text)]">{t("auth.password")}</span>
          <div className="relative">
            <TextInput
              type={showPassword ? "text" : "password"}
              placeholder="••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="new-password"
              error={fieldErrors.password}
            />
            <button
              type="button"
              className="absolute end-2 top-1/2 -translate-y-1/2 text-[var(--color-text-secondary)] hover:text-[var(--color-text)]"
              onClick={() => setShowPassword(!showPassword)}
              aria-label={showPassword ? t("auth.hide_password") : t("auth.show_password")}
            >
              <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                {showPassword ? (
                  <>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19m-6.72-1.07a3 3 0 11-4.24-4.24" />
                    <line x1="1" y1="1" x2="23" y2="23" />
                  </>
                ) : (
                  <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0zM2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                )}
              </svg>
            </button>
          </div>
          <PasswordStrengthIndicator password={password} />
        </label>

        <label className="flex flex-col gap-1">
          <span className="text-sm font-medium text-[var(--color-text)]">{t("auth.confirm_password")}</span>
          <TextInput type="password" placeholder="••••••••" value={passwordConfirm} onChange={(e) => setPasswordConfirm(e.target.value)} autoComplete="new-password" error={fieldErrors.password_confirm} />
        </label>

        <Button type="submit" className="w-full" loading={loading}>{t("auth.create_account")}</Button>
      </form>
    </div>
  );
}

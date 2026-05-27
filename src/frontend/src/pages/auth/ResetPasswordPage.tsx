import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useSearchParams } from "react-router-dom";
import PasswordStrengthIndicator from "@/components/auth/PasswordStrengthIndicator";
import { Alert, Button, TextInput } from "@/components/ui";
import { ApiError } from "@/services/api";
import { useAuthStore } from "@/stores/authStore";

export default function ResetPasswordPage() {
  const { t } = useTranslation();
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token");
  const requestReset = useAuthStore((s) => s.requestPasswordReset);
  const resetPassword = useAuthStore((s) => s.resetPassword);

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [passwordConfirm, setPasswordConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [successMsg, setSuccessMsg] = useState("");
  const [loading, setLoading] = useState(false);

  const handleRequest = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.trim()) {
      setError(t("errors:email_required"));
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const msg = await requestReset(email);
      setSuccessMsg(msg);
      setSuccess(true);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError(t("errors:unexpected_error"));
      }
    } finally {
      setLoading(false);
    }
  };

  const handleReset = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!password || !passwordConfirm) {
      setError(t("errors:all_fields_required"));
      return;
    }
    if (password !== passwordConfirm) {
      setError(t("errors:password_mismatch"));
      return;
    }
    if (!token) {
      setError(t("errors:missing_reset_token"));
      return;
    }
    setLoading(true);
    try {
      const msg = await resetPassword(token, password, passwordConfirm);
      setSuccessMsg(msg);
      setSuccess(true);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError(t("errors:unexpected_error"));
      }
    } finally {
      setLoading(false);
    }
  };

  if (success && token) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[var(--color-surface-alt)] px-4">
        <div className="w-full max-w-sm rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-6 text-center shadow-sm">
          <svg
            className="mx-auto h-12 w-12 text-success-600"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={1.5}
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <h1 className="mt-3 text-lg font-semibold text-[var(--color-text)]">{t("auth.password_reset_title")}</h1>
          <p className="mt-2 text-sm text-[var(--color-text-secondary)]">{successMsg}</p>
          <Link to="/login" className="mt-4 inline-block">
            <Button>{t("auth.sign_in")}</Button>
          </Link>
        </div>
      </div>
    );
  }

  if (!token) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[var(--color-surface-alt)] px-4">
        <div className="w-full max-w-sm rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-6 shadow-sm">
          <h1 className="mb-6 text-center text-xl font-semibold text-[var(--color-text)]">
            {t("auth.reset_password")}
          </h1>

          {success && (
            <Alert variant="success" className="mb-4">
              {successMsg}
            </Alert>
          )}
          {error && (
            <Alert variant="error" className="mb-4">
              {error}
            </Alert>
          )}

          <form onSubmit={handleRequest} className="space-y-4">
            <label className="flex flex-col gap-1">
              <span className="text-sm font-medium text-[var(--color-text)]">{t("auth.email")}</span>
              <TextInput
                type="email"
                placeholder="user@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                autoComplete="email"
              />
            </label>
            <Button type="submit" className="w-full" loading={loading}>
              {t("auth.send_reset_link")}
            </Button>
          </form>

          <p className="mt-4 text-center text-sm">
            <Link to="/login" className="text-[var(--color-text-secondary)] hover:text-[var(--color-text)]">
              {t("auth.back_to_sign_in")}
            </Link>
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-[var(--color-surface-alt)] px-4">
      <div className="w-full max-w-sm rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-6 shadow-sm">
        <h1 className="mb-6 text-center text-xl font-semibold text-[var(--color-text)]">
          {t("auth.set_new_password")}
        </h1>

        {error && (
          <Alert variant="error" className="mb-4">
            {error}
          </Alert>
        )}

        <form onSubmit={handleReset} className="space-y-4">
          <label className="flex flex-col gap-1">
            <span className="text-sm font-medium text-[var(--color-text)]">{t("auth.new_password")}</span>
            <TextInput
              type="password"
              placeholder="••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="new-password"
            />
            <PasswordStrengthIndicator password={password} />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-sm font-medium text-[var(--color-text)]">{t("auth.confirm_password")}</span>
            <TextInput
              type="password"
              placeholder="••••••••"
              value={passwordConfirm}
              onChange={(e) => setPasswordConfirm(e.target.value)}
              autoComplete="new-password"
            />
          </label>
          <Button type="submit" className="w-full" loading={loading}>
            {t("auth.reset_password")}
          </Button>
        </form>
      </div>
    </div>
  );
}

import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate } from "react-router-dom";
import { TextInput, Button, Alert } from "@/components/ui";
import { useAuthStore } from "@/stores/authStore";
import { ApiError } from "@/services/api";

export default function LoginPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const login = useAuthStore((s) => s.login);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!email || !password) { setError(t("errors.email_password_required")); return; }
    setLoading(true);
    try {
      await login(email, password);
      navigate("/ping");
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError(t("errors.unexpected_error"));
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-[var(--color-surface-alt)] px-4">
      <div className="w-full max-w-sm rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-6 shadow-sm">
        <h1 className="mb-6 text-center text-xl font-semibold text-[var(--color-text)]">{t("auth.sign_in")}</h1>

        {error && <Alert variant="error" className="mb-4">{error}</Alert>}

        <form onSubmit={handleSubmit} className="space-y-4">
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

          <label className="flex flex-col gap-1">
            <span className="text-sm font-medium text-[var(--color-text)]">{t("auth.password")}</span>
            <div className="relative">
              <TextInput
                type={showPassword ? "text" : "password"}
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
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
          </label>

          <Button type="submit" className="w-full" loading={loading}>{t("auth.sign_in")}</Button>
        </form>

        <div className="mt-4 text-center text-sm space-y-2">
          <p><Link to="/reset-password" className="text-primary-600 hover:text-primary-700">{t("auth.forgot_password")}</Link></p>
          <p className="text-[var(--color-text-secondary)]">{t("auth.no_account")} <Link to="/register" className="text-primary-600 hover:text-primary-700">{t("auth.sign_up")}</Link></p>
          <p><Link to="/ping" className="text-[var(--color-text-secondary)] hover:text-[var(--color-text)]">{t("auth.continue_as_guest")}</Link></p>
        </div>
      </div>
    </div>
  );
}

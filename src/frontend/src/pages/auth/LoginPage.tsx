import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import LoginForm from "@/components/auth/LoginForm";

export default function LoginPage() {
  const { t } = useTranslation();

  return (
    <div className="flex min-h-screen items-center justify-center bg-[var(--color-surface-alt)] px-4">
      <div className="w-full max-w-sm rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-6 shadow-sm">
        <LoginForm />

        <div className="mt-4 text-center text-sm space-y-2">
          <p><Link to="/reset-password" className="text-primary-600 hover:text-primary-700">{t("auth.forgot_password")}</Link></p>
          <p className="text-[var(--color-text-secondary)]">{t("auth.no_account")} <Link to="/register" className="text-primary-600 hover:text-primary-700">{t("auth.sign_up")}</Link></p>
          <p><Link to="/ping" className="text-[var(--color-text-secondary)] hover:text-[var(--color-text)]">{t("auth.continue_as_guest")}</Link></p>
        </div>
      </div>
    </div>
  );
}

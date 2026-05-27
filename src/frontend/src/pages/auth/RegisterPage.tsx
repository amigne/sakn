import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import RegisterForm from "@/components/auth/RegisterForm";

export default function RegisterPage() {
  const { t } = useTranslation();

  return (
    <main className="flex min-h-screen items-center justify-center bg-[var(--color-surface-alt)] px-4">
      <div className="w-full max-w-sm rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-6 shadow-sm">
        <RegisterForm />

        <p className="mt-4 text-center text-sm text-[var(--color-text-secondary)]">
          {t("auth.has_account")}{" "}
          <Link
            to="/login"
            className="underline text-primary-600 hover:text-primary-700 dark:text-primary-400 dark:hover:text-primary-300"
          >
            {t("auth.sign_in")}
          </Link>
        </p>
      </div>
    </main>
  );
}

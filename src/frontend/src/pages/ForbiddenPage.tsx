import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import PageLayout from "@/components/layout/PageLayout";

export default function ForbiddenPage() {
  const { t } = useTranslation();

  return (
    <PageLayout>
      <div className="flex items-center justify-center py-20">
        <div className="text-center">
          <h1 className="text-4xl font-bold text-[var(--color-text)]">403</h1>
          <p className="mt-2 text-[var(--color-text-secondary)]">{t("common.forbidden")}</p>
          <Link to="/" className="mt-4 inline-block text-sm text-primary-600 hover:text-primary-700">
            {t("common.back_home")}
          </Link>
        </div>
      </div>
    </PageLayout>
  );
}

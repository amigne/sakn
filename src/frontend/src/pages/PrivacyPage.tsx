import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import PageLayout from "@/components/layout/PageLayout";

async function fetchRetentionDays(): Promise<number> {
  try {
    const res = await fetch("/api/v1/public-settings");
    if (!res.ok) return 90;
    const data = await res.json();
    return parseInt(data.settings?.log_retention_days ?? "90", 10) || 90;
  } catch {
    return 90;
  }
}

export default function PrivacyPage() {
  const { t } = useTranslation();
  const [retentionDays, setRetentionDays] = useState<number | null>(null);

  useEffect(() => {
    fetchRetentionDays().then(setRetentionDays);
  }, []);

  return (
    <PageLayout>
      <div className="max-w-2xl mx-auto prose prose-sm dark:prose-invert">
        <h1 className="text-lg font-semibold text-[var(--color-text)] mb-4">
          {t("privacy.title")}
        </h1>

        <section className="mb-6">
          <h2 className="text-base font-medium text-[var(--color-text)] mb-2">
            {t("privacy.cookies.title")}
          </h2>
          <div className="space-y-3 text-sm text-[var(--color-text-secondary)]">
            <p>{t("privacy.cookies.intro")}</p>

            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="border-b border-[var(--color-border)]">
                    <th scope="col" className="py-2 pe-4 text-xs font-semibold uppercase">{t("privacy.cookies.cookie_header")}</th>
                    <th scope="col" className="py-2 pe-4 text-xs font-semibold uppercase">{t("privacy.cookies.purpose_header")}</th>
                    <th scope="col" className="py-2 pe-4 text-xs font-semibold uppercase">{t("privacy.cookies.duration_header")}</th>
                    <th scope="col" className="py-2 text-xs font-semibold uppercase">{t("privacy.cookies.access_header")}</th>
                  </tr>
                </thead>
                <tbody className="align-top">
                  <tr className="border-b border-[var(--color-border)]">
                    <td className="py-2 pe-4 font-mono text-xs">sakn_session</td>
                    <td className="py-2 pe-4">{t("privacy.cookies.session_purpose")}</td>
                    <td className="py-2 pe-4 text-xs">{t("privacy.cookies.session_duration")}</td>
                    <td className="py-2 text-xs">{t("privacy.cookies.session_access")}</td>
                  </tr>
                  <tr className="border-b border-[var(--color-border)]">
                    <td className="py-2 pe-4 font-mono text-xs">sakn_csrf</td>
                    <td className="py-2 pe-4">{t("privacy.cookies.csrf_purpose")}</td>
                    <td className="py-2 pe-4 text-xs">{t("privacy.cookies.csrf_duration")}</td>
                    <td className="py-2 text-xs">{t("privacy.cookies.csrf_access")}</td>
                  </tr>
                </tbody>
              </table>
            </div>

            <p>{t("privacy.cookies.no_tracking")}</p>
          </div>
        </section>

        <section className="mb-6">
          <h2 className="text-base font-medium text-[var(--color-text)] mb-2">
            {t("privacy.data_stored.title")}
          </h2>
          <div className="text-sm text-[var(--color-text-secondary)] space-y-2">
            <p>{t("privacy.data_stored.intro")}</p>
            <ul className="list-disc ps-5 space-y-1">
              <li>{t("privacy.data_stored.item_email")}</li>
              <li>{t("privacy.data_stored.item_password")}</li>
              <li>{t("privacy.data_stored.item_preferences")}</li>
              <li>{t("privacy.data_stored.item_sessions")}</li>
            </ul>
            <p>
              {t("privacy.data_stored.retention", { days: retentionDays ?? 90 })}
            </p>
          </div>
        </section>

        <section className="mb-6">
          <h2 className="text-base font-medium text-[var(--color-text)] mb-2">
            {t("privacy.rights.title")}
          </h2>
          <div className="text-sm text-[var(--color-text-secondary)] space-y-2">
            <p>{t("privacy.rights.intro")}</p>
            <ul className="list-disc ps-5 space-y-1">
              <li><strong>{t("privacy.rights.access")}</strong></li>
              <li><strong>{t("privacy.rights.rectify")}</strong></li>
              <li><strong>{t("privacy.rights.delete")}</strong></li>
              <li><strong>{t("privacy.rights.portability")}</strong></li>
            </ul>
            <p>{t("privacy.rights.contact")}</p>
          </div>
        </section>

        <section className="mb-6">
          <h2 className="text-base font-medium text-[var(--color-text)] mb-2">
            {t("privacy.controller.title")}
          </h2>
          <p className="text-sm text-[var(--color-text-secondary)]">
            Yann GAUTERON<br />
            {t("privacy.controller.email")}: yann@gauteron.me<br />
            {t("privacy.controller.hosting")}
          </p>
        </section>

        <p className="text-xs text-[var(--color-text-secondary)]">
          {t("privacy.last_updated", { date: "2026-05-15" })}
        </p>
      </div>
    </PageLayout>
  );
}

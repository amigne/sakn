import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { NavLink, useLocation } from "react-router-dom";
import PageLayout from "@/components/layout/PageLayout";

const ADMIN_TAB_KEYS = [
  { key: "admin.users", to: "/admin/users" },
  { key: "admin.access", to: "/admin/access" },
  { key: "admin.rate_limits", to: "/admin/rate-limits" },
  { key: "admin.modules", to: "/admin/modules" },
  { key: "admin.settings", to: "/admin/settings" },
  { key: "admin.logs", to: "/admin/logs" },
];

interface AdminLayoutProps {
  children: ReactNode;
  title?: string;
}

export default function AdminLayout({ children, title }: AdminLayoutProps) {
  const { t } = useTranslation();
  const location = useLocation();

  return (
    <PageLayout>
      <div className="border-b border-[var(--color-border)] mb-4">
        <nav className="flex overflow-x-auto" aria-label={t("admin.section_title")}>
          {ADMIN_TAB_KEYS.map((tab) => {
            const isActive = location.pathname.startsWith(tab.to);
            return (
              <NavLink
                key={tab.to}
                to={tab.to}
                className={`focus-ring shrink-0 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
                  isActive
                    ? "border-primary-600 text-primary-600"
                    : "border-transparent text-[var(--color-text-secondary)] hover:text-[var(--color-text)]"
                }`}
              >
                {t(tab.key)}
              </NavLink>
            );
          })}
        </nav>
      </div>
      {title && <h1 className="text-lg font-semibold text-[var(--color-text)] mb-4">{title}</h1>}
      {children}
    </PageLayout>
  );
}

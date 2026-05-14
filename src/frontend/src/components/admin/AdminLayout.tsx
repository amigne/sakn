import { NavLink, useLocation } from "react-router-dom";
import PageLayout from "@/components/layout/PageLayout";
import type { ReactNode } from "react";

const adminTabs = [
  { label: "Users", to: "/admin/users" },
  { label: "Access", to: "/admin/access" },
  { label: "Rate Limits", to: "/admin/rate-limits" },
  { label: "Modules", to: "/admin/modules" },
  { label: "Settings", to: "/admin/settings" },
  { label: "Logs", to: "/admin/logs" },
];

interface AdminLayoutProps {
  children: ReactNode;
  title?: string;
}

export default function AdminLayout({ children, title }: AdminLayoutProps) {
  const location = useLocation();

  return (
    <PageLayout>
      <div className="border-b border-[var(--color-border)] mb-4">
        <nav className="flex overflow-x-auto" aria-label="Admin tabs">
          {adminTabs.map((tab) => {
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
                {tab.label}
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

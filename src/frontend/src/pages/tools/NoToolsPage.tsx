import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import PageLayout from "@/components/layout/PageLayout";
import { api } from "@/services/api";
import { useAuthStore } from "@/stores/authStore";

export default function NoToolsPage() {
  const { t } = useTranslation();
  const user = useAuthStore((s) => s.user);
  const [authTools, setAuthTools] = useState<string[]>([]);

  useEffect(() => {
    api<{ tools: string[] }>("/tools/available-for/authenticated")
      .then((data) => setAuthTools(data.tools ?? []))
      .catch(() => {});
  }, []);

  return (
    <PageLayout>
      <div className="flex flex-col items-center justify-center min-h-[60vh] text-center px-4">
        <div className="text-6xl mb-4">&#128274;</div>
        <h1 className="text-xl font-semibold text-[var(--color-text)] mb-2">
          {t("notools.title")}
        </h1>
        <p className="text-sm text-[var(--color-text-secondary)] max-w-md mb-6">
          {user
            ? t("notools.message")
            : t("notools.message_visitor")}
        </p>

        {!user && authTools.length > 0 && (
          <ul className="text-sm text-[var(--color-text)] space-y-1 mb-6">
            {authTools.map((name) => (
              <li key={name} className="capitalize">{name.replace(/_/g, " ")}</li>
            ))}
          </ul>
        )}

        {!user && (
          <Link
            to="/register"
            className="inline-block px-4 py-2 text-sm font-medium text-white bg-primary-600 rounded-md hover:bg-primary-700"
          >
            {t("notools.register")}
          </Link>
        )}
      </div>
    </PageLayout>
  );
}

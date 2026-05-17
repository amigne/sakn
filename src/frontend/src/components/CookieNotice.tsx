import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";

const STORAGE_KEY = "sakn_cookie_notice_dismissed";

export default function CookieNotice() {
  const { t } = useTranslation();
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const dismissed = localStorage.getItem(STORAGE_KEY);
    if (!dismissed) {
      setVisible(true);
    }
  }, []);

  if (!visible) return null;

  return (
    <div className="fixed bottom-0 start-0 end-0 z-50 border-t border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 px-4 py-2.5 shadow-lg">
      <div className="flex flex-wrap items-center justify-center gap-2 text-xs text-[var(--color-text-secondary)]">
        <span>
          {t("cookies.notice")}{" "}
          <Link to="/privacy" className="underline underline-offset-2 hover:text-[var(--color-text)]">{t("cookies.learn_more")}</Link>
        </span>
        <button
          onClick={() => {
            localStorage.setItem(STORAGE_KEY, "1");
            setVisible(false);
          }}
          className="rounded px-3 py-1 text-xs font-medium bg-gray-100 dark:bg-gray-800 text-[var(--color-text)] hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors"
        >
          {t("cookies.accept")}
        </button>
      </div>
    </div>
  );
}

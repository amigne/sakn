import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate } from "react-router-dom";
import { getLanguage, setLanguage } from "@/i18n/i18n";
import { useAuthStore } from "@/stores/authStore";
import { useThemeStore } from "@/stores/themeStore";
import type { ThemeMode } from "@/types/user";

interface TopBarProps {
  onToggleSidebar: () => void;
  showHamburger?: boolean;
}

export default function TopBar({ onToggleSidebar, showHamburger = false }: TopBarProps) {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const user = useAuthStore((s) => s.user);
  const logout = useAuthStore((s) => s.logout);
  const { mode, setMode } = useThemeStore();

  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) setMenuOpen(false);
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  const [currentLang, setCurrentLang] = useState(() => getLanguage());

  const toggleTheme = () => {
    const order: ThemeMode[] = ["light", "dark", "system"];
    const idx = order.indexOf(mode ?? "system");
    setMode(order[(idx + 1) % order.length] ?? "system");
  };

  const toggleLanguage = () => {
    const next = currentLang === "en" ? "fr" : "en";
    setLanguage(next);
    setCurrentLang(next);
    const currentUser = useAuthStore.getState().user;
    if (currentUser) {
      useAuthStore
        .getState()
        .savePreferences({ language: next })
        .catch(() => {});
    }
  };

  // Compute initials for avatar (skip whitespace-only names)
  const initials = (() => {
    const first = user?.first_name?.trim();
    const last = user?.last_name?.trim();
    if (first && last) {
      return (first.charAt(0) + last.charAt(0)).toUpperCase();
    }
    if (first) {
      return first.charAt(0).toUpperCase();
    }
    if (user?.email) {
      return user.email.trim().charAt(0).toUpperCase();
    }
    return "?";
  })();

  const currentMode: ThemeMode = mode ?? "system";
  const themeIcon =
    currentMode === "dark"
      ? "M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z"
      : currentMode === "light"
        ? "M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z"
        : "M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z";

  return (
    <header className="flex h-12 items-center justify-between border-b border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 px-4">
      <div className="flex items-center gap-2">
        {showHamburger && (
          <button
            onClick={onToggleSidebar}
            className="rounded p-1.5 text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
            aria-label={t("common.toggle_sidebar")}
          >
            <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5" />
            </svg>
          </button>
        )}
        <Link to="/ping" className="flex items-center gap-2 font-semibold text-gray-900 dark:text-gray-100">
          <svg
            className="h-6 w-6 text-blue-600 dark:text-blue-400"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth={2}
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
          </svg>
          <span className="hidden min-[350px]:inline">SAKN</span>
        </Link>
      </div>

      <div className="flex items-center gap-2">
        <button
          onClick={toggleLanguage}
          className="rounded px-2 py-1 text-xs font-medium text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
          aria-label={t("common.switch_language")}
          data-testid="language-toggle"
        >
          {currentLang.toUpperCase()}
        </button>

        <button
          onClick={toggleTheme}
          className="rounded p-1.5 text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
          aria-label={`Theme: ${mode}`}
        >
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d={themeIcon} />
          </svg>
        </button>

        {user ? (
          <div className="relative" ref={menuRef}>
            <button
              onClick={() => setMenuOpen(!menuOpen)}
              className="flex items-center gap-1.5 rounded-full hover:ring-2 hover:ring-blue-200 dark:hover:ring-blue-800 transition-all"
              title={user.email || ""}
            >
              <span className="flex items-center justify-center w-7 h-7 rounded-full bg-blue-600 text-white text-xs font-semibold">
                {initials}
              </span>
              <svg
                className="h-3 w-3 text-gray-400"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={2}
              >
                <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
              </svg>
            </button>
            {menuOpen && (
              <div className="absolute end-0 top-full mt-1 w-48 rounded-md border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 shadow-lg z-50">
                <Link
                  to="/account/preferences"
                  onClick={() => setMenuOpen(false)}
                  className="block px-3 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700"
                >
                  {t("auth.preferences")}
                </Link>
                <Link
                  to="/account/sessions"
                  onClick={() => setMenuOpen(false)}
                  className="block px-3 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700"
                >
                  {t("auth.sessions")}
                </Link>
                <hr className="border-gray-200 dark:border-gray-700" />
                <button
                  onClick={async () => {
                    await logout();
                    setMenuOpen(false);
                    navigate("/ping");
                  }}
                  className="w-full px-3 py-2 text-start text-sm text-red-600 hover:bg-gray-100 dark:hover:bg-gray-700"
                >
                  {t("auth.logout")}
                </button>
              </div>
            )}
          </div>
        ) : (
          <Link to="/login" className="text-sm text-blue-600 hover:text-blue-700 dark:text-blue-400">
            {t("auth.sign_in")}
          </Link>
        )}
      </div>
    </header>
  );
}

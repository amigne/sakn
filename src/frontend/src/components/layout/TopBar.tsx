import { Link } from "react-router-dom";
import { useAuthStore } from "@/stores/authStore";
import { useThemeStore } from "@/stores/themeStore";
import type { ThemeMode, UserRole } from "@/types/user";
import { useState, useRef, useEffect } from "react";

export default function TopBar() {
  const devRole = useAuthStore((s) => s.devRole);
  const storeUser = useAuthStore((s) => s.user);
  const setDevRole = useAuthStore((s) => s.setDevRole);
  const logout = useAuthStore((s) => s.logout);
  const { mode, setMode } = useThemeStore();
  const user = devRole === "visitor" ? null : storeUser;

  const [menuOpen, setMenuOpen] = useState(false);
  const [devOpen, setDevOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const devRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) setMenuOpen(false);
      if (devRef.current && !devRef.current.contains(e.target as Node)) setDevOpen(false);
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  const toggleTheme = () => {
    const order: ThemeMode[] = ["light", "dark", "system"];
    const idx = order.indexOf(mode ?? "system");
    setMode(order[(idx + 1) % order.length] ?? "system");
  };

  const currentMode: ThemeMode = mode ?? "system";
  const themeIcon =
    currentMode === "dark" ? "M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" :
    currentMode === "light" ? "M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" :
    "M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z";

  const roleLabels: Record<UserRole, string> = { visitor: "Visitor", authenticated: "User", administrator: "Admin" };

  return (
    <header className="flex h-12 items-center justify-between border-b border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 px-4">
      <Link to="/ping" className="flex items-center gap-2 font-semibold text-gray-900 dark:text-gray-100">
        <svg className="h-6 w-6 text-blue-600 dark:text-blue-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
        </svg>
        <span className="hidden sm:inline">SAKN</span>
      </Link>

      <div className="flex items-center gap-2">
        <button
          className="rounded px-2 py-1 text-xs font-medium text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
          aria-label="Switch language"
        >
          EN
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
              className="flex items-center gap-1 rounded px-2 py-1 text-sm text-gray-700 dark:text-gray-300"
            >
              <span className="hidden sm:inline max-w-[120px] truncate">{user.email}</span>
              <svg className="h-3 w-3 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
              </svg>
            </button>
            {menuOpen && (
              <div className="absolute end-0 top-full mt-1 w-48 rounded-md border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 shadow-lg z-50">
                <Link to="/account/preferences" onClick={() => setMenuOpen(false)} className="block px-3 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700">Preferences</Link>
                <Link to="/account/sessions" onClick={() => setMenuOpen(false)} className="block px-3 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700">Sessions</Link>
                <hr className="border-gray-200 dark:border-gray-700" />
                <button onClick={() => { logout(); setMenuOpen(false); }} className="w-full px-3 py-2 text-start text-sm text-red-600 hover:bg-gray-100 dark:hover:bg-gray-700">Logout</button>
              </div>
            )}
          </div>
        ) : (
          <Link to="/login" className="text-sm text-blue-600 hover:text-blue-700 dark:text-blue-400">
            Sign In
          </Link>
        )}

        {/* Dev toolbar */}
        <div className="relative ms-2" ref={devRef}>
          <button
            onClick={() => setDevOpen(!devOpen)}
            className="rounded border border-amber-500 px-2 py-0.5 text-xs font-medium text-amber-600 dark:text-amber-400"
          >
            Dev: {devRole ? roleLabels[devRole] : "Live"}
          </button>
          {devOpen && (
            <div className="absolute end-0 top-full mt-1 w-36 rounded-md border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 shadow-lg z-50">
              <button onClick={() => { setDevRole(null); setDevOpen(false); }} className="w-full px-3 py-2 text-start text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700">Live</button>
              <button onClick={() => { setDevRole("visitor"); setDevOpen(false); }} className="w-full px-3 py-2 text-start text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700">Visitor</button>
              <button onClick={() => { setDevRole("authenticated"); setDevOpen(false); }} className="w-full px-3 py-2 text-start text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700">User</button>
              <button onClick={() => { setDevRole("administrator"); setDevOpen(false); }} className="w-full px-3 py-2 text-start text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700">Admin</button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}

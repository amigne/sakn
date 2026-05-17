import { useState, useEffect, useCallback, useRef, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import TopBar from "./TopBar";
import Sidebar from "./Sidebar";

interface PageLayoutProps {
  children: ReactNode;
}

type Breakpoint = "mobile" | "tablet" | "desktop";

function getBreakpoint(w: number): Breakpoint {
  if (w < 768) return "mobile";
  if (w < 1024) return "tablet";
  return "desktop";
}

function getDefaultCollapsed(bp: Breakpoint): boolean {
  return bp === "tablet";
}

export default function PageLayout({ children }: PageLayoutProps) {
  const { t } = useTranslation();
  const [collapsed, setCollapsed] = useState(() => {
    if (typeof window === "undefined") return false;
    return getDefaultCollapsed(getBreakpoint(window.innerWidth));
  });
  const [mobileOpen, setMobileOpen] = useState(false);
  const [isMobile, setIsMobile] = useState(() => {
    if (typeof window === "undefined") return false;
    return window.innerWidth < 768;
  });
  const bpRef = useRef<Breakpoint | null>(null);

  useEffect(() => {
    const handler = () => {
      const w = window.innerWidth;
      const newBp = getBreakpoint(w);
      const prevBp = bpRef.current;

      setIsMobile(w < 768);

      if (prevBp !== null && newBp !== prevBp) {
        // Breakpoint changed — reset to default behavior
        if (newBp === "mobile") {
          setMobileOpen(false);
        } else if (newBp === "tablet") {
          setCollapsed(true);
          setMobileOpen(false);
        } else {
          // desktop
          setCollapsed(false);
          setMobileOpen(false);
        }
      }
      // Within same breakpoint, preserve user's choice
      bpRef.current = newBp;
    };

    bpRef.current = getBreakpoint(window.innerWidth);
    window.addEventListener("resize", handler);
    return () => window.removeEventListener("resize", handler);
  }, []);

  const toggleSidebar = useCallback(() => {
    const bp = bpRef.current ?? getBreakpoint(window.innerWidth);
    if (bp === "mobile") {
      setMobileOpen((prev) => !prev);
    } else {
      setCollapsed((prev) => !prev);
    }
  }, []);

  const closeMobile = useCallback(() => setMobileOpen(false), []);

  return (
    <div className="flex h-screen flex-col bg-gray-100 dark:bg-gray-950 text-gray-900 dark:text-gray-100">
      <TopBar onToggleSidebar={toggleSidebar} showHamburger={isMobile} />
      <div className="flex flex-1 overflow-hidden">
        {/* Desktop/tablet: inline sidebar */}
        {!isMobile && (
          <Sidebar collapsed={collapsed} onToggle={toggleSidebar} showToggle />
        )}

        {/* Mobile: overlay sidebar */}
        {isMobile && mobileOpen && (
          <>
            <div className="fixed inset-0 z-40 bg-black/50" onClick={closeMobile} aria-hidden="true" />
            <div className="fixed inset-y-0 start-0 z-50">
              <Sidebar collapsed={false} onNavigate={closeMobile} />
            </div>
          </>
        )}

        <main className="flex-1 overflow-auto p-4">
          {children}
        </main>
      </div>
      <footer className="border-t border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 px-4 py-1 text-center text-xs text-gray-500 dark:text-gray-400">
        SAKN v0.0.2 — {t("common.footer.tagline")} — {t("common.footer.copyright", { year: 2026 })}
        {" "}·{" "}
        <Link to="/privacy" className="hover:text-gray-700 dark:hover:text-gray-300 underline underline-offset-2">{t("common.privacy")}</Link>
      </footer>
    </div>
  );
}

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { type ReactNode, useEffect } from "react";
import { BrowserRouter } from "react-router-dom";
import { useAuthStore } from "@/stores/authStore";
import { useThemeStore } from "@/stores/themeStore";
import "@/i18n/i18n";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
    },
  },
});

function ThemeProvider({ children }: { children: ReactNode }) {
  const { mode, applyTheme } = useThemeStore();

  useEffect(() => {
    applyTheme(mode);

    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const handler = () => {
      if (mode === "system") applyTheme("system");
    };
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, [mode, applyTheme]);

  return <>{children}</>;
}

function AuthInitializer({ children }: { children: ReactNode }) {
  const init = useAuthStore((s) => s.init);
  const loadPreferences = useAuthStore((s) => s.loadPreferences);

  useEffect(() => {
    const restore = async () => {
      await init();
      // If user was restored, also load preferences and apply theme
      const user = useAuthStore.getState().user;
      if (user) {
        await loadPreferences();
        const prefs = useAuthStore.getState().preferences;
        if (prefs?.theme) {
          useThemeStore.getState().setMode(prefs.theme);
        }
        if (prefs?.locale) {
          import("@/i18n/i18n").then(({ setLanguage }) => setLanguage(prefs.locale!));
        }
      }
    };
    restore();
  }, [init, loadPreferences]);

  return <>{children}</>;
}

interface ProvidersProps {
  children: ReactNode;
}

export default function Providers({ children }: ProvidersProps) {
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <BrowserRouter>
          <AuthInitializer>{children}</AuthInitializer>
        </BrowserRouter>
      </ThemeProvider>
    </QueryClientProvider>
  );
}

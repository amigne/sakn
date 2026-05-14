import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter } from "react-router-dom";
import { useEffect, type ReactNode } from "react";
import { useThemeStore } from "@/stores/themeStore";

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
    const handler = () => { if (mode === "system") applyTheme("system"); };
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, [mode, applyTheme]);

  return <>{children}</>;
}

interface ProvidersProps {
  children: ReactNode;
}

export default function Providers({ children }: ProvidersProps) {
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <BrowserRouter>{children}</BrowserRouter>
      </ThemeProvider>
    </QueryClientProvider>
  );
}

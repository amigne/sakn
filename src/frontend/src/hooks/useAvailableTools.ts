import { useState, useEffect } from "react";
import { api } from "@/services/api";
import { useAuthStore } from "@/stores/authStore";

const TOOL_ROUTES: Record<string, string> = {
  ping: "/ping",
  traceroute: "/traceroute",
  dns_lookup: "/dns",
  ssl_viewer: "/ssl",
};

let cache: { names: string[]; checked: boolean; userId: string | undefined } = {
  names: [],
  checked: false,
  userId: undefined,
};

export { TOOL_ROUTES };

export function invalidateToolCache() {
  cache = { names: [], checked: false, userId: undefined };
}

export function useAvailableTools() {
  const userId = useAuthStore((s) => s.user?.id);
  const isInitialized = useAuthStore((s) => s.isInitialized);
  const [tools, setTools] = useState<string[]>(cache.names);
  const [checked, setChecked] = useState(cache.checked);

  useEffect(() => {
    // Wait for auth to resolve before fetching
    if (!isInitialized) return;

    // Invalidate cache when user identity changes
    if (cache.userId !== userId) {
      cache = { names: [], checked: false, userId };
      setTools([]);
      setChecked(false);
      // Fall through to fetch
    }

    if (cache.checked) {
      setTools(cache.names);
      setChecked(true);
      return;
    }
    let cancelled = false;
    api<{ tools: { name: string }[] }>("/tools")
      .then((data) => {
        const names = data.tools.map((t) => t.name);
        cache = { names, checked: true, userId };
        if (!cancelled) {
          setTools(names);
          setChecked(true);
        }
      })
      .catch(() => {
        if (!cancelled) {
          cache = { names: ["ping", "traceroute", "dns_lookup", "ssl_viewer"], checked: true, userId };
          setTools(cache.names);
          setChecked(true);
        }
      });
    return () => { cancelled = true; };
  }, [userId, isInitialized]);

  return { tools, checked };
}

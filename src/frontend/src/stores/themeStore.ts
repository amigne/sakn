import { create } from "zustand";
import type { ThemeMode } from "@/types/user";

interface ThemeState {
  mode: ThemeMode;
  setMode: (mode: ThemeMode) => void;
  applyTheme: (mode: ThemeMode) => void;
}

function getSystemTheme(): "light" | "dark" {
  if (typeof window === "undefined") return "light";
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function getStoredTheme(): ThemeMode {
  if (typeof window === "undefined") return "system";
  return (localStorage.getItem("theme") as ThemeMode) || "system";
}

function applyThemeClass(mode: ThemeMode) {
  const root = document.documentElement;
  const resolved = mode === "system" ? getSystemTheme() : mode;
  if (resolved === "dark") {
    root.classList.add("dark");
  } else {
    root.classList.remove("dark");
  }
}

export const useThemeStore = create<ThemeState>((set, get) => ({
  mode: getStoredTheme(),
  setMode: (mode) => {
    localStorage.setItem("theme", mode);
    set({ mode });
    get().applyTheme(mode);
  },
  applyTheme: (mode) => {
    applyThemeClass(mode);
  },
}));

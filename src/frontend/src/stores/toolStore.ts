import { create } from "zustand";
import type { ToolName } from "@/types/tool";

type DisplayMode = "table" | "text";

interface ToolState {
  activeTool: ToolName;
  setActiveTool: (tool: ToolName) => void;
  displayMode: Record<string, DisplayMode>;
  setDisplayMode: (tool: ToolName, mode: DisplayMode) => void;
  getDisplayMode: (tool: ToolName) => DisplayMode;
}

function getStoredDisplayMode(tool: ToolName): DisplayMode {
  if (typeof window === "undefined") return "table";
  const stored = localStorage.getItem(`displayMode:${tool}`);
  if (stored === "text" || stored === "table") return stored;
  return "table";
}

export const useToolStore = create<ToolState>((set, get) => ({
  activeTool: "ping",
  setActiveTool: (tool) => set({ activeTool: tool }),

  displayMode: {
    ping: getStoredDisplayMode("ping"),
    traceroute: getStoredDisplayMode("traceroute"),
    dns_lookup: getStoredDisplayMode("dns_lookup"),
    ssl_viewer: "table",
  },

  setDisplayMode: (tool, mode) => {
    localStorage.setItem(`displayMode:${tool}`, mode);
    set((state) => ({
      displayMode: { ...state.displayMode, [tool]: mode },
    }));
  },

  getDisplayMode: (tool) => {
    return get().displayMode[tool] ?? "table";
  },
}));

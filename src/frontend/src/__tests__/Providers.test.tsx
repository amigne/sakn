import { render, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

// jsdom polyfill — not available in test environment
window.matchMedia =
  window.matchMedia ??
  (() =>
    ({
      matches: false,
      addEventListener: () => {},
      removeEventListener: () => {},
      addListener: () => {},
      removeListener: () => {},
    }) as unknown as MediaQueryList);

const { mockSetLanguage } = vi.hoisted(() => ({
  mockSetLanguage: vi.fn(),
}));
vi.mock("@/i18n/i18n", async () => {
  const actual = await vi.importActual<typeof import("@/i18n/i18n")>("@/i18n/i18n");
  return { ...actual, setLanguage: mockSetLanguage, getLanguage: () => "en" };
});

const mockInit = vi.fn(async () => {});
const mockLoadPreferences = vi.fn(async () => {});
const mockSetMode = vi.fn();

vi.mock("@/stores/authStore", () => ({
  useAuthStore: Object.assign(
    vi.fn((selector?: (s: unknown) => unknown) => {
      const store = {
        isInitialized: false,
        user: null,
        init: mockInit,
        loadPreferences: mockLoadPreferences,
        preferences: null,
      };
      return typeof selector === "function" ? selector(store) : store;
    }),
    {
      getState: vi.fn(() => ({
        user: {
          id: "u1",
          email: "x@y.z",
          first_name: "X",
          last_name: "Y",
          role: "authenticated",
          status: "active",
          email_verified: true,
          locale: "en-US",
          created_at: "2024-01-01T00:00:00Z",
        },
        preferences: { language: "fr", locale: "fr-FR", theme: "light", display_mode: "table" },
        loadPreferences: mockLoadPreferences,
      })),
      setState: vi.fn(),
    },
  ),
}));

vi.mock("@/stores/themeStore", () => ({
  useThemeStore: Object.assign(
    vi.fn(() => ({ mode: "system", setMode: mockSetMode, applyTheme: vi.fn() })),
    {
      getState: vi.fn(() => ({ mode: "system", setMode: mockSetMode })),
      setState: vi.fn(),
    },
  ),
}));

// Providers already includes a BrowserRouter — mock it to avoid nesting
vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>("react-router-dom");
  return { ...actual, BrowserRouter: ({ children }: { children: React.ReactNode }) => children };
});

import Providers from "@/Providers";

describe("Providers AuthInitializer — bug #214 #1 (restore language from prefs.language)", () => {
  beforeEach(() => {
    mockSetLanguage.mockReset();
    mockInit.mockReset();
    mockLoadPreferences.mockReset();
    mockInit.mockResolvedValue(undefined);
    mockLoadPreferences.mockResolvedValue(undefined);
  });

  it("calls setLanguage with prefs.language (not prefs.locale) on init", async () => {
    render(
      <Providers>
        <div data-testid="child" />
      </Providers>,
    );

    await waitFor(() => {
      expect(mockSetLanguage).toHaveBeenCalledWith("fr");
    });
  });
});

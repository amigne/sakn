import { render, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import React from "react";

// ── Mocks ────────────────────────────────────────────────────────────────────

const { setLanguageMock, setModeMock } = vi.hoisted(() => ({
  setLanguageMock: vi.fn(),
  setModeMock: vi.fn(),
}));

vi.mock("@/i18n/i18n", () => ({
  setLanguage: setLanguageMock,
  getLanguage: () => "en",
  default: {
    language: "en",
    changeLanguage: vi.fn(),
    on: vi.fn(),
    off: vi.fn(),
    t: (k: string) => k,
  },
}));

const { initMock, loadPreferencesMock } = vi.hoisted(() => ({
  initMock: vi.fn(),
  loadPreferencesMock: vi.fn(),
}));

let storeSnapshot: {
  user: unknown;
  preferences: unknown;
  isLoading: boolean;
  isInitialized: boolean;
} = {
  user: null,
  preferences: null,
  isLoading: false,
  isInitialized: false,
};

const useAuthStoreMock = vi.hoisted(() =>
  Object.assign(
    vi.fn((s?: (state: Record<string, unknown>) => unknown) => {
      const full = { ...storeSnapshot, init: initMock, loadPreferences: loadPreferencesMock };
      return s ? s(full) : full;
    }),
    { getState: () => ({ ...storeSnapshot, init: initMock, loadPreferences: loadPreferencesMock }) },
  ),
);

vi.mock("@/stores/authStore", () => ({
  useAuthStore: useAuthStoreMock,
}));

const useThemeStoreMock = vi.hoisted(() =>
  Object.assign(
    vi.fn((s?: (state: { mode: string; setMode: typeof setModeMock; applyTheme: ReturnType<typeof vi.fn> }) => unknown) => {
      const state = { mode: "system", setMode: setModeMock, applyTheme: vi.fn() };
      return s ? s(state) : state;
    }),
    { getState: () => ({ mode: "system", setMode: setModeMock, applyTheme: vi.fn() }) },
  ),
);

vi.mock("@/stores/themeStore", () => ({
  useThemeStore: useThemeStoreMock,
}));

// Must import after mocks
import Providers from "@/Providers";

// jsdom doesn't implement matchMedia, but ThemeProvider calls it
Object.defineProperty(window, "matchMedia", {
  writable: true,
  value: vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
});

// ── Tests ────────────────────────────────────────────────────────────────────

describe("Providers / AuthInitializer", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    storeSnapshot = {
      user: null,
      preferences: null,
      isLoading: false,
      isInitialized: false,
    };
    initMock.mockImplementation(async () => {
      storeSnapshot.user = {
        email: "test@test.com",
        first_name: "T",
        last_name: "U",
        locale: "en-US",
      };
      storeSnapshot.isInitialized = true;
    });
    loadPreferencesMock.mockImplementation(async () => {
      storeSnapshot.preferences = {
        language: "fr",
        locale: "fr-FR",
        theme: "light",
        display_mode: "table",
      };
    });
  });

  it("calls setLanguage with prefs.language, not prefs.locale (Bug 1 regression)", async () => {
    render(
      <Providers>
        <div>child</div>
      </Providers>,
    );

    await waitFor(() => {
      expect(setLanguageMock).toHaveBeenCalled();
    });

    // The crucial regression check: setLanguage must receive "fr" (language code),
    // not "fr-FR" (BCP 47 locale string from prefs.locale)
    expect(setLanguageMock).toHaveBeenCalledWith("fr");
    expect(setLanguageMock).not.toHaveBeenCalledWith("fr-FR");
    expect(setLanguageMock).not.toHaveBeenCalledWith("en-US");
  });

  it("applies theme from preferences", async () => {
    render(
      <Providers>
        <div>child</div>
      </Providers>,
    );

    await waitFor(() => {
      expect(setModeMock).toHaveBeenCalledWith("light");
    });
  });

  it("does not call setLanguage when preferences have no language", async () => {
    loadPreferencesMock.mockImplementation(async () => {
      storeSnapshot.preferences = {
        language: "",
        locale: "fr-FR",
        theme: "dark",
        display_mode: "table",
      };
    });

    render(
      <Providers>
        <div>child</div>
      </Providers>,
    );

    // Wait for init to complete
    await waitFor(() => {
      expect(initMock).toHaveBeenCalled();
    });

    // setLanguage should NOT be called for empty/falsy language
    expect(setLanguageMock).not.toHaveBeenCalled();
  });

  it("renders children", async () => {
    const { findByText } = render(
      <Providers>
        <div>child content</div>
      </Providers>,
    );

    await expect(findByText("child content")).resolves.toBeInTheDocument();
  });
});

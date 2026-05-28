import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

// ── Mocks (vi.hoisted so factories can reference them) ────────────────────────

const { setLanguageMock, getLanguageMock, savePreferencesMock, logoutMock } = vi.hoisted(() => ({
  setLanguageMock: vi.fn(),
  getLanguageMock: vi.fn(() => "en"),
  savePreferencesMock: vi.fn().mockResolvedValue(undefined),
  logoutMock: vi.fn(),
}));

vi.mock("@/i18n/i18n", () => ({
  setLanguage: setLanguageMock,
  getLanguage: getLanguageMock,
  default: {},
}));

let mockAuthState: {
  user: unknown;
  savePreferences: typeof savePreferencesMock;
  logout: typeof logoutMock;
} = {
  user: {
    email: "test@test.com",
    first_name: "T",
    last_name: "U",
    locale: "en-US",
  },
  savePreferences: savePreferencesMock,
  logout: logoutMock,
};

const useAuthStoreMock = vi.hoisted(() =>
  Object.assign(
    vi.fn((s?: (state: typeof mockAuthState) => unknown) =>
      s ? s(mockAuthState) : mockAuthState,
    ),
    { getState: () => mockAuthState },
  ),
);

vi.mock("@/stores/authStore", () => ({
  useAuthStore: useAuthStoreMock,
}));

vi.mock("@/stores/themeStore", () => ({
  useThemeStore: (s?: (state: { mode: string; setMode: ReturnType<typeof vi.fn> }) => unknown) => {
    const state = { mode: "system", setMode: vi.fn() };
    return s ? s(state) : state;
  },
}));

// Must import after mocks
import TopBar from "@/components/layout/TopBar";

// ── Helpers ──────────────────────────────────────────────────────────────────

function renderTopBar() {
  return render(
    <MemoryRouter>
      <TopBar onToggleSidebar={vi.fn()} />
    </MemoryRouter>,
  );
}

// ── Tests ────────────────────────────────────────────────────────────────────

describe("TopBar", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getLanguageMock.mockReturnValue("en");
    mockAuthState = {
      user: {
        email: "test@test.com",
        first_name: "T",
        last_name: "U",
        locale: "en-US",
      },
      savePreferences: savePreferencesMock,
      logout: logoutMock,
    };
  });

  describe("toggleLanguage", () => {
    it("calls setLanguage with the toggled value", () => {
      renderTopBar();
      fireEvent.click(screen.getByTestId("language-toggle"));
      expect(setLanguageMock).toHaveBeenCalledWith("fr");
    });

    it("calls savePreferences with { language } key, not { locale } (Bug 3 regression)", () => {
      renderTopBar();
      fireEvent.click(screen.getByTestId("language-toggle"));

      expect(savePreferencesMock).toHaveBeenCalledTimes(1);
      const arg = savePreferencesMock.mock.calls[0]![0];
      expect(arg).toEqual({ language: "fr" });
      // Regression: must NOT pass locale key
      expect(arg).not.toHaveProperty("locale");
    });

    it("does not call savePreferences when no user is logged in", () => {
      mockAuthState.user = null;
      renderTopBar();
      fireEvent.click(screen.getByTestId("language-toggle"));
      expect(setLanguageMock).toHaveBeenCalledWith("fr");
      expect(savePreferencesMock).not.toHaveBeenCalled();
    });

    it("displays the current language code", () => {
      getLanguageMock.mockReturnValue("en");
      renderTopBar();
      expect(screen.getByTestId("language-toggle")).toHaveTextContent("EN");
    });
  });
});

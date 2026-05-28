import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import i18n from "@/i18n/i18n";

const mockSavePreferences = vi.fn();
const mockLogout = vi.fn();

const mockUser = {
  id: "u1", email: "x@y.z", first_name: "X", last_name: "Y",
  role: "authenticated", status: "active", email_verified: true,
  locale: "en-US", created_at: "2024-01-01T00:00:00Z",
};

vi.mock("@/stores/authStore", () => ({
  useAuthStore: Object.assign(
    vi.fn((selector?: (s: unknown) => unknown) => {
      const store = {
        user: mockUser,
        preferences: { language: "en", locale: "en-US", theme: "light", display_mode: "table" },
        savePreferences: mockSavePreferences,
        logout: mockLogout,
        isLoading: false,
        isInitialized: true,
      };
      return typeof selector === "function" ? selector(store) : store;
    }),
    { getState: vi.fn(() => ({
      user: mockUser,
      preferences: { language: "en", locale: "en-US", theme: "light", display_mode: "table" },
      savePreferences: mockSavePreferences,
    })), setState: vi.fn() },
  ),
}));

vi.mock("@/stores/themeStore", () => ({
  useThemeStore: vi.fn(() => ({ mode: "system", setMode: vi.fn() })),
}));

import TopBar from "@/components/layout/TopBar";

describe("TopBar — bug #214 #3 (toggleLanguage saves under language key)", () => {
  beforeEach(async () => {
    await i18n.changeLanguage("en");
    mockSavePreferences.mockReset();
    mockSavePreferences.mockResolvedValue({});
  });

  it("calls savePreferences with { language: ... }, NOT { locale: ... }", async () => {
    render(
      <MemoryRouter>
        <TopBar onToggleSidebar={() => {}} showHamburger={false} />
      </MemoryRouter>,
    );

    const langBtn = screen.getByTestId("language-toggle");
    fireEvent.click(langBtn);

    await waitFor(() => {
      expect(mockSavePreferences).toHaveBeenCalled();
      const callArg = mockSavePreferences.mock.calls[0]?.[0];
      expect(callArg).toHaveProperty("language");
      expect(callArg).not.toHaveProperty("locale");
    });
  });
});

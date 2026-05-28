import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import i18n from "@/i18n/i18n";

const mockSetLanguage = vi.fn();
vi.mock("@/i18n/i18n", async () => {
  const actual = await vi.importActual<typeof import("@/i18n/i18n")>("@/i18n/i18n");
  return { ...actual, setLanguage: mockSetLanguage, getLanguage: () => "en" };
});

const mockSavePreferences = vi.fn();
const mockLoadPreferences = vi.fn(async () => {});
const mockUpdateProfile = vi.fn();

vi.mock("@/stores/authStore", () => ({
  useAuthStore: Object.assign(
    vi.fn((selector?: (s: unknown) => unknown) => {
      const store = {
        user: {
          id: "u1", email: "x@y.z", first_name: "Test", last_name: "User",
          role: "authenticated", status: "active", email_verified: true,
          locale: "en-US", created_at: "2024-01-01T00:00:00Z",
        },
        preferences: { language: "en", locale: "en-US", theme: "light", display_mode: "table" },
        isLoading: false,
        isInitialized: true,
        savePreferences: mockSavePreferences,
        loadPreferences: mockLoadPreferences,
        updateProfile: mockUpdateProfile,
      };
      return typeof selector === "function" ? selector(store) : store;
    }),
    { getState: vi.fn(), setState: vi.fn() },
  ),
}));

vi.mock("@/stores/themeStore", () => ({
  useThemeStore: vi.fn(() => ({ mode: "light", setMode: vi.fn() })),
}));

import ProfilePage from "@/pages/account/ProfilePage";

describe("ProfilePage — bug #214 #2 (saveLanguage calls i18n.setLanguage)", () => {
  beforeEach(async () => {
    await i18n.changeLanguage("en");
    mockSetLanguage.mockReset();
    mockSavePreferences.mockReset();
    mockLoadPreferences.mockReset();
    mockLoadPreferences.mockResolvedValue(undefined);
    mockSavePreferences.mockResolvedValue({});
    mockUpdateProfile.mockResolvedValue({});
  });

  afterEach(async () => {
    await i18n.changeLanguage("en");
  });

  it("calls i18n.setLanguage when the language dropdown changes", async () => {
    render(
      <MemoryRouter>
        <ProfilePage />
      </MemoryRouter>,
    );

    // Open the language select (Radix renders a button trigger inside a <label>)
    const trigger = screen.getByRole("button", { name: /language/i });
    fireEvent.click(trigger);

    // Select the French option. The option is rendered in a Radix portal.
    // Its label is "Français" (t("account.locale_fr")).
    await waitFor(() => {
      const frOption = screen.getByRole("option", { name: "Français" });
      fireEvent.click(frOption);
    });

    await waitFor(() => {
      expect(mockSetLanguage).toHaveBeenCalledWith("fr");
      expect(mockSavePreferences).toHaveBeenCalledWith({ language: "fr" });
    });
  });
});

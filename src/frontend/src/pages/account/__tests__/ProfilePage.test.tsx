import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { mockSetLanguage } = vi.hoisted(() => ({
  mockSetLanguage: vi.fn(),
}));
vi.mock("@/i18n/i18n", async () => {
  const actual = await vi.importActual<typeof import("@/i18n/i18n")>("@/i18n/i18n");
  return { ...actual, setLanguage: mockSetLanguage, getLanguage: () => "en" };
});

import i18n from "@/i18n/i18n";

const mockSavePreferences = vi.fn();
const mockLoadPreferences = vi.fn(async () => {});
const mockUpdateProfile = vi.fn();

vi.mock("@/stores/authStore", () => ({
  useAuthStore: Object.assign(
    vi.fn((selector?: (s: unknown) => unknown) => {
      const store = {
        user: {
          id: "u1",
          email: "x@y.z",
          first_name: "Test",
          last_name: "User",
          role: "authenticated",
          status: "active",
          email_verified: true,
          locale: "en-US",
          created_at: "2024-01-01T00:00:00Z",
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

// Isolate from TopBar — PageLayout renders children directly
vi.mock("@/components/layout/PageLayout", () => ({
  default: ({ children }: { children: React.ReactNode }) => <>{children}</>,
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

    // The Radix Select trigger has role="combobox" and is inside a <label>
    // with text "Language" (t("account.language")).
    const trigger = screen.getByRole("combobox", { name: /language/i });
    fireEvent.click(trigger);

    // Select "Français" from the Radix dropdown (rendered in a portal)
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

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { mockSetLanguage, mockGetLanguage } = vi.hoisted(() => ({
  mockSetLanguage: vi.fn(),
  mockGetLanguage: vi.fn(() => "en"),
}));
vi.mock("@/i18n/i18n", async () => {
  const actual = await vi.importActual<typeof import("@/i18n/i18n")>("@/i18n/i18n");
  return { ...actual, setLanguage: mockSetLanguage, getLanguage: mockGetLanguage };
});

import i18n from "@/i18n/i18n";

const mockSavePreferences = vi.fn();
const mockLoadPreferences = vi.fn(async () => {});
const mockUpdateProfile = vi.fn();

const { mockStoreUser, mockStorePreferences } = vi.hoisted(() => ({
  mockStoreUser: {
    id: "u1",
    email: "x@y.z",
    first_name: "Test",
    last_name: "User",
    role: "authenticated" as const,
    status: "active" as const,
    email_verified: true,
    locale: "en-US",
    created_at: "2024-01-01T00:00:00Z",
  },
  mockStorePreferences: { language: "en", locale: "en-US", theme: "light" as const, display_mode: "table" as const },
}));

vi.mock("@/stores/authStore", () => ({
  useAuthStore: Object.assign(
    vi.fn((selector?: (s: unknown) => unknown) => {
      const store = {
        user: mockStoreUser,
        preferences: mockStorePreferences,
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
    mockGetLanguage.mockReturnValue("en");
    Object.assign(mockStoreUser, {
      id: "u1",
      email: "x@y.z",
      first_name: "Test",
      last_name: "User",
      role: "authenticated",
      status: "active",
      email_verified: true,
      locale: "en-US",
      created_at: "2024-01-01T00:00:00Z",
    });
    Object.assign(mockStorePreferences, { language: "en", locale: "en-US", theme: "light", display_mode: "table" });
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

describe("ProfilePage — issue #294 (missing preference keys fallback)", () => {
  beforeEach(async () => {
    await i18n.changeLanguage("fr");
    mockGetLanguage.mockReturnValue("fr");
    Object.assign(mockStoreUser, {
      id: "u1", email: "x@y.z", first_name: "Test", last_name: "User",
      role: "authenticated", status: "active", email_verified: true,
      locale: "fr-CH", created_at: "2024-01-01T00:00:00Z",
    });
    Object.assign(mockStorePreferences, { theme: "light", display_mode: "table" });
    // simulate missing language and locale keys
    delete (mockStorePreferences as Record<string, unknown>).language;
    delete (mockStorePreferences as Record<string, unknown>).locale;
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

  it("falls back to i18n language when preferences.language is missing", async () => {
    render(
      <MemoryRouter>
        <ProfilePage />
      </MemoryRouter>,
    );

    // The language Select should show "Français" (i18n language "fr")
    // not "English" (hardcoded "en" fallback from old code)
    await waitFor(() => {
      const trigger = screen.getByLabelText(/langue/i);
      expect(trigger).toHaveTextContent("Français");
    });
  });

  it("falls back to i18n language when preferences.locale is missing", async () => {
    // Simulate the reported bug: DB has no locale preference,
    // and the login response defaulted locale to "en-US"
    mockStoreUser.locale = "en-US";

    render(
      <MemoryRouter>
        <ProfilePage />
      </MemoryRouter>,
    );

    // The locale Select should derive from i18n language (fr → fr-FR),
    // not hardcoded "en-US" from the old fallback chain
    await waitFor(() => {
      const trigger = screen.getByLabelText(/locale|paramètres régionaux/i);
      // "fr-FR" is displayed as "français (France)" when language is "fr"
      expect(trigger).toHaveTextContent("français (France)");
    });
  });

  it("uses preferences values when both language and locale are present", async () => {
    // Restore preferences for this test
    Object.assign(mockStorePreferences, { language: "fr", locale: "fr-CH" });

    render(
      <MemoryRouter>
        <ProfilePage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      const langTrigger = screen.getByLabelText(/langue/i);
      expect(langTrigger).toHaveTextContent("Français");
    });

    await waitFor(() => {
      const locTrigger = screen.getByLabelText(/locale|paramètres régionaux/i);
      expect(locTrigger).toHaveTextContent("français (Suisse)");
    });
  });
});

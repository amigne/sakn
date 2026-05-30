import { beforeEach, describe, expect, it, vi } from "vitest";

// ── Mocks ────────────────────────────────────────────────────────────────────

const mockLogin = vi.fn();
const mockGetPreferences = vi.fn();
const mockUpdatePreferences = vi.fn();

vi.mock("@/services/authService", () => ({
  login: (...args: unknown[]) => mockLogin(...args),
  fetchCurrentUser: vi.fn(),
  logout: vi.fn(),
  register: vi.fn(),
  verifyEmail: vi.fn(),
  resendVerification: vi.fn(),
  requestPasswordReset: vi.fn(),
  resetPassword: vi.fn(),
  updateProfile: vi.fn(),
}));

vi.mock("@/services/preferencesService", () => ({
  getPreferences: () => mockGetPreferences(),
  updatePreferences: (...args: unknown[]) => mockUpdatePreferences(...args),
}));

vi.mock("@/stores/themeStore", () => ({
  useThemeStore: {
    getState: () => ({ setMode: vi.fn() }),
  },
}));

// NOTE: @/i18n/i18n is intentionally NOT mocked. login() imports setLanguage
// statically and calls it after loading preferences; the real implementation
// is a harmless no-throw side effect here, so we let it run. The i18n
// restoration after login is covered explicitly by:
// - ProfilePage.test.tsx (setLanguage applied on language change)
// - Providers.test.tsx (AuthInitializer applies language)
// - E2E profile-language.spec.ts (full login → profile flow)

import { useAuthStore } from "@/stores/authStore";

describe("authStore.login — loads preferences after login (#294)", () => {
  beforeEach(() => {
    useAuthStore.setState({
      user: null,
      preferences: null,
      isLoading: false,
      isInitialized: false,
    });
    mockLogin.mockReset();
    mockGetPreferences.mockReset();
    mockUpdatePreferences.mockReset();
  });

  it("loads language and locale preferences into store after successful login", async () => {
    mockLogin.mockResolvedValue({
      user: {
        id: "u1",
        email: "a@b.c",
        first_name: "Test",
        last_name: "User",
        role: "authenticated",
        status: "active",
        email_verified: true,
        locale: "fr-CH",
      },
    });
    mockGetPreferences.mockResolvedValue({
      preferences: { language: "fr", locale: "fr-CH", theme: "light", display_mode: "table" },
    });

    await useAuthStore.getState().login("a@b.c", "pw");

    const prefs = useAuthStore.getState().preferences;
    expect(prefs?.language).toBe("fr");
    expect(prefs?.locale).toBe("fr-CH");
  });

  it("sets user from login response before loading preferences", async () => {
    mockLogin.mockResolvedValue({
      user: {
        id: "u1",
        email: "a@b.c",
        first_name: "Test",
        last_name: "User",
        role: "authenticated",
        status: "active",
        email_verified: true,
        locale: "fr-CH",
      },
    });
    mockGetPreferences.mockResolvedValue({
      preferences: { language: "fr", locale: "fr-CH", theme: "light", display_mode: "table" },
    });

    await useAuthStore.getState().login("a@b.c", "pw");

    const user = useAuthStore.getState().user;
    expect(user?.email).toBe("a@b.c");
    expect(user?.locale).toBe("fr-CH");
  });
});

describe("authStore.savePreferences — throws on service failure (#294 regression)", () => {
  beforeEach(() => {
    useAuthStore.setState({
      preferences: { language: "en", locale: "en-US", theme: "light", display_mode: "table" },
    });
    mockUpdatePreferences.mockReset();
  });

  it("rejects when preferencesService.updatePreferences rejects", async () => {
    mockUpdatePreferences.mockRejectedValue(new Error("API error"));

    await expect(useAuthStore.getState().savePreferences({ language: "fr" })).rejects.toThrow("API error");
  });

  it("updates store preferences on success", async () => {
    mockUpdatePreferences.mockResolvedValue({
      preferences: { language: "fr", locale: "fr-CH", theme: "light", display_mode: "table" },
    });

    await useAuthStore.getState().savePreferences({ language: "fr", locale: "fr-CH" });

    const prefs = useAuthStore.getState().preferences;
    expect(prefs?.language).toBe("fr");
    expect(prefs?.locale).toBe("fr-CH");
  });
});

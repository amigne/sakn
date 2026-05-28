import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

// ── Mocks ────────────────────────────────────────────────────────────────────

const { setLanguageMock, getLanguageMock, savePreferencesMock, loadPreferencesMock, updateProfileMock } = vi.hoisted(
  () => ({
    setLanguageMock: vi.fn(),
    getLanguageMock: vi.fn(() => "en"),
    savePreferencesMock: vi.fn().mockResolvedValue(undefined),
    loadPreferencesMock: vi.fn().mockResolvedValue(undefined),
    updateProfileMock: vi.fn().mockResolvedValue(undefined),
  }),
);

vi.mock("@/i18n/i18n", () => ({
  setLanguage: setLanguageMock,
  getLanguage: getLanguageMock,
  default: {
    language: "en",
    changeLanguage: vi.fn(),
  },
}));

let mockAuthState: Record<string, unknown> = {
  user: { email: "test@test.com", first_name: "Test", last_name: "User", locale: "en-US" },
  preferences: null,
  savePreferences: savePreferencesMock,
  loadPreferences: loadPreferencesMock,
  updateProfile: updateProfileMock,
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

vi.mock("@/services/api", () => ({
  ApiError: class ApiError extends Error {
    status: number;
    constructor(message: string, status: number) {
      super(message);
      this.status = status;
    }
  },
}));

vi.mock("@/components/layout/PageLayout", () => ({
  default: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

vi.mock("@/components/ui", () => ({
  Select: ({
    options,
    value,
    onChange,
    ariaLabel,
  }: {
    options: { value: string; label: string }[];
    value?: string;
    defaultValue?: string;
    onChange?: (v: string) => void;
    placeholder?: string;
    disabled?: boolean;
    error?: string;
    className?: string;
    ariaLabel?: string;
  }) => (
    <select value={value} onChange={(e) => onChange?.(e.target.value)} aria-label={ariaLabel}>
      {options.map((o) => (
        <option key={o.value} value={o.value}>
          {o.label}
        </option>
      ))}
    </select>
  ),
  RadioButton: ({
    label,
    checked,
    onChange,
    name,
  }: {
    name: string;
    checked: boolean;
    onChange: () => void;
    label: string;
  }) => (
    <label>
      <input type="radio" name={name} checked={checked} onChange={onChange} />
      {label}
    </label>
  ),
  TextInput: ({
    value,
    disabled,
    type,
    onChange,
  }: {
    type?: string;
    value?: string;
    disabled?: boolean;
    onChange?: (e: React.ChangeEvent<HTMLInputElement>) => void;
  }) => <input type={type || "text"} value={value || ""} disabled={disabled} onChange={onChange} />,
}));

vi.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (k: string) => k }),
  Trans: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

// Must import after mocks
import ProfilePage from "@/pages/account/ProfilePage";

// ── Helpers ──────────────────────────────────────────────────────────────────

function renderPage() {
  return render(
    <MemoryRouter>
      <ProfilePage />
    </MemoryRouter>,
  );
}

// ── Tests ────────────────────────────────────────────────────────────────────

describe("ProfilePage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getLanguageMock.mockReturnValue("en");
    mockAuthState = {
      user: { email: "test@test.com", first_name: "Test", last_name: "User", locale: "en-US" },
      preferences: null,
      savePreferences: savePreferencesMock,
      loadPreferences: loadPreferencesMock,
      updateProfile: updateProfileMock,
    };
  });

  describe("saveLanguage (Bug 2 regression)", () => {
    it("calls i18n.setLanguage when the language dropdown changes", async () => {
      renderPage();

      const langSelect = screen.getByRole("combobox", { name: "account.language" });
      fireEvent.change(langSelect, { target: { value: "fr" } });

      // saveLanguage uses dynamic import → microtask; wait for it
      await waitFor(() => {
        expect(setLanguageMock).toHaveBeenCalledWith("fr");
      });
    });

    it("persists the language preference to the server", async () => {
      renderPage();

      const langSelect = screen.getByRole("combobox", { name: "account.language" });
      fireEvent.change(langSelect, { target: { value: "fr" } });

      await waitFor(() => {
        expect(savePreferencesMock).toHaveBeenCalledWith({ language: "fr" });
      });
    });

    it("has initial language value from getLanguage()", () => {
      getLanguageMock.mockReturnValue("en");
      renderPage();

      const langSelect = screen.getByRole("combobox", { name: "account.language" }) as HTMLSelectElement;
      expect(langSelect.value).toBe("en");
    });
  });
});

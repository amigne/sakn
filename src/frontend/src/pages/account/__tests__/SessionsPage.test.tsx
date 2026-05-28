import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

// ── Mocks ────────────────────────────────────────────────────────────────────

const { mockListSessions, toLocaleStringSpy } = vi.hoisted(() => ({
  mockListSessions: vi.fn(),
  toLocaleStringSpy: vi.fn((locale?: string) => `formatted[${locale ?? "default"}]`),
}));

vi.mock("@/services/sessionService", () => ({
  listSessions: () => mockListSessions(),
  revokeSession: vi.fn(),
}));

let mockAuthState: {
  user: { locale: string } | null;
  preferences: { locale: string; language: string; theme: string; display_mode: string } | null;
} = {
  user: { locale: "en-GB" },
  preferences: null,
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

vi.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (k: string) => k }),
}));

vi.mock("@/components/layout/PageLayout", () => ({
  default: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

vi.mock("@/components/ui", () => ({
  Badge: ({ children }: { children: React.ReactNode; variant?: string }) => <span>{children}</span>,
  Button: ({ children, onClick }: { children: React.ReactNode; onClick?: () => void; variant?: string }) => (
    <button onClick={onClick}>{children}</button>
  ),
  Modal: ({
    children,
    open,
    footer,
  }: {
    children: React.ReactNode;
    open: boolean;
    onClose?: () => void;
    title?: string;
    footer?: React.ReactNode;
  }) => (open ? <div role="dialog">{children}{footer}</div> : null),
}));

vi.spyOn(Date.prototype, "toLocaleString").mockImplementation(toLocaleStringSpy);

// Must import after mocks
import SessionsPage from "@/pages/account/SessionsPage";

// ── Helpers ──────────────────────────────────────────────────────────────────

function renderPage() {
  return render(
    <MemoryRouter>
      <SessionsPage />
    </MemoryRouter>,
  );
}

// ── Tests ────────────────────────────────────────────────────────────────────

describe("SessionsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockAuthState = {
      user: { locale: "en-GB" },
      preferences: null,
    };
  });

  describe("formatDate (Bug 4 regression)", () => {
    it("passes user.locale to toLocaleString when preferences.locale is not set", async () => {
      mockListSessions.mockResolvedValue({
        sessions: [
          {
            id: "1",
            ip_address: "192.168.1.1",
            user_agent: "Firefox",
            last_activity_at: "2024-01-15T10:30:00Z",
            current: true,
          },
        ],
      });

      renderPage();
      await waitFor(() => {
        expect(screen.getByText("192.168.1.1")).toBeInTheDocument();
      });

      // Regression: toLocaleString must receive a locale argument (Bug 4)
      const dateCalls = toLocaleStringSpy.mock.calls.filter((c) => c.length > 0);
      expect(dateCalls.length).toBeGreaterThan(0);
      expect(dateCalls[0]![0]).toBe("en-GB");
    });

    it("prefers preferences.locale over user.locale", async () => {
      mockAuthState.preferences = {
        locale: "fr-FR",
        language: "fr",
        theme: "light",
        display_mode: "table",
      };
      mockListSessions.mockResolvedValue({
        sessions: [
          {
            id: "1",
            ip_address: "10.0.0.1",
            user_agent: "Chrome",
            last_activity_at: "2024-06-01T12:00:00Z",
            current: true,
          },
        ],
      });

      renderPage();
      await waitFor(() => {
        expect(screen.getByText("10.0.0.1")).toBeInTheDocument();
      });

      const dateCalls = toLocaleStringSpy.mock.calls.filter((c) => c.length > 0);
      expect(dateCalls.length).toBeGreaterThan(0);
      expect(dateCalls[0]![0]).toBe("fr-FR");
    });

    it("renders date strings without crashing when no user locale is available", async () => {
      mockAuthState.user = null;
      mockListSessions.mockResolvedValue({
        sessions: [
          {
            id: "1",
            ip_address: "1.2.3.4",
            user_agent: "Safari",
            last_activity_at: "2024-03-01T08:00:00Z",
            current: true,
          },
        ],
      });

      renderPage();
      await waitFor(() => {
        expect(screen.getByText("1.2.3.4")).toBeInTheDocument();
      });

      // Page should render without crash (userLocale is null/undefined)
      expect(screen.getByText("1.2.3.4")).toBeInTheDocument();
    });
  });
});

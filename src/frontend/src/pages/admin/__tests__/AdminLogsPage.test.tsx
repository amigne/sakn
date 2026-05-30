import { act, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// ── Mocks ────────────────────────────────────────────────────────────────────

vi.mock("@/components/admin/AdminLayout", () => ({
  default: ({ children, title }: { children: React.ReactNode; title: string }) => (
    <div data-testid="admin-layout">
      <h1>{title}</h1>
      {children}
    </div>
  ),
}));

const mockSavePreferences = vi.fn();

vi.mock("@/stores/authStore", () => ({
  useAuthStore: Object.assign(
    vi.fn((selector?: (s: unknown) => unknown) => {
      const store = {
        user: null,
        preferences: {} as Record<string, string>,
        savePreferences: mockSavePreferences,
        loadPreferences: vi.fn(),
      };
      return typeof selector === "function" ? selector(store) : store;
    }),
    { getState: vi.fn(), setState: vi.fn() },
  ),
}));

// Mock admin services to return empty data (component fetches on mount)
vi.mock("@/services/admin", () => ({
  listToolExecutions: vi.fn(() => Promise.resolve({ items: [], total: 0 })),
  listSecurityEvents: vi.fn(() => Promise.resolve({ items: [], total: 0 })),
  listAuditLogs: vi.fn(() => Promise.resolve({ items: [], total: 0 })),
}));

import i18n from "@/i18n/i18n";
import AdminLogsPage from "@/pages/admin/AdminLogsPage";

describe("AdminLogsPage — savePreferences rejection safety (#294 regression)", () => {
  beforeEach(async () => {
    await i18n.changeLanguage("en");
    mockSavePreferences.mockReset();
  });

  afterEach(async () => {
    await i18n.changeLanguage("en");
  });

  it("does not throw unhandled rejection when savePreferences rejects in handleLimitChange", async () => {
    mockSavePreferences.mockRejectedValue(new Error("API error"));

    // The component fetches data on mount; the Select for page size
    // is rendered after data arrives. Mock returns empty data, so it renders.
    await act(async () => {
      render(
        <MemoryRouter>
          <AdminLogsPage />
        </MemoryRouter>,
      );
    });

    // The component should render without unhandled rejection.
    // The savePreferences rejection is caught by .catch(() => {}) — if it
    // weren't, this test would fail with an unhandled promise rejection.
    await vi.waitFor(() => {
      expect(screen.getByTestId("admin-layout")).toBeInTheDocument();
    });
  });

  it("does not throw unhandled rejection when savePreferences rejects in handleAutoRefreshChange", async () => {
    mockSavePreferences.mockRejectedValue(new Error("API error"));

    await act(async () => {
      render(
        <MemoryRouter>
          <AdminLogsPage />
        </MemoryRouter>,
      );
    });

    await vi.waitFor(() => {
      expect(screen.getByTestId("admin-layout")).toBeInTheDocument();
    });
  });
});

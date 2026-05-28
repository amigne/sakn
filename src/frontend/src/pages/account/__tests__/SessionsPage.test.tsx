import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import i18n from "@/i18n/i18n";

vi.mock("@/services/sessionService", () => ({
  listSessions: vi.fn(() =>
    Promise.resolve({
      sessions: [
        {
          id: "s1",
          ip_address: "1.2.3.4",
          user_agent: "Mozilla/5.0",
          created_at: "2024-06-15T14:00:00Z",
          last_activity_at: "2024-06-15T15:30:00Z",
          current: true,
        },
      ],
    }),
  ),
  revokeSession: vi.fn(),
}));

vi.mock("@/stores/authStore", () => ({
  useAuthStore: Object.assign(
    vi.fn((selector?: (s: unknown) => unknown) => {
      const store = {
        user: {
          id: "u1",
          email: "x@y.z",
          first_name: "X",
          last_name: "Y",
          role: "authenticated",
          status: "active",
          email_verified: true,
          locale: "fr-FR",
          created_at: "2024-01-01T00:00:00Z",
        },
        preferences: { language: "fr", locale: "fr-FR", theme: "light", display_mode: "table" },
      };
      return typeof selector === "function" ? selector(store) : store;
    }),
    { getState: vi.fn(), setState: vi.fn() },
  ),
}));

import SessionsPage from "@/pages/account/SessionsPage";

describe("SessionsPage — bug #214 #4 (formatDate uses user locale)", () => {
  beforeEach(async () => {
    await i18n.changeLanguage("en");
  });

  it("formats dates using the user locale (fr-FR), not browser default", async () => {
    render(
      <MemoryRouter>
        <SessionsPage />
      </MemoryRouter>,
    );

    // The date should appear formatted for fr-FR locale
    const expectedFr = new Date("2024-06-15T15:30:00Z").toLocaleString("fr-FR");
    await waitFor(() => {
      expect(screen.getByText(expectedFr)).toBeInTheDocument();
    });
  });
});

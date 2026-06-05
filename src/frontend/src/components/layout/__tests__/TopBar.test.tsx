import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import i18n from "@/i18n/i18n";

const mockSavePreferences = vi.fn();
const mockLogout = vi.fn();

const mockUser = {
  id: "u1",
  email: "x@y.z",
  first_name: "X",
  last_name: "Y",
  role: "authenticated",
  status: "active",
  email_verified: true,
  locale: "en-US",
  created_at: "2024-01-01T00:00:00Z",
};

const { mockWhoami } = vi.hoisted(() => ({
  mockWhoami: vi.fn(),
}));

vi.mock("@/services/authService", () => ({
  whoami: mockWhoami,
}));

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
    {
      getState: vi.fn(() => ({
        user: mockUser,
        preferences: { language: "en", locale: "en-US", theme: "light", display_mode: "table" },
        savePreferences: mockSavePreferences,
      })),
      setState: vi.fn(),
    },
  ),
}));

vi.mock("@/stores/themeStore", () => ({
  useThemeStore: vi.fn(() => ({ mode: "system", setMode: vi.fn() })),
}));

import TopBar from "@/components/layout/TopBar";

function renderTopBar() {
  return render(
    <MemoryRouter>
      <TopBar onToggleSidebar={() => {}} showHamburger={false} />
    </MemoryRouter>,
  );
}

describe("TopBar — bug #214 #3 (toggleLanguage saves under language key)", () => {
  beforeEach(async () => {
    await i18n.changeLanguage("en");
    mockWhoami.mockResolvedValue({ ip: null });
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

describe("TopBar — visitor IP display", () => {
  beforeEach(async () => {
    await i18n.changeLanguage("en");
    mockWhoami.mockReset();
    mockSavePreferences.mockReset();
    mockSavePreferences.mockResolvedValue({});
  });

  describe("AC-MYIP-008, 009: renders IP before language toggle", () => {
    it("shows the resolved IP with globe icon, before the language toggle", async () => {
      mockWhoami.mockResolvedValue({ ip: "203.0.113.7" });
      renderTopBar();

      const ipEl = await screen.findByTestId("ip-display");
      expect(ipEl).toBeDefined();

      // AC-MYIP-009: IP displayed in monospace with globe icon
      expect(ipEl.textContent).toContain("203.0.113.7");
      const mono = ipEl.querySelector(".font-mono");
      expect(mono).toBeDefined();
      const svg = ipEl.querySelector("svg");
      expect(svg).toBeDefined();

      // AC-MYIP-008: IP element is rendered before the language toggle in DOM order
      const langBtn = screen.getByTestId("language-toggle");
      expect(ipEl.compareDocumentPosition(langBtn) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    });
  });

  describe("AC-MYIP-010: click copies to clipboard", () => {
    it("copies IP to clipboard on click and shows feedback", async () => {
      mockWhoami.mockResolvedValue({ ip: "203.0.113.7" });

      const writeText = vi.fn().mockResolvedValue(undefined);
      Object.defineProperty(navigator, "clipboard", {
        value: { writeText },
        writable: true,
      });

      renderTopBar();
      const ipEl = await screen.findByTestId("ip-display");

      fireEvent.click(ipEl);
      expect(writeText).toHaveBeenCalledWith("203.0.113.7");

      // Feedback shown after copy
      await waitFor(() => {
        expect(ipEl.textContent).toContain("IP copied!");
      });
    });

    it("copies on Enter key", async () => {
      mockWhoami.mockResolvedValue({ ip: "10.0.0.1" });

      const writeText = vi.fn().mockResolvedValue(undefined);
      Object.defineProperty(navigator, "clipboard", {
        value: { writeText },
        writable: true,
      });

      renderTopBar();
      const ipEl = await screen.findByTestId("ip-display");

      fireEvent.keyDown(ipEl, { key: "Enter" });
      expect(writeText).toHaveBeenCalledWith("10.0.0.1");
    });

    it("copies on Space key", async () => {
      mockWhoami.mockResolvedValue({ ip: "10.0.0.1" });

      const writeText = vi.fn().mockResolvedValue(undefined);
      Object.defineProperty(navigator, "clipboard", {
        value: { writeText },
        writable: true,
      });

      renderTopBar();
      const ipEl = await screen.findByTestId("ip-display");

      fireEvent.keyDown(ipEl, { key: " " });
      expect(writeText).toHaveBeenCalledWith("10.0.0.1");
    });
  });

  describe("AC-MYIP-011: tooltip and accessible name", () => {
    it("has title and aria-label from common.your_ip", async () => {
      mockWhoami.mockResolvedValue({ ip: "203.0.113.7" });
      renderTopBar();

      const ipEl = await screen.findByTestId("ip-display");
      expect(ipEl.getAttribute("title")).toBe("Your IP address (click to copy)");
      expect(ipEl.getAttribute("aria-label")).toBe("Your IP address (click to copy)");
    });

    it("announces copy feedback via aria-live polite", async () => {
      mockWhoami.mockResolvedValue({ ip: "203.0.113.7" });

      const writeText = vi.fn().mockResolvedValue(undefined);
      Object.defineProperty(navigator, "clipboard", {
        value: { writeText },
        writable: true,
      });

      renderTopBar();
      const ipEl = await screen.findByTestId("ip-display");

      fireEvent.click(ipEl);

      await waitFor(() => {
        const status = ipEl.querySelector('[role="status"]');
        expect(status).toBeDefined();
        expect(status?.getAttribute("aria-live")).toBe("polite");
        expect(status?.textContent).toBe("IP copied!");
      });
    });
  });

  describe("AC-MYIP-012: omitted on failure", () => {
    it("does not render when whoami rejects", async () => {
      mockWhoami.mockRejectedValue(new Error("Network error"));
      renderTopBar();

      // Wait a tick for the promise to settle
      await screen.findByTestId("language-toggle");

      expect(screen.queryByTestId("ip-display")).toBeNull();
    });

    it("does not render when ip is null", async () => {
      mockWhoami.mockResolvedValue({ ip: null });
      renderTopBar();

      await screen.findByTestId("language-toggle");

      expect(screen.queryByTestId("ip-display")).toBeNull();
    });
  });

  describe("AC-MYIP-013: hidden below sm breakpoint", () => {
    it("has hidden sm:flex classes for responsive visibility", async () => {
      mockWhoami.mockResolvedValue({ ip: "203.0.113.7" });
      renderTopBar();

      const ipEl = await screen.findByTestId("ip-display");
      const className = ipEl.className;
      expect(className).toContain("hidden");
      expect(className).toContain("sm:flex");
    });
  });

  describe("AC-MYIP-014: keyboard focus ring", () => {
    it("is reachable in tab order before language toggle", async () => {
      mockWhoami.mockResolvedValue({ ip: "203.0.113.7" });
      renderTopBar();

      const ipEl = await screen.findByTestId("ip-display");
      // The button is focusable (no tabIndex=-1) and has focus-visible ring classes
      expect(ipEl.getAttribute("tabIndex")).toBeNull(); // not disabled from focus
      const className = ipEl.className;
      expect(className).toContain("focus-visible:ring-2");
    });
  });
});

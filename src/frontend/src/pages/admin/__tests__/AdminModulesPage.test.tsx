import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import i18n from "@/i18n/i18n";
import AdminModulesPage from "@/pages/admin/AdminModulesPage";
import type { AccessPermission, ToolModule } from "@/types/admin";
import type { UserRole } from "@/types/user";

// ── Mocks ────────────────────────────────────────────────────────────────────

vi.mock("@/components/admin/AdminLayout", () => ({
  default: ({ children, title }: { children: React.ReactNode; title: string }) => (
    <div data-testid="admin-layout">
      <h1>{title}</h1>
      {children}
    </div>
  ),
}));

const mockListModules = vi.fn();
const mockListRolePermissions = vi.fn();
const mockUpdateModule = vi.fn();
const mockUpdateRolePermissions = vi.fn();

vi.mock("@/services/admin", () => ({
  listModules: () => mockListModules(),
  listRolePermissions: () => mockListRolePermissions(),
  updateModule: (...args: unknown[]) => mockUpdateModule(...args),
  updateRolePermissions: (...args: unknown[]) => mockUpdateRolePermissions(...args),
  createDnsServer: vi.fn(),
  deleteDnsServer: vi.fn(),
  listDnsServers: vi.fn(),
  reorderDnsServers: vi.fn(),
  updateDnsServer: vi.fn(),
}));

vi.mock("@/services/api", () => ({
  api: vi.fn(),
}));

// ── Helpers ──────────────────────────────────────────────────────────────────

function makeModule(overrides: Partial<ToolModule> = {}): ToolModule {
  return { name: "ping", enabled: true, has_settings: false, ...overrides };
}

function makePermission(toolName: string, role: UserRole, overrides: Partial<AccessPermission> = {}): AccessPermission {
  return { id: `${toolName}-${role}`, tool_name: toolName, role, allowed: true, ...overrides };
}

function renderPage() {
  return render(
    <MemoryRouter>
      <AdminModulesPage />
    </MemoryRouter>,
  );
}

// ── Tests ────────────────────────────────────────────────────────────────────

describe("AdminModulesPage", () => {
  beforeEach(async () => {
    await i18n.changeLanguage("en");
    vi.clearAllMocks();
  });

  afterEach(async () => {
    await i18n.changeLanguage("en");
  });

  describe("loading state", () => {
    it("renders spinner while modules are loading", () => {
      mockListModules.mockReturnValue(new Promise(() => {}));
      mockListRolePermissions.mockReturnValue(new Promise(() => {}));

      renderPage();

      expect(screen.getByRole("status")).toBeInTheDocument();
    });
  });

  describe("error state", () => {
    it("renders error banner when loading fails", async () => {
      mockListModules.mockRejectedValue(new Error("Network error"));
      mockListRolePermissions.mockResolvedValue({ permissions: [] });

      renderPage();

      expect(await screen.findByText("Network error")).toBeInTheDocument();
    });
  });

  describe("matrix rendering", () => {
    it("disables role toggles when a module is disabled", async () => {
      mockListModules.mockResolvedValue({
        modules: [
          makeModule({ name: "ping", enabled: false }),
          makeModule({ name: "traceroute", enabled: true }),
          makeModule({ name: "dns_lookup", enabled: true }),
          makeModule({ name: "ssl_viewer", enabled: true }),
        ],
      });
      mockListRolePermissions.mockResolvedValue({
        permissions: [
          makePermission("ping", "administrator"),
          makePermission("ping", "authenticated"),
          makePermission("ping", "visitor"),
          makePermission("traceroute", "administrator"),
          makePermission("traceroute", "authenticated"),
          makePermission("traceroute", "visitor"),
          makePermission("dns_lookup", "administrator"),
          makePermission("dns_lookup", "authenticated"),
          makePermission("dns_lookup", "visitor"),
          makePermission("ssl_viewer", "administrator"),
          makePermission("ssl_viewer", "authenticated"),
          makePermission("ssl_viewer", "visitor"),
        ],
      });

      renderPage();

      await screen.findByText("Ping");

      const rows = screen.getAllByRole("row").slice(1); // skip header
      const pingRow = rows[0]!; // first module is ping (disabled)
      const otherRows = rows.slice(1);

      for (const toggle of within(pingRow).getAllByRole("switch").slice(1)) {
        expect(toggle).toBeDisabled();
      }

      for (const row of otherRows) {
        for (const toggle of within(row).getAllByRole("switch").slice(1)) {
          expect(toggle).not.toBeDisabled();
        }
      }
    });

    it("shows settings gear only for modules with has_settings", async () => {
      mockListModules.mockResolvedValue({
        modules: [
          makeModule({ name: "dns_lookup", enabled: true, has_settings: true }),
          makeModule({ name: "ping", enabled: true, has_settings: false }),
        ],
      });
      mockListRolePermissions.mockResolvedValue({
        permissions: [
          makePermission("ping", "administrator"),
          makePermission("ping", "authenticated"),
          makePermission("ping", "visitor"),
          makePermission("dns_lookup", "administrator"),
          makePermission("dns_lookup", "authenticated"),
          makePermission("dns_lookup", "visitor"),
        ],
      });

      renderPage();

      await screen.findByText("DNS Lookup");

      const rows = screen.getAllByRole("row").slice(1);
      const dnsRow = rows[0]!;
      const pingRow = rows[1]!;

      // DNS Lookup has has_settings=true → gear button visible
      expect(within(dnsRow).getByRole("button", { name: "Settings" })).toBeInTheDocument();
      // Ping has has_settings=false → no gear button
      expect(within(pingRow).queryByRole("button", { name: "Settings" })).not.toBeInTheDocument();
    });
  });

  describe("interactions", () => {
    it("preserves role permission values when toggling enabled off and on", async () => {
      mockUpdateModule.mockResolvedValue({ module: { name: "ping", enabled: false } });

      mockListModules.mockResolvedValue({
        modules: [makeModule({ name: "ping", enabled: true })],
      });
      mockListRolePermissions.mockResolvedValue({
        permissions: [
          makePermission("ping", "administrator", { allowed: true }),
          makePermission("ping", "authenticated", { allowed: true }),
          makePermission("ping", "visitor", { allowed: false }),
        ],
      });

      renderPage();

      await screen.findByText("Ping");

      const row = () => screen.getAllByRole("row")[1]!;
      const enabledToggle = () => within(row()).getAllByRole("switch")[0]!;
      const roleToggles = () => within(row()).getAllByRole("switch").slice(1);

      // Initial state: role toggles reflect permissions
      expect(roleToggles()[0]).toBeChecked(); // admin: true
      expect(roleToggles()[1]).toBeChecked(); // auth: true
      expect(roleToggles()[2]).not.toBeChecked(); // visitor: false

      // Toggle Enabled OFF → role toggles become disabled
      fireEvent.click(enabledToggle());
      expect(mockUpdateModule).toHaveBeenCalledWith("ping", { enabled: false });

      // After optimistic update: all role toggles are disabled
      for (const toggle of roleToggles()) {
        expect(toggle).toBeDisabled();
      }

      // Toggle Enabled ON
      mockUpdateModule.mockResolvedValue({ module: { name: "ping", enabled: true } });
      fireEvent.click(enabledToggle());

      // Role toggles are re-enabled with original values preserved
      expect(roleToggles()[0]).toBeChecked(); // admin: still true
      expect(roleToggles()[1]).toBeChecked(); // auth: still true
      expect(roleToggles()[2]).not.toBeChecked(); // visitor: still false
      for (const toggle of roleToggles()) {
        expect(toggle).not.toBeDisabled();
      }
    });
  });
});

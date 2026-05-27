import { test, expect } from "@playwright/test";

const ADMIN_USER = {
  user: {
    id: "test-admin-001",
    email: "admin@sakn.test",
    first_name: "Test",
    last_name: "Admin",
    role: "administrator",
    status: "active",
    email_verified: true,
    locale: "en",
    created_at: "2024-01-01T00:00:00Z",
  },
};

const MODULES = {
  modules: [
    { name: "ping", enabled: true, has_settings: false },
    { name: "traceroute", enabled: true, has_settings: true },
    { name: "dns_lookup", enabled: false, has_settings: true },
    { name: "ssl_viewer", enabled: true, has_settings: false },
  ],
};

const PERMISSIONS = {
  permissions: [
    { id: "perm-1", tool_name: "ping", role: "administrator", allowed: true },
    { id: "perm-2", tool_name: "ping", role: "authenticated", allowed: true },
    { id: "perm-3", tool_name: "ping", role: "visitor", allowed: false },
    { id: "perm-4", tool_name: "traceroute", role: "administrator", allowed: true },
    { id: "perm-5", tool_name: "traceroute", role: "authenticated", allowed: false },
    { id: "perm-6", tool_name: "traceroute", role: "visitor", allowed: false },
    { id: "perm-7", tool_name: "dns_lookup", role: "administrator", allowed: true },
    { id: "perm-8", tool_name: "dns_lookup", role: "authenticated", allowed: false },
    { id: "perm-9", tool_name: "dns_lookup", role: "visitor", allowed: false },
    { id: "perm-10", tool_name: "ssl_viewer", role: "administrator", allowed: true },
    { id: "perm-11", tool_name: "ssl_viewer", role: "authenticated", allowed: true },
    { id: "perm-12", tool_name: "ssl_viewer", role: "visitor", allowed: true },
  ],
};

test.describe("Admin Modules Page", () => {
  test.beforeEach(async ({ page }) => {
    await page.route("**/api/v1/auth/me", (route) => {
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(ADMIN_USER),
      });
    });
    await page.route("**/api/v1/admin/modules", (route) => {
      if (route.request().method() === "GET") {
        route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(MODULES),
        });
      } else {
        route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ module: { name: "ping", enabled: true } }),
        });
      }
    });
    await page.route("**/api/v1/admin/role-permissions", (route) => {
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(PERMISSIONS),
      });
    });
  });

  test("renders the module matrix with correct columns", async ({ page }) => {
    await page.goto("/admin/modules", { waitUntil: "networkidle" });

    await expect(page.locator("h1")).toHaveText("Module Activation");

    // Verify table headers
    const headerTexts = await page.locator("th").allTextContents();
    expect(headerTexts).toContain("Tool");
    expect(headerTexts).toContain("Enabled");
    // The matrix has role columns for administrator, authenticated, visitor
    const headersLower = headerTexts.map((t) => t.toLowerCase());
    expect(headersLower).toContain("administrator");
    expect(headersLower).toContain("authenticated");
    expect(headersLower).toContain("visitor");

    // Verify all 4 modules are listed
    await expect(page.locator("text=Ping")).toBeVisible();
    await expect(page.locator("text=Traceroute")).toBeVisible();
    await expect(page.locator("text=DNS Lookup")).toBeVisible();
    await expect(page.locator("text=TLS Certificate Viewer")).toBeVisible();
  });

  test("disables role toggles when module enabled is turned off", async ({
    page,
  }) => {
    await page.goto("/admin/modules", { waitUntil: "networkidle" });

    await expect(page.locator("text=Ping")).toBeVisible();

    // Find the DNS Lookup row (it has enabled: false in our fixture)
    const rows = page.locator("tbody tr");
    const dnsRow = rows.filter({ has: page.locator("text=DNS Lookup") });

    // The role toggles in the DNS Lookup row should be disabled
    await dnsRow.first().waitFor({ state: "visible" });
    // Role toggles are the 2nd-4th switches in the row
    const dnsSwitches = dnsRow.locator('[role="switch"]');
    const count = await dnsSwitches.count();
    // 1st switch = Enabled, 2nd-4th = role toggles
    for (let i = 1; i < count; i++) {
      await expect(dnsSwitches.nth(i)).toBeDisabled();
    }
  });

  test("/admin/access returns 404", async ({ page }) => {
    // Re-mock the response mock for the redirect request
    // The AdminGuard check hits auth/me again, which is fine
    await page.goto("/admin/access", { waitUntil: "networkidle" });

    // The route was removed — expect a 404 page, not a redirect
    await expect(page.locator("h1")).toContainText("404");
  });
});

import { test, expect } from "@playwright/test";

test.describe("Admin Pages", () => {
  test.beforeEach(async ({ page }) => {
    // Mock auth API — inject admin user without backend
    await page.route("**/api/v1/auth/me", (route) => {
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
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
        }),
      });
    });
    await page.goto("/", { waitUntil: "networkidle" });

  });

  test("admin section appears in sidebar", async ({ page }) => {
    const navText = await page.textContent("nav");
    expect(navText).toContain("Administration");
  });

  const adminPages: [string, string, string][] = [
    ["/admin/users", "User Management"],
["/admin/rate-limits", "Rate Limits"],
    ["/admin/modules", "Module Activation"],
    ["/admin/settings", "Global Settings"],
    ["/admin/logs", "Log Viewer"],
  ];

  for (const [route, expected] of adminPages) {
    test(`admin page ${route} shows correct heading`, async ({ page }) => {
      await page.goto(route, { waitUntil: "networkidle" });

      await expect(page.locator("h1")).toHaveText(expected);
    });
  }
});

test.describe("Visitor Mode", () => {
  test("admin section is hidden in visitor mode", async ({ page }) => {
    await page.goto("/", { waitUntil: "networkidle" });


    // Default unauthenticated state is "visitor" (useAuth: role ?? "visitor")
    const navText = await page.textContent("nav");
    expect(navText).not.toContain("Administration");

    const headerText = await page.textContent("header");
    expect(headerText).toContain("Sign In");
  });
});

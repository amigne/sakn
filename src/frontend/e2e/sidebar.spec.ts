import { test, expect } from "@playwright/test";

test.describe("Sidebar", () => {
  test("shows admin section when authenticated as administrator", async ({ page }) => {
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


    const navText = await page.textContent("nav");
    expect(navText).toContain("Administration");
  });
});

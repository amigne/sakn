import { expect, test } from "@playwright/test";

const ADMIN_USER = {
  id: "test-admin-001",
  email: "admin@sakn.test",
  first_name: "Test",
  last_name: "Admin",
  role: "administrator",
  status: "active",
  email_verified: true,
  locale: "en-US",
  created_at: "2024-01-01T00:00:00Z",
};

test.describe("Profile Language — i18n flow", () => {
  let savedLanguage = "en";

  test.beforeEach(async ({ page }) => {
    savedLanguage = "en";
    await page.route("**/api/v1/auth/me", (route) => {
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ user: ADMIN_USER }),
      });
    });
    await page.route("**/api/v1/preferences", async (route) => {
      if (route.request().method() === "GET") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            preferences: { language: savedLanguage, locale: "en-US", theme: "light", display_mode: "table" },
          }),
        });
      } else {
        const body = JSON.parse(route.request().postData() ?? "{}");
        if (body.language) savedLanguage = body.language;
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            preferences: { language: savedLanguage, locale: "en-US", theme: "light", display_mode: "table" },
          }),
        });
      }
    });
    await page.route("**/api/v1/auth/csrf", (route) => {
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({}) });
    });
  });

  test("changing language via TopBar toggle persists across reload", async ({ page }) => {
    await page.goto("/account/preferences", { waitUntil: "networkidle" });

    // Wait for the page to fully render (English heading "Profile")
    await expect(page.getByRole("heading", { name: /profile/i })).toBeVisible({ timeout: 5000 });

    // Use the TopBar language toggle
    const langBtn = page.getByTestId("language-toggle");
    await expect(langBtn).toHaveText("EN");
    await langBtn.click();
    await expect(langBtn).toHaveText("FR");

    // After switching to French, the heading should show "Profil"
    await expect(page.getByRole("heading", { name: /profil/i })).toBeVisible({ timeout: 5000 });

    // Reload and verify FR is still active
    await page.reload({ waitUntil: "networkidle" });
    await expect(page.getByRole("heading", { name: /profil/i })).toBeVisible({ timeout: 5000 });
  });
});

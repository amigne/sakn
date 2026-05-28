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
    // Allow CSRF token fetch
    await page.route("**/api/v1/auth/csrf", (route) => {
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({}) });
    });
  });

  test("changing the language in profile updates UI immediately and persists across reload", async ({ page }) => {
    await page.goto("/account/preferences", { waitUntil: "networkidle" });

    // The language dropdown trigger button is inside a label "Language"
    const langTrigger = page.getByRole("button", { name: /language/i });
    await expect(langTrigger).toBeVisible();
    await langTrigger.click();

    // Select "Français" from the dropdown
    const frOption = page.getByRole("option", { name: "Français" });
    await frOption.click();

    // After switching to French, the heading should show "Profil" (French translation)
    await expect(page.getByRole("heading", { name: /profil/i })).toBeVisible({ timeout: 5000 });

    // Reload and verify FR is still active (language persisted to server)
    await page.reload({ waitUntil: "networkidle" });
    await expect(page.getByRole("heading", { name: /profil/i })).toBeVisible({ timeout: 5000 });
  });
});

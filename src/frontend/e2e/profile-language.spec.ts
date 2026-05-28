import { test, expect } from "@playwright/test";

const TEST_PASSWORD = "E2eTest1234!";

function uniqueEmail() {
  return `e2e-lang-${Date.now()}@test.com`;
}

test.describe("Profile Language", () => {
  test("language change via profile dropdown persists across reload", async ({ page }) => {
    const email = uniqueEmail();

    // ── Setup: register and login ────────────────────────────────────────
    await page.request.post("/api/v1/auth/register", {
      data: {
        email,
        password: TEST_PASSWORD,
        password_confirm: TEST_PASSWORD,
        first_name: "Lang",
        last_name: "Test",
      },
    });

    await page.request.post("/api/v1/auth/login", {
      data: { email, password: TEST_PASSWORD },
    });

    // ── Navigate to profile page ─────────────────────────────────────────
    await page.goto("/account/preferences", { waitUntil: "networkidle" });

    // Page heading in English (default)
    await expect(page.getByRole("heading", { name: "Profile", level: 1 })).toBeVisible();

    // ── Change language to French via the profile dropdown ───────────────
    const langTrigger = page.getByRole("combobox", { name: "Language" });
    await langTrigger.click();

    // Radix renders the option list in a portal; select "Français"
    await page.getByRole("option", { name: "Français" }).click();

    // UI should switch to French immediately (Bug 2 regression: i18n.setLanguage called)
    await expect(page.getByRole("heading", { name: "Profil", level: 1 })).toBeVisible();

    // The language select trigger now shows "Français" and has French aria-label
    await expect(page.getByRole("combobox", { name: "Langue" })).toBeVisible();

    // ── Reload and verify persistence ────────────────────────────────────
    await page.reload({ waitUntil: "networkidle" });

    // Heading should still be in French (cookie persists)
    await expect(page.getByRole("heading", { name: "Profil", level: 1 })).toBeVisible();

    // Verify the lang cookie was set
    const cookies = await page.context().cookies();
    const langCookie = cookies.find((c) => c.name === "lang");
    expect(langCookie?.value).toBe("fr");
  });

  test("TopBar language toggle switches UI immediately", async ({ page }) => {
    // No auth needed — the TopBar toggle works for visitors
    await page.goto("/login", { waitUntil: "networkidle" });

    // Page in English
    await expect(page.getByRole("heading", { name: /sign in/i })).toBeVisible();

    // Toggle language via TopBar button
    const toggle = page.getByTestId("language-toggle");
    await expect(toggle).toHaveText("EN");
    await toggle.click();

    // UI switches to French
    await expect(toggle).toHaveText("FR");
    await expect(page.getByRole("heading", { name: /connexion/i })).toBeVisible();

    // Reload — language persists via cookie
    await page.reload({ waitUntil: "networkidle" });
    await expect(page.getByRole("heading", { name: /connexion/i })).toBeVisible();
    await expect(page.getByTestId("language-toggle")).toHaveText("FR");
  });
});

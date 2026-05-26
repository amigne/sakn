import { test, expect } from "@playwright/test";

test.describe("SAKN smoke tests", () => {
  test("home page redirects to ping", async ({ page }) => {
    await page.goto("/");
    await page.waitForURL("**/ping");
    expect(page.url()).toContain("/ping");
  });

  test("ping page loads with form", async ({ page }) => {
    await page.goto("/ping");
    await expect(page.locator("header")).toBeVisible();
    await expect(page.locator("main")).toBeVisible();
  });

  test("theme toggle cycles", async ({ page }) => {
    await page.goto("/ping");
    const themeBtn = page.locator('button[aria-label*="Theme"]');
    await expect(themeBtn).toBeVisible();
    await themeBtn.click();
    // Should not crash
    await expect(page.locator("header")).toBeVisible();
  });

  test("language toggle switches", async ({ page }) => {
    await page.goto("/ping");
    const langBtn = page.locator('button[aria-label*="lang" i]');
    await expect(langBtn).toBeVisible();
    const initial = await langBtn.textContent();
    await langBtn.click();
    const after = await langBtn.textContent();
    expect(after).not.toBe(initial);
  });

  test("mobile hamburger menu", async ({ page }) => {
    await page.setViewportSize({ width: 400, height: 800 });
    await page.goto("/ping");
    await expect(page.locator('button[aria-label="Toggle sidebar"]')).toBeVisible();
  });

  test("login page accessible", async ({ page }) => {
    await page.goto("/login");
    await expect(page.locator("main")).toBeVisible();
  });

  test("register page accessible", async ({ page }) => {
    await page.goto("/register");
    await expect(page.locator("main")).toBeVisible();
  });
});

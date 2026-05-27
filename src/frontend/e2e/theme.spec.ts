import { test, expect } from "@playwright/test";

test.describe("Theme", () => {
  test("toggles from light to dark mode", async ({ page }) => {
    // Force initial state to light for deterministic behavior
    await page.addInitScript(() => localStorage.setItem("theme", "light"));
    await page.goto("/", { waitUntil: "networkidle" });

    const card = page.locator(".card").first();
    const lightBg = await card.evaluate((el) =>
      getComputedStyle(el).backgroundColor,
    );

    const themeBtn = page.locator('button[aria-label*="Theme" i]');
    await themeBtn.click(); // light → dark

    await expect.poll(() =>
      page.evaluate(() => document.documentElement.classList.contains("dark"))
    ).toBe(true);

    const darkBg = await card.evaluate((el) =>
      getComputedStyle(el).backgroundColor,
    );
    expect(darkBg).not.toBe(lightBg);
  });

  test("cycles theme: system -> light -> dark", async ({ page }) => {
    await page.goto("/", { waitUntil: "networkidle" });

    const themeBtn = page.locator('button[aria-label*="Theme"]');
    const initialLabel = await themeBtn.getAttribute("aria-label");
    const initialDark = await page.evaluate(() =>
      document.documentElement.classList.contains("dark"),
    );

    // Click once: system -> light or light -> dark
    await themeBtn.click();
    await expect.poll(async () => {
      return await themeBtn.getAttribute("aria-label");
    }).not.toBe(initialLabel);

    // Click twice
    await themeBtn.click();
    const label2 = await themeBtn.getAttribute("aria-label");
    // After two clicks, we should be in a different state from initial
    await expect.poll(() =>
      page.evaluate(() => document.documentElement.classList.contains("dark"))
    ).not.toBe(initialDark);
  });

  test("number input uses correct color-scheme in dark mode", async ({
    page,
  }) => {
    await page.goto("/", { waitUntil: "networkidle" });

    // Switch to dark mode
    const themeBtn = page.locator('button[aria-label*="Theme"]');
    await themeBtn.click();
    await themeBtn.click();

    await expect.poll(() =>
      page.evaluate(() => document.documentElement.classList.contains("dark"))
    ).toBe(true);

    const countInput = page.locator('input[type="number"]').first();
    const colorScheme = await countInput.evaluate((el) =>
      getComputedStyle(el).colorScheme,
    );
    expect(colorScheme).toBe("dark");
  });
});

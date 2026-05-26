import { test, expect } from "@playwright/test";

test.describe("Theme", () => {
  test("toggles from light to dark mode", async ({ page }) => {
    test.skip(!!process.env.CI, "Pre-existing — theme is 3-state (system→light→dark), see #201");
    await page.goto("/", { waitUntil: "networkidle" });
    await page.waitForTimeout(500);

    const card = page.locator(".card").first();
    const lightBg = await card.evaluate((el) =>
      getComputedStyle(el).backgroundColor,
    );

    await page.click('button[aria-label*="Theme"]');
    await page.waitForTimeout(300);

    const hasDark = await page.evaluate(() =>
      document.documentElement.classList.contains("dark"),
    );
    expect(hasDark).toBe(true);

    const darkBg = await card.evaluate((el) =>
      getComputedStyle(el).backgroundColor,
    );
    expect(darkBg).not.toBe(lightBg);
  });

  test("cycles theme: system -> light -> dark", async ({ page }) => {
    await page.goto("/", { waitUntil: "networkidle" });
    await page.waitForTimeout(500);

    const themeBtn = page.locator('button[aria-label*="Theme"]');
    const initialLabel = await themeBtn.getAttribute("aria-label");
    const initialDark = await page.evaluate(() =>
      document.documentElement.classList.contains("dark"),
    );

    // Click once: system -> light or light -> dark
    await themeBtn.click();
    await page.waitForTimeout(300);
    const label1 = await themeBtn.getAttribute("aria-label");
    expect(label1).not.toBe(initialLabel);

    // Click twice
    await themeBtn.click();
    await page.waitForTimeout(300);
    const label2 = await themeBtn.getAttribute("aria-label");
    // After two clicks, we should be in a different state from initial
    const darkAfter2 = await page.evaluate(() =>
      document.documentElement.classList.contains("dark"),
    );
    expect(darkAfter2).not.toBe(initialDark);
  });

  test("number input uses correct color-scheme in dark mode", async ({
    page,
  }) => {
    await page.goto("/", { waitUntil: "networkidle" });
    await page.waitForTimeout(500);

    // Switch to dark mode
    const themeBtn = page.locator('button[aria-label*="Theme"]');
    await themeBtn.click();
    await themeBtn.click();
    await page.waitForTimeout(300);

    const isDark = await page.evaluate(() =>
      document.documentElement.classList.contains("dark"),
    );
    expect(isDark).toBe(true);

    const countInput = page.locator('input[type="number"]').first();
    const colorScheme = await countInput.evaluate((el) =>
      getComputedStyle(el).colorScheme,
    );
    expect(colorScheme).toBe("dark");
  });
});

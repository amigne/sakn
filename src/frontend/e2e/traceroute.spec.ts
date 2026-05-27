import { test, expect } from "@playwright/test";

test.describe("Traceroute", () => {
  test("executes with configurable probe count and resets", async ({
    page,
  }) => {
    test.skip(!!process.env.CI, "Backend required — follow-up issue for E2E backend-dependent tests");
    await page.goto("/traceroute", { waitUntil: "networkidle" });

    // Run with default probe count
    await page.click('button:has-text("Trace")');
    await expect(page.locator("th").first()).toBeVisible({ timeout: 10000 });

    const headers = await page.locator("th").allTextContents();
    expect(headers.length).toBeGreaterThan(0);

    // Change probe count and reset
    const probesInput = page.locator('input[type="number"]').nth(2);
    await probesInput.fill("5");

    await page.click('button:has-text("Reset")');
    await page.click('button:has-text("Trace")');
    await expect(page.locator("th").first()).toBeVisible({ timeout: 10000 });

    const headersNew = await page.locator("th").allTextContents();
    expect(headersNew.length).toBeGreaterThan(0);
  });
});

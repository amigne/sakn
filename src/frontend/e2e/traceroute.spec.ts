import { test, expect } from "@playwright/test";

test.describe("Traceroute", () => {
  test("executes with configurable probe count and resets", async ({
    page,
  }) => {
    await page.goto("/traceroute", { waitUntil: "networkidle" });

    await page.getByPlaceholder("8.8.8.8").fill("1.1.1.1");
    // Use TCP probes — UDP is blocked on GitHub Actions runners
    await page.getByRole("combobox").first().click();
    await page.getByRole("option", { name: "TCP" }).click();
    // Run with default probe count
    await page.click('button:has-text("Trace")');
    await expect(page.locator("th").first()).toBeVisible({ timeout: 25000 });

    const headers = await page.locator("th").allTextContents();
    expect(headers.length).toBeGreaterThan(0);

    // Change probe count and reset
    const probesInput = page.locator('input[type="number"]').nth(2);
    await probesInput.fill("5");

    await page.click('button:has-text("Reset")');
    // Re-select TCP after reset (reset reverts form to UDP default)
    await page.getByRole("combobox").first().click();
    await page.getByRole("option", { name: "TCP" }).click();
    await page.click('button:has-text("Trace")');
    await expect(page.locator("th").first()).toBeVisible({ timeout: 25000 });

    const headersNew = await page.locator("th").allTextContents();
    expect(headersNew.length).toBeGreaterThan(0);
  });
});

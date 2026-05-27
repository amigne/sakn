import { test, expect } from "@playwright/test";

test.describe("Tool Execution", () => {
  test("executes ping and displays results in table", async ({ page }) => {
    await page.goto("/ping", { waitUntil: "networkidle" });

    const execBtn = page.locator("button", { hasText: "Execute" });
    await execBtn.click();
    await expect(page.locator("table tr").first()).toBeVisible({ timeout: 10000 });

    const rows = await page.locator("table tr").count();
    expect(rows).toBeGreaterThan(1);

    await expect(page.getByText("Summary")).toBeVisible();
  });

  test("text view toggle shows raw output", async ({ page }) => {
    await page.goto("/ping", { waitUntil: "networkidle" });

    await page.locator("button", { hasText: "Execute" }).click();
    await expect(page.locator("table tr").first()).toBeVisible({ timeout: 10000 });

    await page.click('button:has-text("Text")');
    await expect(page.locator("pre").first()).toBeVisible({ timeout: 5000 });
  });
});

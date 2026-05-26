import { test, expect } from "@playwright/test";

test.describe("Tool Execution", () => {
  test("executes ping and displays results in table", async ({ page }) => {
    test.skip(!!process.env.CI, "Backend required — follow-up issue for E2E backend-dependent tests");
    await page.goto("/ping", { waitUntil: "networkidle" });
    await page.waitForTimeout(500);

    const execBtn = page.locator("button", { hasText: "Execute" });
    await execBtn.click();
    await page.waitForTimeout(4000);

    const rows = await page.locator("table tr").count();
    expect(rows).toBeGreaterThan(1);

    const body = await page.textContent("body");
    expect(body).toContain("Summary");
  });

  test("text view toggle shows raw output", async ({ page }) => {
    test.skip(!!process.env.CI, "Backend required — follow-up issue for E2E backend-dependent tests");
    await page.goto("/ping", { waitUntil: "networkidle" });
    await page.waitForTimeout(500);

    await page.locator("button", { hasText: "Execute" }).click();
    await page.waitForTimeout(3000);

    await page.click('button:has-text("Text")');
    await page.waitForTimeout(300);

    const preCount = await page.locator("pre").count();
    expect(preCount).toBeGreaterThan(0);
  });
});

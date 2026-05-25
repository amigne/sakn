import { test, expect } from "@playwright/test";

test.describe("Tool Execution", () => {
  test("dev toolbar is visible and opens dropdown", async ({ page }) => {
    await page.goto("/", { waitUntil: "networkidle" });
    await page.waitForTimeout(500);

    const devBtn = page.locator("button", { hasText: "Dev:" });
    await expect(devBtn).toBeVisible();

    await devBtn.click();
    await page.waitForTimeout(300);

    // Dropdown should have role options
    const body = await page.textContent("body");
    expect(body).toContain("Admin");
  });

  test("can switch to admin role via dev toolbar", async ({ page }) => {
    await page.goto("/", { waitUntil: "networkidle" });
    await page.waitForTimeout(500);

    await page.click("button:has-text('Dev:')");
    await page.waitForTimeout(300);

    const adminOption = page.locator("button", { hasText: /^Admin$/ });
    if ((await adminOption.count()) > 0) {
      await adminOption.first().click();
      await page.waitForTimeout(500);

      const adminSection = page.locator("text=Administration");
      await expect(adminSection).toBeVisible();
    }
  });

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
